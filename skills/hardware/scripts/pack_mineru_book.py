"""将指定的 MinerU Middle JSON 转成可在本机检索的逐页 OCR 索引。"""

import argparse
import gzip
import io
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from ocr_books import DIGEST, load_books, pages_and_coverage, valid_book_id


def text_parts(value):
    if isinstance(value, str):
        if value.strip() and not value.startswith("data:image/"):
            yield value.strip()
    elif isinstance(value, list):
        for item in value:
            yield from text_parts(item)
    elif isinstance(value, dict):
        if value.get("type") in {"image_body", "header", "footer", "page_number"}:
            return
        for key in ("content", "text", "blocks", "children", "lines", "spans", "items"):
            if key in value:
                yield from text_parts(value[key])


def read_mineru(paths, total_pages, printed):
    pages = {}
    engines = set()
    for path in paths:
        source = json.loads(path.read_text(encoding="utf-8-sig"))
        if source.get("schema") != "docvortex.middle":
            raise ValueError(f"需要 MinerU 4.x Middle JSON：{path}")
        producer = source.get("metadata", {}).get("producer", {})
        settings = source.get("extensions", {}).get("mineru", {})
        version = producer.get("version")
        if not version or str(settings.get("parse_mode", "")).lower() != "ocr":
            raise ValueError(f"导出件未标为 MinerU OCR，或缺少版本：{path}")
        engines.add(f"MinerU {version} / {settings.get('tier', 'unknown')} / OCR")
        for page in source["pages"]:
            index = page["page_idx"]
            if type(index) is not int or not 0 <= index < total_pages:
                raise ValueError(f"无效的原始 PDF 页索引：{index!r}")
            physical = index + 1
            if physical in pages:
                raise ValueError(f"多个导出件包含同一 PDF 物理页：{physical}")
            blocks = []
            for block in page["blocks"]:
                content = " ".join(text_parts(block)).strip()
                if content:
                    blocks.append(content)
            pages[physical] = {"pdf_page": physical, "printed_page": printed.get(str(physical)),
                               "text": "\n\n".join(blocks)}
    if not pages or len(engines) != 1 or not any(page["text"] for page in pages.values()):
        raise ValueError("没有可入库的 OCR 正文，或导出件使用了不同的 OCR 配置")
    return pages, engines.pop()


def atomic_text(path, writer, compressed=False):
    with NamedTemporaryFile(dir=path.parent, prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
        temp = Path(stream.name)
    try:
        if compressed:
            with temp.open("wb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as zipped:
                with io.TextIOWrapper(zipped, encoding="utf-8", newline="\n") as output:
                    writer(output)
        else:
            with temp.open("w", encoding="utf-8", newline="\n") as output:
                writer(output)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def pack(args):
    raw_labels = json.loads(args.page_labels.read_text(encoding="utf-8-sig")) if args.page_labels else {}
    if not isinstance(raw_labels, dict) or any(
        not key.isascii() or not key.isdigit() or str(int(key)) != key
        or not 1 <= int(key) <= args.pdf_pages
        or not isinstance(value, str) or not value.strip() for key, value in raw_labels.items()
    ):
        raise ValueError("页码文件应是以 PDF 物理页为键、印刷页码字符串为值的 JSON 对象")

    pages, engine = read_mineru(args.middle_json, args.pdf_pages, raw_labels)
    output = args.output
    name = f"{args.id}.jsonl.gz"
    book = {"id": args.id, "title": args.title, "edition": args.edition,
            "source_sha256": args.source_sha256, "pdf_pages": args.pdf_pages, "pages_file": name,
            "ocr_engine": engine}
    catalog = output / "manifest.json"
    payload = output / name
    sources = {*args.middle_json, args.page_labels} - {None}
    if {path.resolve() for path in sources} & {catalog.resolve(), payload.resolve()}:
        raise ValueError("索引输出和源文件必须使用不同路径")
    books = load_books(output)
    if any(key.casefold() == args.id.casefold() and key != args.id for key in books):
        raise ValueError("已有书目编号只允许使用原始大小写")
    old = books.get(args.id)
    if old and any(old[key] != book[key] for key in ("source_sha256", "pdf_pages", "ocr_engine")):
        raise ValueError("该书编号已有不同的原件或 OCR 配置，请使用不同目录或编号")
    if old is None and payload.exists():
        raise ValueError("同名正文缺少可核验书目，请选择其他目录或编号")
    if old:
        existing, _ = pages_and_coverage(output, old)
        for physical, entry in existing.items():
            if physical in pages and str(physical) not in raw_labels:
                pages[physical]["printed_page"] = entry["printed_page"]
            entry["printed_page"] = raw_labels.get(str(physical), entry["printed_page"])
            pages.setdefault(physical, entry)

    def write_pages(stream):
        for number in sorted(pages):
            stream.write(json.dumps(pages[number], ensure_ascii=False) + "\n")

    output.mkdir(parents=True, exist_ok=True)
    atomic_text(payload, write_pages, compressed=True)
    books[args.id] = book
    manifest = {"schema_version": 1, "books": [books[key] for key in sorted(books)]}
    atomic_text(catalog, lambda stream: json.dump(manifest, stream, ensure_ascii=False, indent=2))
    print(json.dumps({"id": args.id, "exported_pages": len(pages), "pdf_pages": args.pdf_pages,
                      "pages_with_text": sum(bool(row["text"]) for row in pages.values()),
                      "printed_page_labels": sum(row["printed_page"] is not None for row in pages.values())},
                     ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--edition", required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--pdf-pages", required=True, type=int)
    parser.add_argument("--page-labels", type=Path)
    parser.add_argument("--output", required=True, type=Path, help="本地索引目录")
    parser.add_argument("middle_json", nargs="+", type=Path)
    args = parser.parse_args()
    if (
        not valid_book_id(args.id) or not DIGEST.fullmatch(args.source_sha256)
        or args.pdf_pages < 1 or not args.title.strip() or not args.edition.strip()
    ):
        parser.error("文档编号、标题、版次、原件 SHA-256 或 PDF 页数无效")
    try:
        pack(args)
    except (OSError, EOFError, AttributeError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
