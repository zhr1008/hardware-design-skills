"""Cross-check saved BOM and pick-and-place CSVs before freezing a PCBA release."""

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sys


REFERENCE = re.compile(r"[A-Z][A-Z0-9_]*(?:[.-][A-Z0-9_]+)*", re.ASCII | re.IGNORECASE)
NUMBER = r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)"
COORDINATE = re.compile(rf"({NUMBER})\s*(mm|mil|in|inch)?", re.IGNORECASE)
ROTATION = re.compile(rf"{NUMBER}\s*(?:°|deg)?", re.IGNORECASE)
SIDE = {
    "top": "top", "front": "top", "fcu": "top", "t": "top",
    "bottom": "bottom", "back": "bottom", "bcu": "bottom", "b": "bottom",
}
ALIASES = {
    "reference": {"designator", "designators", "ref", "refs", "refdes", "reference", "references", "referencedesignator", "referencedesignators"},
    "dnp": {"dnp", "dnf", "donotpopulate", "donotfit"},
    "customer_supply": {"customersupply"},
    "x": {"midx", "posx", "x"},
    "y": {"midy", "posy", "y"},
    "side": {"layer", "side"},
    "rotation": {"rot", "rotation"},
}
TRUE_DNP = {"1", "true", "yes", "y", "dnp", "dnf", "do not populate", "do not fit"}
FALSE_DNP = {"", "0", "false", "no", "n"}


def header_key(value):
    return re.sub(r"[\s_.-]+", "", value.strip().lower())


def unit_key(value):
    unit = value.lower()
    return "in" if unit == "inch" else unit


def read_table(path, required, optional=()):
    with path.open("rb") as source:
        raw = source.read()
    reader = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    header = next(reader, None)
    if not header:
        raise ValueError(f"{path.name}: missing header")
    keys = [header_key(value) for value in header]
    units = {}
    positions = {}
    for field in (*required, *optional):
        matches = []
        for i, key in enumerate(keys):
            axis = re.fullmatch(r"(.+)\((mm|mil|in|inch)\)", key) if field in ("x", "y") else None
            if (axis[1] if axis else key) in ALIASES[field]:
                matches.append(i)
                if axis:
                    units[field] = unit_key(axis[2])
        if len(matches) > 1:
            raise ValueError(f"{path.name}: ambiguous {field} columns")
        if not matches and field in required:
            raise ValueError(f"{path.name}: missing {field} column")
        if matches:
            positions[field] = matches[0]
    rows = []
    for row in reader:
        if not any(cell.strip() for cell in row):
            continue
        line = reader.line_num
        if len(row) != len(header):
            raise ValueError(f"{path.name}:{line}: expected {len(header)} columns, found {len(row)}")
        rows.append((line, {field: row[index].strip() for field, index in positions.items()}))
    return rows, hashlib.sha256(raw).hexdigest(), units


def parse_refs(value, grouped):
    refs = re.split(r"[,;\s]+", value.strip()) if grouped else [value.strip()]
    for ref in refs:
        if (
            not REFERENCE.fullmatch(ref) or not any(c.isdigit() for c in ref)
            or re.search(r"[0-9]-[A-Za-z]*[0-9]", ref)
        ):
            raise ValueError("expected explicit reference designators such as R1, U2; expand ranges")
    return [ref.upper() for ref in refs]


def read_bom(rows, issue):
    count = Counter()
    dnp = set()
    for line, row in rows:
        try:
            refs = parse_refs(row["reference"], grouped=True)
        except ValueError as exc:
            issue("bom_invalid_reference", line=line, value=row["reference"], detail=str(exc))
            continue
        count.update(refs)
        flag = row.get("dnp", "").casefold()
        supply_dnp = row.get("customer_supply", "").casefold() == "dnp"
        if flag in TRUE_DNP or supply_dnp:
            dnp.update(refs)
        if flag not in TRUE_DNP | FALSE_DNP:
            issue("bom_ambiguous_dnp", line=line, references=refs, value=row["dnp"])
        elif supply_dnp and flag and flag in FALSE_DNP:
            issue("bom_conflicting_dnp", line=line, references=refs, value=row["dnp"])
    return count, dnp


