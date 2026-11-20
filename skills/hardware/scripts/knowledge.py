"""查询随包审查规则，或读取使用者在本机管理的工程知识库。"""

import argparse
from collections import Counter
from contextlib import closing
import json
import os
from pathlib import Path
import re
import sqlite3
from tempfile import NamedTemporaryFile
import unicodedata

from rule_domains import UnknownDomain, resolve_domains


RULES = Path(__file__).resolve().parents[1] / "assets" / "review-knowledge" / "rules.json"
DATA = Path("assets/engineering-library")
INDEX = Path("scripts/index.db")
PDF_HEADING = re.compile(r"PDF page ([1-9][0-9]*)")
SECTION_ROWS = (
    "SELECT sections.file, sections.anchor, sections.heading, section_content.content "
    "FROM sections JOIN section_content ON section_content.id = sections.id"
)
SOURCE_FIELDS = (
    "id", "title", "display_title", "publisher", "edition", "category", "display_group",
    "document_number", "source_sha256", "access_status", "source_url", "source_url_status",
    "source_url_edition", "related_official_url", "source_note",
)


def json_v1(path, key, expected_type):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if (not isinstance(data, dict) or type(data.get("schema_version")) is not int
            or data["schema_version"] != 1 or not isinstance(data.get(key), expected_type)):
        raise ValueError(f"无法识别 {path.name} 的 v1 数据格式")
    return data


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", str(value)).casefold().split())


def terms_for(values):
    terms = [normalized(value) for value in values]
    if not all(terms):
        raise ValueError("查询关键词不能为空")
    return terms


def library_path(root, name):
    relative = Path(name)
    if relative.anchor or ".." in relative.parts:
        raise ValueError("资料路径须相对于本机知识库目录")
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError("资料路径超出指定知识库目录")
    return target


def catalogue(root):
    rows = json_v1(library_path(root, DATA / "manifest.json"), "documents", list)["documents"]
    docs = {}
    files = set()
    for doc in rows:
        key = doc["id"]
        file = doc["reference_file"]
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", key) or key.upper() in docs:
            raise ValueError("资料编号无效或重复")
        resolved = library_path(root, file)
        if resolved in files:
            raise ValueError("资料清单含重复正文路径")
        if doc.get("source_file"):
            library_path(root, doc["source_file"])
        docs[key.upper()] = doc
        files.add(resolved)
    return docs


def describe(doc, root=None):
    result = {field: doc[field] for field in SOURCE_FIELDS if field in doc}
    if root is not None:
        source = library_path(root, doc["source_file"]) if doc.get("source_file") else None
        result["source_attached"] = source is not None and source.is_file()
        result["source_path"] = str(source) if result["source_attached"] else None
    return result


def enrich_catalogue(docs, public_sources):
    for key, doc in docs.items():
        public = public_sources.get(key)
        if public and public.get("source_sha256") == doc.get("source_sha256") and doc.get("source_sha256"):
            overrides = {field: value for field, value in doc.items() if value not in (None, "", "未核对")}
            docs[key] = {**doc, **public, **overrides}
    return docs


def metadata_match(doc, terms):
    return all(term in normalized(" ".join(str(doc.get(field, "")) for field in SOURCE_FIELDS)) for term in terms)


def open_index(root):
    path = library_path(root, INDEX)
    if not path.is_file():
        raise ValueError("知识库缺少 scripts/index.db，请提供已有索引或运行 build-index")
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def locators(row):
    page = PDF_HEADING.fullmatch(row["heading"])
    return {"locator": row["heading"], "anchor": row["anchor"],
            "pdf_page": int(page[1]) if page else None}


def search(root, docs, ids, names, terms, limit):
    selected_ids = {value.upper() for value in ids}
    unknown = selected_ids - docs.keys()
    if unknown:
        raise ValueError("清单中没有文档：" + ", ".join(sorted(unknown)))
    names, terms = terms_for(names), terms_for(terms)
    selected = {doc["reference_file"]: doc for key, doc in docs.items()
                if (not selected_ids or key in selected_ids) and metadata_match(doc, names)}
    found = []
    if selected:
        with closing(open_index(root)) as db:
            # Query exact file paths in bounded groups. A category can contain multiple documents.
            files = list(selected)
            for offset in range(0, len(files), 200):
                chunk = files[offset:offset + 200]
                placeholders = ",".join("?" for _ in chunk)
                for row in db.execute(f"{SECTION_ROWS} WHERE sections.file IN ({placeholders})", chunk):
                    content = normalized(row["content"])
                    positions = [content.find(term) for term in terms]
                    if min(positions) < 0:
                        continue
                    start = max(0, min(positions) - 50)
                    doc = selected[row["file"]]
                    found.append({
                        "document_id": doc["id"], "title": doc.get("display_title", doc.get("title")),
                        "edition": doc.get("edition"), **locators(row),
                        "reference": f'{row["file"]}#{row["anchor"]}',
                        "snippet": content[start:start + 220],
                        "score": sum(content.count(term) for term in terms),
                    })
    found.sort(key=lambda row: (-row["score"], row["document_id"], row["anchor"]))
    return {"searched_documents": len(selected), "matched_sections": len(found), "results": found[:limit]}


