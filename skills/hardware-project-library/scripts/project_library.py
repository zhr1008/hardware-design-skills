#!/usr/bin/env python3
"""Private, explicit-file engineering evidence index. No network or code execution."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path, PureWindowsPath

SCHEMA = "hardware-project-record-v1"
DIMENSIONS = ("schematic", "component_selection", "pcb_drc", "simulation", "firmware_build", "bringup", "production")
STATUSES = {"PASS", "FAIL", "UNKNOWN", "NOT_TESTED", "NOT_APPLICABLE"}
ROLES = {"schematic", "pcb", "bom", "firmware", "library", "mechanical", "test", "datasheet", "documentation", "license", "manufacturing"}
CLASSIFICATIONS = {"observed", "project_rule", "reuse_candidate", "hypothesis"}


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def identifier(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,95}", value):
        raise ValueError("id must be 1-96 letters/digits/dot/underscore/hyphen, starting with a letter or digit")
    return value


def linked_path(path: Path) -> bool:
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def selected_file(root: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("file path must be a nonempty relative path")
    path = Path(relative)
    if path.is_absolute() or PureWindowsPath(relative).drive or ".." in path.parts:
        raise ValueError(f"file path must stay inside source_root: {relative}")
    candidate = root / path
    for part in [candidate, *candidate.parents]:
        if part == root:
            break
        if linked_path(part):
            raise ValueError(f"linked file or directory is not accepted: {relative}")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError(f"not a regular file within source_root: {relative}")
    return resolved


def validate_spec(spec: object) -> dict:
    if not isinstance(spec, dict):
        raise ValueError("spec must be an object")
    identifier(spec.get("id"))
    for field in ("title", "revision", "source_root"):
        if not isinstance(spec.get(field), str) or not spec[field].strip():
            raise ValueError(f"{field} is required")
    if spec.get("visibility", "private") != "private":
        raise ValueError("this tool only creates private records; publication is a separate workflow")
    source = spec.get("source")
    if not isinstance(source, dict) or source.get("kind") not in {"company", "vendor", "open_hardware", "project"}:
        raise ValueError("source.kind must be company/vendor/open_hardware/project")
    if not isinstance(source.get("usage_basis"), str) or not source["usage_basis"].strip():
        raise ValueError("source.usage_basis must describe the actual permission or project context")
    if source["kind"] in {"vendor", "open_hardware"}:
        locator = source.get("locator")
        if not isinstance(locator, str) or not locator.startswith("https://"):
            raise ValueError("public sources require an exact HTTPS source.locator")
    if not isinstance(spec.get("conditions", {}), dict):
        raise ValueError("conditions must be an object")
    if not isinstance(spec.get("tags", []), list) or any(not isinstance(t, str) for t in spec.get("tags", [])):
        raise ValueError("tags must be a list of strings")
    files = spec.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("select at least one actual source/evidence file")
    ids = set()
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("files entries must be objects")
        fid = identifier(item.get("id"))
        if fid in ids:
            raise ValueError(f"duplicate file id: {fid}")
        ids.add(fid)
        if item.get("role") not in ROLES:
            raise ValueError(f"unsupported role for {fid}")
    evidence = spec.get("evidence", {})
    if not isinstance(evidence, dict) or set(evidence) - set(DIMENSIONS):
        raise ValueError("evidence has unsupported dimensions")
    for name, entry in evidence.items():
        if not isinstance(entry, dict) or entry.get("status") not in STATUSES:
            raise ValueError(f"invalid evidence status: {name}")
        refs = entry.get("file_ids", [])
        if not isinstance(refs, list) or any(not isinstance(r, str) or r not in ids for r in refs):
            raise ValueError(f"unknown evidence file reference: {name}")
        if entry["status"] in {"PASS", "FAIL"} and not refs:
            raise ValueError(f"{name}: PASS/FAIL requires a source file, not a label alone")
        if entry["status"] == "NOT_APPLICABLE" and not entry.get("note"):
            raise ValueError(f"{name}: NOT_APPLICABLE requires a reason")
    claims = spec.get("claims", [])
    if not isinstance(claims, list):
        raise ValueError("claims must be a list")
    for claim in claims:
        if not isinstance(claim, dict) or not isinstance(claim.get("statement"), str) or not claim["statement"].strip():
            raise ValueError("claim.statement is required")
        if claim.get("classification") not in CLASSIFICATIONS:
            raise ValueError("claim classification must retain fact/rule/candidate/hypothesis distinction")
        refs = claim.get("file_ids", [])
        if not isinstance(refs, list) or any(not isinstance(r, str) or r not in ids for r in refs):
            raise ValueError("claim contains an unknown file reference")
        if claim["classification"] != "hypothesis" and not refs:
            raise ValueError("observations, rules and reusable candidates need source evidence")
        if not claim.get("applies_when") or not claim.get("limitations"):
            raise ValueError("claims require applies_when and limitations")
    if spec.get("supersedes") is not None:
        identifier(spec["supersedes"])
        if spec["supersedes"] == spec["id"]:
            raise ValueError("a record cannot supersede itself")
    return spec


def register(library: Path, spec: dict) -> Path:
    validate_spec(spec)
    root = Path(spec["source_root"]).expanduser()
    if not root.is_absolute():
        raise ValueError("source_root must be an explicit absolute path")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("source_root is not a directory")
    record = json.loads(json.dumps(spec))
    record.update(schema=SCHEMA, visibility="private", source_root=str(root),
                  captured_at=dt.datetime.now(dt.timezone.utc).isoformat())
    paths = set()
    for item in record["files"]:
        path = selected_file(root, item["path"])
        if path in paths:
            raise ValueError("the same file may only be registered once per record")
        paths.add(path)
        item.update(path=path.relative_to(root).as_posix(), size_bytes=path.stat().st_size, sha256=file_hash(path))
    for dimension in DIMENSIONS:
        record.setdefault("evidence", {}).setdefault(dimension, {"status": "NOT_TESTED", "file_ids": [], "note": "No evidence recorded"})
    record["record_sha256"] = hashlib.sha256(canonical(record)).hexdigest()
    target = library / "records" / (identifier(record["id"]) + ".json")
    if target.exists():
        raise ValueError(f"record exists; use a new revision/id: {record['id']}")
    if record.get("supersedes"):
        read_record(library, record["supersedes"])
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    return target


def read_record(library: Path, record_id: str) -> dict:
    path = library / "records" / (identifier(record_id) + ".json")
    record = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(record, dict) or record.get("schema") != SCHEMA or record.get("id") != record_id:
        raise ValueError("record schema or identity mismatch")
    checksum = record.get("record_sha256")
    payload = {k: v for k, v in record.items() if k != "record_sha256"}
    if checksum != hashlib.sha256(canonical(payload)).hexdigest():
        raise ValueError("record checksum mismatch; do not silently rewrite historical evidence")
    validate_spec(record)
    return record


def verify(library: Path, record_id: str) -> dict:
    record = read_record(library, record_id)
    root = Path(record["source_root"]).resolve()
    findings = []
    for item in record["files"]:
        try:
            path = selected_file(root, item["path"])
            if file_hash(path) != item["sha256"] or path.stat().st_size != item["size_bytes"]:
                findings.append({"file_id": item["id"], "issue": "content_changed"})
        except (OSError, ValueError) as exc:
            findings.append({"file_id": item["id"], "issue": "unavailable_or_invalid", "detail": str(exc)})
    failures = [name for name, evidence in record["evidence"].items() if evidence["status"] == "FAIL"]
    return {"id": record_id, "integrity_ok": not findings, "findings": findings,
            "declared_failures": failures, "evidence_status": {k: v["status"] for k, v in record["evidence"].items()},
            "engineering_validation": "not_performed_by_indexer"}


def search(library: Path, query: str, limit: int = 20) -> dict:
    terms = query.casefold().split()
    matches, invalid = [], []
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    for path in sorted((library / "records").glob("*.json")):
        try:
            record = read_record(library, path.stem)
            haystack = json.dumps({k: record.get(k) for k in ("id", "title", "tags", "conditions", "claims")}, ensure_ascii=False).casefold()
            if all(term in haystack for term in terms):
                matches.append({"id": record["id"], "title": record["title"], "revision": record["revision"],
                                "visibility": record["visibility"], "supersedes": record.get("supersedes"),
                                "evidence_status": {k: v["status"] for k, v in record["evidence"].items()}})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            invalid.append({"id": path.stem, "error": str(exc)})
    return {"query": query, "matches": matches[:limit], "total_matches": len(matches), "invalid_records": invalid,
            "order": "record_id; no maturity ranking", "source_integrity": "run verify before reuse"}


def template() -> dict:
    return {"id": "project-revision-module", "title": "", "revision": "", "visibility": "private",
            "source_root": "", "source": {"kind": "company", "locator": None, "usage_basis": ""},
            "tags": [], "conditions": {}, "files": [],
            "evidence": {k: {"status": "NOT_TESTED", "file_ids": [], "conditions": {}, "note": ""} for k in DIMENSIONS},
            "claims": [], "supersedes": None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("template"); p.add_argument("--out", type=Path, required=True)
    for command in ("register", "search", "inspect", "verify"):
        p = sub.add_parser(command); p.add_argument("--library", type=Path, required=True)
        if command == "register": p.add_argument("--spec", type=Path, required=True)
        elif command == "search":
            p.add_argument("--query", default=""); p.add_argument("--limit", type=int, default=20)
        else: p.add_argument("--id", required=True)
    for command in ("module-search", "module-fit"):
        p = sub.add_parser(command)
        p.add_argument("--library", type=Path, required=True, help="explicit module root")
        p.add_argument("--conditions", type=Path, help="JSON request with conditions, interfaces, and changes")
        if command == "module-search":
            p.add_argument("--query", default="")
            p.add_argument("--limit", type=int, default=5)
        else:
            p.add_argument("--manifest", type=Path, required=True, help="module.json under the module root")
            p.add_argument("--manifest-sha256", help="expected hash of a previously identified manifest")
    args = parser.parse_args()
    try:
        if args.command == "template":
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(template(), ensure_ascii=False, indent=2) + "\n")
            result = {"created": str(args.out), "requires_actual_project_evidence": True}
        elif args.command == "register":
            spec = json.loads(args.spec.read_text(encoding="utf-8-sig"))
            result = {"record": str(register(args.library, spec)), "engineering_validation": "not_performed_by_indexer"}
        elif args.command in ("module-search", "module-fit"):
            from module_pack import module_fit, module_search, read_json

            request = read_json(args.conditions.read_bytes()) if args.conditions else {}
            if args.command == "module-search":
                result = module_search(args.library, args.query, request, args.limit)
            else:
                result = module_fit(args.library, args.manifest, request, args.manifest_sha256)
        elif args.command == "search": result = search(args.library, args.query, args.limit)
        elif args.command == "inspect": result = read_record(args.library, args.id)
        else: result = verify(args.library, args.id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if (result.get("integrity_ok") is False or result.get("invalid_records")
                     or result.get("invalid_modules") or result.get("status") == "blocked") else 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc), "operation": args.command}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
