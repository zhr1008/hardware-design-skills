"""检索指定目录内的逐页 OCR 索引。"""

import argparse
import gzip
import json
from pathlib import Path, PureWindowsPath
import re
import unicodedata


BOOK_ID = re.compile(r"[A-Za-z0-9_-]+", re.ASCII)
DIGEST = re.compile(r"[a-f0-9]{64}", re.ASCII)
OCR_NOTE = "公式、单位及图表以相同版次的原页为准。"


def valid_book_id(value):
    return (
        isinstance(value, str) and BOOK_ID.fullmatch(value) is not None
        and not PureWindowsPath(f"{value}.jsonl.gz").is_reserved()
    )


def load_books(directory):
    manifest = directory / "manifest.json"
    if not manifest.exists():
        return {}
    with manifest.open(encoding="utf-8-sig") as stream:
        catalogue = json.load(stream)
    if (
        not isinstance(catalogue, dict) or type(catalogue.get("schema_version")) is not int
        or catalogue["schema_version"] != 1 or not isinstance(catalogue.get("books"), list)
    ):
        raise ValueError("书籍数据格式不受支持")
    books = {}
    seen_ids = set()
    for book in catalogue["books"]:
        if not isinstance(book, dict):
            raise ValueError("索引中的书目须为对象")
        book_id = book.get("id")
        if (
            not valid_book_id(book_id) or book_id.casefold() in seen_ids
            or book.get("pages_file") != f"{book_id}.jsonl.gz"
        ):
            raise ValueError(f"书籍编号重复或正文文件名无效：{book_id}")
        if (
            type(book.get("pdf_pages")) is not int or book["pdf_pages"] < 1
            or not all(isinstance(book.get(field), str) and book[field].strip()
                       for field in ("title", "edition", "ocr_engine", "source_sha256"))
            or DIGEST.fullmatch(book["source_sha256"]) is None
        ):
            raise ValueError(f"书目元数据无效：{book_id}")
        seen_ids.add(book_id.casefold())
        books[book_id] = book
    return books


def pages_and_coverage(directory, book):
    path = directory / book["pages_file"]
    coverage = {
        "status": "payload_missing",
        "pdf_pages": book["pdf_pages"],
        "pages_recorded": 0,
        "pages_with_text": 0,
        "pages_with_printed_number": 0,
    }
    if not path.exists():
        return {}, coverage
    pages = {}
    with gzip.open(path, mode="rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            page = row["pdf_page"]
            if type(page) is not int or not 1 <= page <= book["pdf_pages"] or page in pages:
                raise ValueError(f'{book["id"]} 的 PDF 页码无效或重复：{page}')
            if not isinstance(row["text"], str) or (
                row["printed_page"] is not None and not isinstance(row["printed_page"], str)
            ):
                raise ValueError(f'{book["id"]} 的第 {page} 页字段无效')
            pages[page] = {field: row[field] for field in ("pdf_page", "printed_page", "text")}
    coverage.update(
        status="complete" if len(pages) == book["pdf_pages"] else "partial",
        pages_recorded=len(pages),
        pages_with_text=sum(bool(row["text"].strip()) for row in pages.values()),
        pages_with_printed_number=sum(bool(row["printed_page"]) for row in pages.values()),
    )
    return pages, coverage


def compact(value):
    return " ".join(unicodedata.normalize("NFKC", value).split())


def search(pages, terms, limit):
    matches = []
    for page in sorted(pages):
        row = pages[page]
        text = compact(row["text"])
        positions = [text.casefold().find(term) for term in terms]
        if min(positions) < 0:
            continue
        # Pick a bounded excerpt around the search term with the most characters.
        anchor = positions[max(range(len(terms)), key=lambda i: len(terms[i]))]
        start = max(0, anchor - 80)
        matches.append({
            "pdf_page": page,
            "printed_page": row["printed_page"],
            "snippet": text[start:start + 360],
        })
        if len(matches) == limit:
            break
    return matches


def show(result, status=0):
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--library", required=True, type=Path, help="用户提供的 OCR 索引目录")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="列出该目录的书目和 OCR 覆盖", allow_abbrev=False)
    query = sub.add_parser("search", help="按书检索同一页中的关键词", allow_abbrev=False)
    query.add_argument("--book", required=True)
    query.add_argument("terms", nargs="+")
    query.add_argument("--limit", type=int, default=8, choices=range(1, 31), metavar="1..30")
    read = sub.add_parser("read", help="读取一页 OCR 原始文字", allow_abbrev=False)
    read.add_argument("book")
    read.add_argument("pdf_page", type=int, help="PDF 物理页，从 1 开始")
    args = parser.parse_args()

    try:
        books = load_books(args.library)
        if args.command == "status":
            present = (args.library / "manifest.json").is_file()
            return show({
                "manifest_present": present,
                "books": [
                    {**book, "coverage": pages_and_coverage(args.library, book)[1]}
                    for book in books.values()
                ],
            }, status=0 if present else 1)
        book = books.get(args.book)
        if book is None:
            return show({"error": "索引目录缺少指定书目", "id": args.book}, status=1)
        pages, coverage = pages_and_coverage(args.library, book)
        result = {"book": book, "coverage": coverage, "note": OCR_NOTE}
        if args.command == "search":
            terms = [compact(term).casefold() for term in args.terms]
            if not all(terms):
                parser.error("检索词不能为空")
            result["results"] = search(pages, terms, args.limit)
            return show(result, status=1 if coverage["status"] == "payload_missing" else 0)
        if not 1 <= args.pdf_page <= book["pdf_pages"]:
            parser.error("PDF 物理页超出范围")
        row = pages.get(args.pdf_page)
        result["page"] = row
        if row is None:
            result["error"] = "数据包缺少此 PDF 物理页。"
        return show(result, status=1 if row is None else 0)
    except (OSError, EOFError, KeyError, TypeError, ValueError) as error:
        return show({"error": f"无法读取 OCR 数据：{error}"}, status=1)


if __name__ == "__main__":
    raise SystemExit(main())
