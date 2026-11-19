#!/usr/bin/env python3
"""Validate contract, revision consistency, and hashes for a PCBA release."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import stat
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from check_assembly import check as check_assembly, parse_refs


APPROVALS = (
    "design_critical_substitution", "assembly_placement", "final_price", "payment",
)
REQUIRED_ARTIFACTS = {
    "board_source", "eda_project", "gerber", "drill", "bom", "cpl",
    "constraints", "render_top", "render_bottom", "circuit_review",
    "schematic_connectivity", "schematic_visual_audit", "layout_review",
    "sourcing_lock",
}
REQUIRED_CONSTRAINTS = {
    "board_width_mm", "board_height_mm", "layer_count", "thickness_mm",
    "surface_finish", "assembly_sides", "quantity_pcbs", "quantity_assembled",
}
ZERO_VERIFICATIONS = {
    "unexplained_raw_disconnects", "real_drc_errors", "layout_check_failures",
}
PASS_VERIFICATIONS = {
    "circuit_gate", "layout_gate", "raw_connectivity", "power_connectivity",
    "visual_mechanical_review", "dfm_review", "sourcing_lock_current",
    "revision_reconciled",
}
ASSEMBLY_CHECK_KEY = "assembly_check"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def passlike(value: object) -> bool:
    return value is True or (isinstance(value, str) and value.strip().upper() == "PASS")


def zero(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        return False
    try:
        return Decimal(str(value)).is_zero()
    except InvalidOperation:
        return False


def positive_number(value: object) -> bool:
    if isinstance(value, bool):
        return False
    try:
        number = float(value)
        return math.isfinite(number) and number > 0
    except (TypeError, ValueError, OverflowError):
        return False


def positive_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def valid_assembly_sides(value: object) -> bool:
    if isinstance(value, str):
        items = [item.strip().title() for item in value.replace("+", ",").replace(";", ",").split(",") if item.strip()]
    elif isinstance(value, list):
        items = [str(item).strip().title() for item in value if str(item).strip()]
    else:
        return False
    return bool(items) and set(items) <= {"Top", "Bottom"}


def contract_object(data: dict, name: str, errors: list[str]) -> dict:
    value = data.get(name, {})
    if isinstance(value, dict):
        return value
    errors.append(f"{name} must be an object")
    return {}


def contract_errors(data: dict) -> list[str]:
    errors: list[str] = []
    if data.get("schema") != "pcba-release-manifest-v1":
        errors.append("invalid schema")
    revision = data.get("revision")
    if not isinstance(revision, str) or not revision.strip():
        errors.append("revision must be nonempty text")
    status = data.get("status")
    if not isinstance(status, str) or status not in {"PASS", "BLOCKED", "USER_REVIEW"}:
        errors.append("invalid release status")

    artifacts = contract_object(data, "artifacts", errors)
    for role, item in artifacts.items():
        if not isinstance(item, dict):
            errors.append(f"{role}: artifact entry must be an object")
        elif item.get("revision") != revision:
            errors.append(f"{role}: mixed revision {item.get('revision')!r}")

    approvals = contract_object(data, "approvals", errors)
    approval_evidence = contract_object(data, "approval_evidence", errors)
    for name in APPROVALS:
        decision = approvals.get(name)
        if not isinstance(decision, str) or decision not in {"PENDING", "APPROVED", "REJECTED"}:
            errors.append(f"approval {name}: invalid status")
        elif decision in {"APPROVED", "REJECTED"}:
            evidence = approval_evidence.get(name)
            if not isinstance(evidence, list) or not evidence or not all(
                isinstance(item, str) and item.strip() for item in evidence
            ):
                errors.append(f"approval {name}: decision requires nonempty evidence text entries")

    constraints = contract_object(data, "constraints", errors)
    verification = contract_object(data, "verification", errors)
    if status == "PASS":
        missing_artifacts = sorted(REQUIRED_ARTIFACTS - set(artifacts))
        if missing_artifacts:
            errors.append(f"PASS missing artifact roles: {missing_artifacts}")
        missing_constraints = sorted(REQUIRED_CONSTRAINTS - set(constraints))
        if missing_constraints:
            errors.append(f"PASS missing constraints: {missing_constraints}")
        for name in ("board_width_mm", "board_height_mm", "thickness_mm"):
            if not positive_number(constraints.get(name)):
                errors.append(f"PASS requires positive finite {name}")
        for name in ("layer_count", "quantity_pcbs", "quantity_assembled"):
            if not positive_integer(constraints.get(name)):
                errors.append(f"PASS requires positive integer {name}")
        if (positive_integer(constraints.get("quantity_pcbs")) and
                positive_integer(constraints.get("quantity_assembled")) and
                constraints["quantity_assembled"] > constraints["quantity_pcbs"]):
            errors.append("quantity_assembled may not exceed quantity_pcbs")
        finish = constraints.get("surface_finish")
        if (not isinstance(finish, str) or not finish.strip() or
                finish.strip().lower() in {"none", "tbd", "unknown"}):
            errors.append("PASS requires nonempty surface_finish")
        if not valid_assembly_sides(constraints.get("assembly_sides")):
            errors.append("PASS assembly_sides must contain Top and/or Bottom")
        for name in sorted(ZERO_VERIFICATIONS):
            if not zero(verification.get(name)):
                errors.append(f"PASS requires {name}=0")
        for name in sorted(PASS_VERIFICATIONS):
            if not passlike(verification.get(name)):
                errors.append(f"PASS requires {name}=PASS")
        substitution_required = verification.get("design_critical_substitution_required")
        if not isinstance(substitution_required, bool):
            errors.append("PASS requires boolean design_critical_substitution_required")
        elif substitution_required and approvals.get("design_critical_substitution") != "APPROVED":
            errors.append("required design-critical substitution is not approved")
    return errors


def confined_artifact(root: Path, relative: Path) -> Path:
    if relative.anchor or ".." in relative.parts:
        raise ValueError("expected a package-relative path inside the manifest directory")
    path = root
    for part in relative.parts:
        if os.name == "nt" and (part.endswith((" ", ".")) or ":" in part):
            raise ValueError("ambiguous Windows path component")
        path /= part
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or (
            getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise ValueError("package artifact paths cannot contain symbolic links or reparse points")
    return path


def unique_json_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate manifest key: {key!r}")
        result[key] = value
    return result


def read_manifest(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    return parse_manifest(raw), hashlib.sha256(raw).hexdigest().upper()


def parse_manifest(raw: bytes) -> dict:
    data = json.loads(raw.decode("utf-8-sig"), parse_float=Decimal, object_pairs_hook=unique_json_object)
    if not isinstance(data, dict):
        raise ValueError("manifest must be a JSON object")
    return data


def assembly_check_record(artifacts: dict, paths: dict[str, Path], exclusions: set[str]) -> dict:
    try:
        if paths["bom"].samefile(paths["cpl"]):
            raise ValueError("BOM and CPL must be distinct files")
        result = check_assembly(paths["bom"], paths["cpl"], exclusions)
    except (OSError, ValueError, csv.Error) as exc:
        raise ValueError(f"BOM/CPL reconciliation requires supported same-revision CSV files: {exc}") from exc
    hashes = {role: value.upper() for role, value in result["sha256"].items()}
    if any(hashes[role] != artifacts[role].get("sha256") for role in hashes):
        raise ValueError("BOM/CPL SHA-256 changed between artifact verification and assembly check")
    if result["status"] != "matched":
        raise ValueError(f"BOM/CPL reconciliation failed: {json.dumps(result['issues'], ensure_ascii=False)}")
    return {"status": result["status"], "sha256": hashes, "explicit_exclusions": sorted(exclusions)}


def assembly_exclusions(record: object, artifacts: dict) -> set[str]:
    if (not isinstance(record, dict) or record.get("status") != "matched"
            or record.get("sha256") != {role: artifacts[role]["sha256"] for role in ("bom", "cpl")}):
        raise ValueError("assembly_check must record a match bound to the listed BOM/CPL SHA-256")
    references = record.get("explicit_exclusions")
    if not isinstance(references, list) or not all(isinstance(ref, str) for ref in references):
        raise ValueError("assembly_check explicit_exclusions must be a list of BOM reference designators")
    return {ref for item in references for ref in parse_refs(item, grouped=False)}


def manifest_errors(data: dict, root: Path, *, confine: bool = False) -> list[str]:
    return contract_errors(data) + package_errors(data, root, confine=confine)


def package_errors(data: dict, root: Path, *, confine: bool = False) -> list[str]:
    errors = []
    artifacts = data.get("artifacts") if isinstance(data.get("artifacts"), dict) else {}
    verified_paths = {}
    for role, item in artifacts.items():
        if not isinstance(item, dict):
            continue
        value = item.get("path")
        if not isinstance(value, str) or not value:
            errors.append(f"{role}: missing artifact path")
            continue
        relative = Path(value)
        try:
            path = confined_artifact(root, relative) if confine else (root / relative).resolve()
            if not path.is_file():
                errors.append(f"{role}: missing file {path}")
                continue
            actual = sha256(path)
            size = path.stat().st_size
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(f"{role}: artifact could not be read: {exc}")
            continue
        if actual != item.get("sha256"):
            errors.append(f"{role}: SHA-256 mismatch")
        if type(item.get("size_bytes")) is not int or size != item["size_bytes"]:
            errors.append(f"{role}: size mismatch")
        elif actual == item.get("sha256"):
            verified_paths[role] = path
    if data.get("status") != "PASS":
        errors.append(f"manifest status is {data.get('status')!r}, not PASS")
    elif {"bom", "cpl"} <= verified_paths.keys():
        verification = data.get("verification")
        try:
            exclusions = set()
            if isinstance(verification, dict) and ASSEMBLY_CHECK_KEY in verification:
                exclusions = assembly_exclusions(verification[ASSEMBLY_CHECK_KEY], artifacts)
            assembly_check_record(artifacts, verified_paths, exclusions)
        except ValueError as exc:
            errors.append(str(exc))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--formal", action="store_true", help="emit a versioned evidence envelope")
    parser.add_argument(
        "--confine-to-manifest-dir", action="store_true",
        help="Artifacts must use package-relative paths that stay inside the manifest directory.",
    )
    args = parser.parse_args()
    digest = None
    missing = False
    identity = {}
    try:
        raw = args.manifest.read_bytes()
        digest = hashlib.sha256(raw).hexdigest() if args.formal else None
        data = parse_manifest(raw)
        identity = {key: data[key] for key in ("release", "revision")
                    if isinstance(data.get(key), str) and data[key].strip()}
        structural = contract_errors(data)
        errors = structural + package_errors(data, args.manifest.parent.resolve(), confine=args.confine_to_manifest_dir)
        invalid = bool(structural)
        artifacts = data.get("artifacts") if isinstance(data.get("artifacts"), dict) else {}
        result = {
            "status": "PASS" if not errors else "BLOCKED",
            "manifest_status": data.get("status") if isinstance(data.get("status"), str) else None,
            "artifacts": len(artifacts),
            "errors": errors,
        }
    except (OSError, ValueError, InvalidOperation) as exc:
        result = {"status": "BLOCKED", "manifest_status": None, "artifacts": 0, "errors": [str(exc)]}
        invalid = True
        missing = isinstance(exc, FileNotFoundError)
    output = result
    if args.formal:
        sys.path.insert(0, str(Path(__file__).absolute().parents[2] / "hardware/scripts"))
        from evidence_adapter import saved_release

        output = saved_release(result, args.manifest, digest, identity=identity, invalid=invalid, missing=missing)
    print(json.dumps(output, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