def read_reference(root, doc, locator, offset, limit):
    if locator.isascii() and locator.isdigit():
        locator = f"PDF page {int(locator)}"
    with closing(open_index(root)) as db:
        rows = db.execute(f"{SECTION_ROWS} WHERE sections.file = ? AND "
                          "(sections.anchor = ? OR sections.heading = ?)",
                          (doc["reference_file"], locator, locator)).fetchall()
    exact = [row for row in rows if row["anchor"] == locator]
    rows = exact or rows
    if len(rows) != 1:
        raise ValueError("该定位缺失或不唯一，请使用 search 返回的 anchor")
    row = rows[0]
    fields = locators(row)
    text = row["content"]
    inline = re.search(r"^\s*印刷页 ([^\n。]+)。", text, flags=re.M)
    printed = inline[1] if inline else None
    labels_path = library_path(root, DATA / "page-labels.json")
    if fields["pdf_page"] and labels_path.is_file():
        labels = json_v1(labels_path, "documents", dict)["documents"]
        entry = labels.get(doc["id"])
        if entry is not None:
            if not doc.get("source_sha256") or entry["source_sha256"] != doc["source_sha256"]:
                raise ValueError("印刷页记录与当前原件版本不一致")
            label = entry["pages"].get(str(fields["pdf_page"]))
            if label is not None and printed is not None and label != printed:
                raise ValueError("印刷页标与正文内页标不一致")
            printed = label if label is not None else printed
    return {"document": describe(doc, root), **fields, "printed_page": printed,
            "text": text[offset:offset + limit], "total_characters": len(text),
            "next_offset": offset + limit if offset + limit < len(text) else None}


def review_rules(data, sources, args):
    terms = terms_for(args.terms)
    known_ids = {rule["id"] for rule in data}
    domains = resolve_domains(args.domain, data)
    unknown = set(args.id) - known_ids
    if unknown:
        raise ValueError("未知规则编号或领域：" + ", ".join(sorted(unknown)))
    selected = []
    for rule in data:
        if (args.id and rule["id"] not in args.id) or (domains and rule["domain"] not in domains):
            continue
        if not all(term in normalized(json.dumps(rule, ensure_ascii=False)) for term in terms):
            continue
        if args.summary:
            selected.append({key: rule[key] for key in ("id", "title", "domain", "applies_when")})
        else:
            evidence = []
            for item in rule["evidence"]:
                key = item["document_id"]
                source = sources[key.upper()]
                evidence.append({**item, "source": describe(source), "locator": f"PDF page {item['pdf_page']}"})
            selected.append({**rule, "evidence": evidence})
    return {"count": len(selected), "rules": selected}


def sections(markdown):
    headings = list(re.finditer(r"^##[ \t]+(.+?)[ \t]*$", markdown, re.M))
    if not headings:
        yield "document", "Document", markdown
        return
    used = set()
    for i, match in enumerate(headings):
        title = match[1]
        slug = re.sub(r"[^\w\s-]", "", title.casefold())
        slug = re.sub(r"\s+", "-", slug).strip("-") or "section"
        anchor = slug
        suffix = 2
        while anchor in used:
            anchor = f"{slug}-{suffix}"
            suffix += 1
        used.add(anchor)
        end = headings[i + 1].start() if i + 1 < len(headings) else len(markdown)
        yield anchor, title, markdown[match.end():end].strip()