def read_cpl(rows, header_units, issue):
    count = Counter()
    sides = Counter()
    units = set()
    for line, row in rows:
        try:
            ref, = parse_refs(row["reference"], grouped=False)
        except ValueError as exc:
            issue("cpl_invalid_reference", line=line, value=row["reference"], detail=str(exc))
            continue
        count[ref] += 1
        side = SIDE.get(header_key(row["side"]))
        if side is None:
            issue("cpl_invalid_side", line=line, reference=ref, value=row["side"])
        else:
            sides[side] += 1
        if not ROTATION.fullmatch(row["rotation"]):
            issue("cpl_invalid_rotation", line=line, reference=ref, value=row["rotation"])
        row_units = set()
        for axis in ("x", "y"):
            match = COORDINATE.fullmatch(row[axis])
            if match is None:
                issue("cpl_invalid_coordinate", line=line, reference=ref, axis=axis, value=row[axis])
                continue
            declared = header_units.get(axis)
            explicit = unit_key(match[2]) if match[2] else None
            if declared and explicit and declared != explicit:
                issue("cpl_coordinate_unit_conflict", line=line, reference=ref, axis=axis,
                      header_unit=declared, cell_unit=explicit)
            row_units.add(explicit or declared or "unspecified")
        if len(row_units) > 1:
            issue("cpl_coordinate_unit_mismatch", line=line, reference=ref, units=sorted(row_units))
        units.update(row_units)
    return count, sides, units


def check(bom, cpl, exclusions):
    bom_rows, bom_hash, _ = read_table(bom, ("reference",), ("dnp", "customer_supply"))
    cpl_rows, cpl_hash, header_units = read_table(cpl, ("reference", "x", "y", "side", "rotation"))
    issues = []

    def issue(code, **context):
        issues.append({"code": code, **context})

    bom_refs, dnp = read_bom(bom_rows, issue)
    cpl_refs, sides, units = read_cpl(cpl_rows, header_units, issue)
    skipped = dnp | exclusions
    expected = set(bom_refs) - skipped
    placed = set(cpl_refs)
    if not bom_refs:
        issue("bom_no_references")
    if not expected:
        issue("bom_no_placement_targets")
    for name, refs in (("bom", bom_refs), ("cpl", cpl_refs)):
        duplicates = {ref: refs[ref] for ref in sorted(refs) if refs[ref] > 1}
        if duplicates:
            issue(f"{name}_duplicate_references", counts=duplicates)
    if len(units - {"unspecified"}) > 1:
        issue("cpl_mixed_coordinate_units", units=sorted(units))
    for code, refs in (
        ("exclusion_not_in_bom", skipped - set(bom_refs)),
        ("bom_missing_from_cpl", expected - placed),
        ("cpl_missing_from_bom", placed - set(bom_refs)),
        ("cpl_places_excluded_reference", placed & skipped),
    ):
        if refs:
            issue(code, references=sorted(refs))
    return {
        "status": "issues_found" if issues else "matched",
        "sha256": {"bom": bom_hash, "cpl": cpl_hash},
        "bom_reference_count": len(bom_refs),
        "cpl_reference_count": len(cpl_refs),
        "matched_reference_count": len(expected & placed),
        "excluded_references": sorted(skipped),
        "cpl_side_counts": dict(sorted(sides.items())),
        "cpl_coordinate_units": sorted(units),
        "issues": issues,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("bom", type=Path, help="UTF-8 comma-delimited BOM CSV")
    parser.add_argument("--cpl", required=True, type=Path, help="UTF-8 comma-delimited CPL CSV")
    parser.add_argument("--exclude", action="append", default=[], help="explicit BOM refs omitted from placement (repeatable)")
    parser.add_argument("--format", choices=("json", "text"), default="json")
    args = parser.parse_args(argv)
    try:
        exclusions = {ref for group in args.exclude for ref in parse_refs(group, grouped=True)}
        if args.bom.samefile(args.cpl):
            raise ValueError("BOM and CPL must be distinct files")
        result = check(args.bom, args.cpl, exclusions)
    except (OSError, ValueError, csv.Error) as exc:
        report = {"status": "invalid_input", "error": str(exc)}
        print(json.dumps(report, ensure_ascii=False) if args.format == "json" else report["error"], file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f'{result["status"]}: {result["matched_reference_count"]} matched references')
        for item in result["issues"]:
            print(json.dumps(item, ensure_ascii=False))
    return 1 if result["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
