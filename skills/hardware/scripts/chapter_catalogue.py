"""Resolve original chapter headings to PDF physical pages."""

from functools import lru_cache
import json
from pathlib import Path


CATALOGUE = Path("assets/engineering-library/chapters.json")


@lru_cache(maxsize=4)
def load(root):
    path = root / CATALOGUE
    if not path.is_file():
        return {}
    result = json.loads(path.read_text(encoding="utf-8"))
    if result["schema_version"] != 1:
        raise ValueError("不支持该章节索引版本")
    return result["documents"]


def chapters(root, document):
    item = load(root).get(document["id"])
    if item is None:
        return []
    if (item["source_sha256"] != document.get("source_sha256")
            or item["pdf_pages"] != document.get("pdf_pages")):
        raise ValueError(f"章节索引与当前原件版本不一致：{document['id']}")
    return item["sections"]


def locate(root, document, pdf_page):
    if pdf_page is None:
        return None
    present = [
        section for section in chapters(root, document)
        if section["start_pdf_page"] <= pdf_page <= section["end_pdf_page"]
    ]
    return max(present, key=lambda section: (section["level"], section["start_pdf_page"]), default=None)