def build_index(root, docs, replace):
    target = library_path(root, INDEX)
    if not docs:
        raise ValueError("资料清单没有可建立索引的文档")
    if target.exists() and not replace:
        raise ValueError("索引已存在，更新指定索引时传入 --replace")
    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=target.parent, suffix=".db", delete=False) as stream:
        staging = Path(stream.name)
    count = 0
    try:
        with closing(sqlite3.connect(staging)) as db, db:
            db.execute("CREATE TABLE sections(id INTEGER PRIMARY KEY, file TEXT, anchor TEXT, heading TEXT)")
            db.execute("CREATE INDEX sections_by_file ON sections(file)")
            db.execute("CREATE TABLE section_content(id INTEGER PRIMARY KEY, content TEXT)")
            for doc in docs.values():
                path = library_path(root, doc["reference_file"])
                for anchor, heading, content in sections(path.read_text(encoding="utf-8-sig")):
                    count += 1
                    db.execute("INSERT INTO sections VALUES (?, ?, ?, ?)",
                               (count, doc["reference_file"], anchor, heading))
                    db.execute("INSERT INTO section_content VALUES (?, ?)", (count, content))
        if replace:
            staging.replace(target)
        elif os.name == "nt":
            staging.rename(target)
        else:
            os.link(staging, target)
    finally:
        staging.unlink(missing_ok=True)
    return {"indexed_documents": len(docs), "indexed_sections": count}


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--library", type=Path, help="本机知识库根目录")
    sub = parser.add_subparsers(dest="command", required=True)
    sources = sub.add_parser("sources", help="跨规则书目、手册索引和制造版次查证")
    sources.add_argument("terms", nargs="+")
    sources.add_argument("--limit", type=int, choices=range(1, 101), default=10)
    sub.add_parser("status", help="列出规则数量及索引覆盖")
    rules = sub.add_parser("rules", help="按领域、编号或关键词检索规则")
    rules.add_argument("terms", nargs="*")
    rules.add_argument("--domain", action="append", default=[], help="按领域或常用别名筛选，可重复")
    rules.add_argument("--id", action="append", default=[])
    rules.add_argument("--summary", action="store_true")
    find = sub.add_parser("find", help="按书目、厂商、编号等定位资料")
    find.add_argument("terms", nargs="+")
    find.add_argument("--limit", type=int, choices=range(1, 101), default=20)
    lookup = sub.add_parser("search", help="从本机 SQLite 索引检索正文")
    lookup.add_argument("terms", nargs="+")
    lookup.add_argument("--doc", action="append", default=[])
    lookup.add_argument("--name", action="append", default=[])
    lookup.add_argument("--limit", type=int, choices=range(1, 31), default=6)
    read = sub.add_parser("read", help="读取一页或一段正文")
    read.add_argument("document_id")
    read.add_argument("locator")
    read.add_argument("--offset", type=int, default=0)
    read.add_argument("--limit", type=int, choices=range(1, 22001), default=6000)
    build = sub.add_parser("build-index", help="以清单中的 Markdown 建立本机索引")
    build.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    if args.command == "sources":
        from source_catalog import search_sources

        print(json.dumps(search_sources(args.terms, args.limit), ensure_ascii=False, indent=2))
        return
    try:
        root = args.library.resolve(strict=True) if args.library else None
        if root is None and args.command in {"search", "read", "build-index"}:
            raise ValueError("请用 --library 指定本机知识库目录")
        public = json_v1(RULES, "rules", list)
        sources = {key.upper(): {"id": key, **entry} for key, entry in public["sources"].items()}
        docs = enrich_catalogue(catalogue(root), sources) if root is not None else {}
        data = public["rules"]
        if root is not None and args.command in {"rules", "status"}:
            path = library_path(root, DATA / "review-rules.json")
            if path.is_file():
                data = json_v1(path, "rules", list)["rules"]
                sources.update(docs)
            else:
                sources = {**docs, **sources}
        if args.command == "status":
            result = {"review_rules": len(data), "rule_domains": dict(Counter(rule["domain"] for rule in data)),
                      "reference_sources": len(sources), "library_configured": root is not None}
            if root is not None:
                index_present = library_path(root, INDEX).is_file()
                scanned = Counter()
                if index_present:
                    with closing(open_index(root)) as db:
                        scanned.update(dict(db.execute(
                            "SELECT sections.file, COUNT(*) FROM sections JOIN section_content "
                            "ON section_content.id = sections.id GROUP BY sections.file")))
                result.update({"documents": len(docs), "index_present": index_present,
                               "indexed_sections": sum(scanned[doc["reference_file"]] for doc in docs.values()),
                               "missing_from_index": [key for key, doc in docs.items() if not scanned[doc["reference_file"]]]})
        elif args.command == "rules":
            result = review_rules(data, sources, args)
        elif args.command == "find":
            terms = terms_for(args.terms)
            selected = [describe(doc, root) for doc in (docs if root is not None else sources).values()
                        if metadata_match(doc, terms)]
            result = {"count": len(selected), "documents": selected[:args.limit]}
        elif args.command == "search":
            result = search(root, docs, args.doc, args.name, args.terms, args.limit)
        elif args.command == "read":
            if args.offset < 0:
                raise ValueError("offset 必须大于或等于 0")
            result = read_reference(root, docs[args.document_id.upper()], args.locator, args.offset, args.limit)
        else:
            result = build_index(root, docs, args.replace)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except UnknownDomain as error:
        print(json.dumps({"error": str(error), "available_domains": error.available_domains}, ensure_ascii=False))
        return 1
    except (OSError, KeyError, TypeError, ValueError, sqlite3.Error) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
