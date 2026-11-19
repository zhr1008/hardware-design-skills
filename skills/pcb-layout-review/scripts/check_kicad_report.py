"""Summarize saved KiCad 9/10 ERC or DRC JSON without starting KiCad."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys


SCHEMAS = {f"https://schemas.kicad.org/{kind}.v1.json": kind for kind in ("erc", "drc")}
SEVERITIES = {"error", "warning", "exclusion"}


def unique_mapping(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON member: {key}")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError(f"invalid JSON number: {value}")


def require_list(data, field, where):
    value = data.get(field)
    if not isinstance(value, list):
        raise ValueError(f"{where}.{field} must be an array")
    return value


def report_groups(report, kind):
    if kind == "drc":
        for key in ("violations", "unconnected_items", "schematic_parity"):
            yield key, require_list(report, key, "report")
        return
    for i, sheet in enumerate(require_list(report, "sheets", "report")):
        where = f"sheets[{i}]"
        if not isinstance(sheet, dict) or not isinstance(sheet.get("path"), str):
            raise ValueError(f"{where} must be an object with a sheet path")
        yield where, require_list(sheet, "violations", where)


def reported_ignored_checks(report):
    if "ignored_checks" not in report:
        return None
    checks = require_list(report, "ignored_checks", "report")
    for check in checks:
        if not isinstance(check, dict) or any(
            not isinstance(check.get(field), str) or not check[field].strip()
            for field in ("key", "description")
        ):
            raise ValueError("each ignored check must have a rule key and description")
    return [{"key": check["key"], "description": check["description"]} for check in checks]


def check(path, expected_kind):
    return check_bytes(path.read_bytes(), expected_kind)


def check_bytes(raw, expected_kind):
    report = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_mapping, parse_constant=reject_constant)
    if not isinstance(report, dict):
        raise ValueError("report must be a JSON object")
    schema = report.get("$schema")
    kind = SCHEMAS.get(schema) if isinstance(schema, str) else None
    if kind is None or (expected_kind is not None and kind != expected_kind):
        raise ValueError("expected a matching KiCad ERC/DRC v1 JSON report")
    version = report.get("kicad_version")
    if not isinstance(version, str) or not re.fullmatch(r"(?:9|10)(?:\.[0-9]+){0,2}", version):
        raise ValueError("only KiCad 9.x and 10.x stable report versions are supported")
    for field in ("source", "date"):
        if not isinstance(report.get(field), str) or not report[field].strip():
            raise ValueError(f"report.{field} must be non-empty text")
    selected = report.get("included_severities", [])
    if not isinstance(selected, list) or any(not isinstance(value, str) or value not in SEVERITIES for value in selected):
        raise ValueError("included_severities must contain only error, warning or exclusion")
    ignored = reported_ignored_checks(report)

    totals = Counter(error=0, warning=0, excluded=0)
    rules = {}
    group_totals = {}
    group_labels = {}
    for group, violations in report_groups(report, kind):
        counts = Counter(error=0, warning=0, excluded=0)
        for index, item in enumerate(violations):
            if (
                not isinstance(item, dict) or not isinstance(item.get("type"), str)
                or not item["type"].strip() or item.get("severity") not in ("error", "warning")
                or not isinstance(item.get("excluded", False), bool)
            ):
                raise ValueError(f"{group}[{index}] must contain a rule type, severity and optional boolean excluded")
            bucket = "excluded" if item.get("excluded", False) else item["severity"]
            counts[bucket] += 1
            rules.setdefault(item["type"], Counter(error=0, warning=0, excluded=0))[bucket] += 1
        totals.update(counts)
        group_totals[group] = dict(counts)
    if kind == "erc":
        for group, sheet in zip(group_totals, report["sheets"]):
            group_labels[group] = sheet["path"]

    missing = SEVERITIES - set(selected)
    if kind == "erc" and not group_totals:
        raise ValueError("ERC report contains no sheet evidence")
    status = "no_reported_findings"
    if missing:
        status = "coverage_incomplete"
    elif ignored or any(totals.values()):
        status = "review_required"
    return {
        "status": status,
        "kind": kind,
        "kicad_version": version,
        "source": report["source"],
        "report_date": report["date"],
        "sha256": hashlib.sha256(raw).hexdigest(),
        "included_severities": sorted(set(selected)),
        "missing_severities": sorted(missing),
        "ignored_checks": ignored,
        "counts": dict(totals),
        "groups": group_totals,
        "group_sheet_paths": group_labels,
        "rules": {key: dict(rules[key]) for key in sorted(rules)},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("report", type=Path, help="existing ERC or DRC JSON report")
    parser.add_argument("--kind", choices=("erc", "drc"), help="require a report of this kind")
    parser.add_argument("--formal", action="store_true", help="emit a versioned evidence envelope")
    args = parser.parse_args(argv)
    missing = False
    raw = None
    try:
        raw = args.report.read_bytes()
        result = check_bytes(raw, args.kind)
    except (OSError, ValueError) as exc:
        result = {"status": "invalid_input", "error": str(exc)}
        missing = isinstance(exc, FileNotFoundError)
    output = result
    stream = sys.stderr if result["status"] == "invalid_input" and not args.formal else sys.stdout
    if args.formal:
        sys.path.insert(0, str(Path(__file__).absolute().parents[2] / "hardware/scripts"))
        from evidence_adapter import saved_kicad

        digest = hashlib.sha256(raw).hexdigest() if raw is not None else None
        output = saved_kicad(result, args.report, digest, missing=missing)
    print(json.dumps(output, ensure_ascii=False, indent=2), file=stream)
    return {"no_reported_findings": 0, "review_required": 1, "coverage_incomplete": 2,
            "invalid_input": 2}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
