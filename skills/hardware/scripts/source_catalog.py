"""Look up versioned bibliography entries without opening source PDFs or a private library."""

import json
from pathlib import Path
import unicodedata


def normalized(value):
    return unicodedata.normalize("NFKC", value).casefold()


def search_sources(terms, limit):
    folder = Path(__file__).resolve().parents[1] / "assets/review-knowledge"
    rules = json.loads((folder / "rules.json").read_text(encoding="utf-8-sig"))
    handbook = json.loads((folder / "lifecycle-sources.json").read_text(encoding="utf-8-sig"))
    wanted = [normalized(term.strip()) for term in terms]
    if not all(wanted):
        raise ValueError("来源检索词不能为空")
    records = []
    for category, entries in (
        ("rule_source", rules["sources"].items()),
        ("handbook", handbook["sources"].items()),
        ("manufacturing_revision", ((r["identity"], r) for r in handbook["manufacturing_revisions"])),
    ):
        for identity, record in entries:
            content = normalized(identity + " " + json.dumps(record, ensure_ascii=False))
            if all(term in content for term in wanted):
                records.append({"catalog": category, "id": identity, "record": record})
    records.sort(key=lambda r: normalized(r["id"]) not in wanted)
    return {"count": len(records), "results": records[:limit]}
