#!/usr/bin/env python3
"""Create, validate, update, and invalidate pcba-program-state-v1 files."""

from __future__ import annotations

import argparse
import datetime as dt
from decimal import InvalidOperation
import json
from pathlib import Path
import sys


STAGES = (
    "product_definition", "sourcing", "circuit", "schematic_visual",
    "placement", "routing", "manufacturing_release", "assembly_placement",
    "order",
)
STATUSES = {"PASS", "BLOCKED", "USER_REVIEW"}
APPROVALS = ("design_critical_substitution", "assembly_placement", "final_price", "payment")
RELEASE_EVIDENCE_ROLES = ("release_manifest", "cpl")
INVALIDATION = {
    "product-definition": STAGES,
    "netlist": STAGES[2:],
    "circuit": STAGES[2:],
    "mpn-package": STAGES[1:],
    "footprint": STAGES[4:],
    "placement": STAGES[4:],
    "routing": STAGES[5:],
    "bom": ("sourcing", "manufacturing_release", "assembly_placement", "order"),
    "cpl": ("manufacturing_release", "assembly_placement", "order"),
    "browser-placement": ("manufacturing_release", "assembly_placement", "order"),
    "stock-price": ("sourcing", "order"),
}

STAGE_PREREQUISITES = {
    "sourcing": ("product_definition",),
    "circuit": ("product_definition",),
    "placement": ("circuit", "schematic_visual"),
    "routing": ("placement",),
    "manufacturing_release": ("circuit", "schematic_visual", "placement", "routing"),
    "assembly_placement": ("manufacturing_release",),
    "order": STAGES[:-1],
}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def initial(project_id: str) -> dict:
    return {
        "schema": "pcba-program-state-v1",
        "project_id": project_id,
        "updated_at": now(),
        "stages": {stage: {"status": "BLOCKED", "evidence": []} for stage in STAGES},
        "artifacts": {},
        "risks": [],
        "approvals": {
            "design_critical_substitution": "PENDING",
            "assembly_placement": "PENDING",
            "final_price": "PENDING",
            "payment": "PENDING",
        },
        "approval_evidence": {name: [] for name in APPROVALS},
        "manual_browser_edits_present": False,
        "invalidation_log": [],
    }


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path: Path, state: dict) -> None:
    state["updated_at"] = now()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def has_evidence(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and item.strip() for item in value
    )


def last_browser_edit(state: dict) -> dict:
    return next((entry for entry in reversed(state.get("invalidation_log", []))
                 if entry.get("change") == "browser-placement"), {})


def valid_sha256(digest: object) -> bool:
    return isinstance(digest, str) and len(digest) == 64 and all(char in "0123456789ABCDEF" for char in digest)


def changed_release(previous: object, current: object) -> bool:
    return isinstance(previous, dict) and isinstance(current, dict) and all(
        valid_sha256(previous.get(role)) and valid_sha256(current.get(role)) and previous[role] != current[role]
        for role in RELEASE_EVIDENCE_ROLES
    )


def browser_edits_pending(state: dict) -> bool:
    edit = last_browser_edit(state)
    return bool(state.get("manual_browser_edits_present") or (
        edit and not changed_release(edit.get("previous_release"), edit.get("regenerated_release"))
    ))


def verified_release(manifest: Path, state_dir: Path) -> dict:
    release_scripts = Path(__file__).resolve().parents[2] / "release-pcba-fabrication" / "scripts"
    if not (release_scripts / "validate_release_manifest.py").is_file():
        raise ValueError("release-pcba-fabrication validator is required to verify the manufacturing release")
    if str(release_scripts) not in sys.path:
        sys.path.insert(0, str(release_scripts))
    try:
        from validate_release_manifest import manifest_errors, read_manifest

        manifest = manifest.resolve()
        data, digest = read_manifest(manifest)
        errors = manifest_errors(data, manifest.parent)
    except (ImportError, OSError, RuntimeError, ValueError, InvalidOperation) as exc:
        raise ValueError(f"cannot verify release manifest {manifest}: {exc}") from exc
    if errors:
        raise ValueError(f"manufacturing release manifest {manifest}: " + "; ".join(errors))
    cpl = data["artifacts"]["cpl"]
    return {
        role: {
            "path": str(path.relative_to(state_dir)) if path.is_relative_to(state_dir) else str(path),
            "revision": data["revision"],
            "sha256": sha256,
        }
        for role, path, sha256 in (
            ("release_manifest", manifest, digest),
            ("cpl", (manifest.parent / cpl["path"]).resolve(), cpl["sha256"]),
        )
    }


def release_hashes(artifacts: dict) -> dict:
    result = {}
    for role in RELEASE_EVIDENCE_ROLES:
        record = artifacts.get(role)
        digest = record.get("sha256") if isinstance(record, dict) else None
        if valid_sha256(digest):
            result[role] = digest
    return result


def record_release(state: dict, manifest: Path, previous: Path | None, state_dir: Path) -> dict:
    records = verified_release(manifest, state_dir)
    hashes = release_hashes(records)
    prior_hashes = release_hashes(state["artifacts"])
    if state["stages"]["manufacturing_release"]["status"] == "PASS" and hashes != prior_hashes:
        raise ValueError("invalidate the previous release before recording a different or previously unbound manifest")
    if browser_edits_pending(state):
        edit = last_browser_edit(state)
        baseline = edit.get("previous_release", {})
        if not isinstance(baseline, dict):
            baseline = {}
        if previous is not None:
            supplied = release_hashes(verified_release(previous, state_dir))
            if any(supplied.get(role) != digest for role, digest in baseline.items()):
                raise ValueError("--previous-release-manifest differs from the release recorded before browser edits")
            baseline = supplied
        if not all(valid_sha256(baseline.get(role)) for role in RELEASE_EVIDENCE_ROLES):
            raise ValueError("missing pre-edit release hashes; supply the original frozen package with --previous-release-manifest")
        unchanged = [role for role, digest in hashes.items() if baseline[role] == digest]
        if unchanged:
            raise ValueError(f"browser edits require regenerated release artifacts with new SHA-256: {', '.join(unchanged)}")
        if state["stages"]["assembly_placement"]["status"] != "BLOCKED" or state["stages"]["order"]["status"] != "BLOCKED":
            raise ValueError("invalidate CPL before recording browser recovery so assembly and order can be reviewed again")
        if edit:
            edit["previous_release"] = baseline
            edit["regenerated_release"] = hashes
        state["manual_browser_edits_present"] = False
    elif previous is not None:
        raise ValueError("--previous-release-manifest is only used when browser edits are pending")
    state["artifacts"].update(records)
    return records


def validate(state: dict, state_dir: Path, verified_records: dict | None = None) -> list[str]:
    errors: list[str] = []
    if state.get("schema") != "pcba-program-state-v1":
        errors.append("schema must be pcba-program-state-v1")
    if not state.get("project_id"):
        errors.append("project_id is required")
    stages = state.get("stages", {})
    if set(stages) != set(STAGES):
        errors.append("stage set does not match pcba-program-state-v1")
    for stage in STAGES:
        if stages.get(stage, {}).get("status") not in STATUSES:
            errors.append(f"{stage}: invalid status")
        status = stages.get(stage, {}).get("status")
        if status in {"PASS", "USER_REVIEW"} and not has_evidence(stages.get(stage, {}).get("evidence")):
            errors.append(f"{stage}: {status} requires nonempty evidence text entries")
        if status in {"PASS", "USER_REVIEW"}:
            missing = [name for name in STAGE_PREREQUISITES.get(stage, ())
                       if stages.get(name, {}).get("status") != "PASS"]
            if missing:
                errors.append(f"{stage}: prerequisites are not PASS: {missing}")
    approvals = state.get("approvals", {})
    for name in APPROVALS:
        if approvals.get(name) not in {"PENDING", "APPROVED", "REJECTED"}:
            errors.append(f"approval {name}: invalid status")
        if approvals.get(name) in {"APPROVED", "REJECTED"} and not has_evidence(state.get("approval_evidence", {}).get(name)):
            errors.append(f"approval {name}: decision requires nonempty evidence text entries")
    if browser_edits_pending(state):
        if stages.get("manufacturing_release", {}).get("status") == "PASS":
            errors.append("manufacturing_release cannot PASS until browser placement edits are reconciled")
        if stages.get("assembly_placement", {}).get("status") in {"PASS", "USER_REVIEW"}:
            errors.append("assembly_placement requires a regenerated release after browser edits")
    if stages.get("manufacturing_release", {}).get("status") == "PASS":
        artifacts = state.get("artifacts", {})
        manifest = artifacts.get("release_manifest", {})
        path = manifest.get("path") if isinstance(manifest, dict) else None
        if not isinstance(path, str) or not path.strip():
            errors.append("manufacturing_release PASS requires a verified --release-manifest and CPL")
        else:
            try:
                records = verified_records if verified_records is not None else verified_release(state_dir / path, state_dir)
                if any(artifacts.get(role) != record for role, record in records.items()):
                    errors.append("manufacturing_release manifest or CPL differs from the recorded path, revision or SHA-256")
            except ValueError as exc:
                errors.append(str(exc))
    if stages.get("assembly_placement", {}).get("status") == "PASS" and approvals.get("assembly_placement") != "APPROVED":
        errors.append("assembly_placement PASS requires its independent approval")
    if stages.get("order", {}).get("status") == "PASS":
        missing = [name for name in APPROVALS if approvals.get(name) != "APPROVED"]
        if missing:
            errors.append(f"order PASS requires all independent approvals: {missing}")
    if approvals.get("assembly_placement") == "APPROVED" and stages.get("assembly_placement", {}).get("status") not in {"USER_REVIEW", "PASS"}:
        errors.append("assembly placement approval requires completed evidence at USER_REVIEW or PASS")
    if approvals.get("final_price") == "APPROVED":
        if stages.get("assembly_placement", {}).get("status") != "PASS":
            errors.append("final price approval requires PASS assembly placement")
        if stages.get("order", {}).get("status") not in {"USER_REVIEW", "PASS"}:
            errors.append("final price approval requires an order stage at USER_REVIEW or PASS")
    if approvals.get("payment") == "APPROVED":
        missing_prior = [name for name in APPROVALS[:-1] if approvals.get(name) != "APPROVED"]
        if missing_prior:
            errors.append(f"payment approval requires all prior approvals: {missing_prior}")
        if stages.get("order", {}).get("status") not in {"USER_REVIEW", "PASS"}:
            errors.append("payment approval requires an order stage at USER_REVIEW or PASS")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, default=Path(".pcba-workflow/program-state.json"))
    sub = parser.add_subparsers(dest="command", required=True)
    init_p = sub.add_parser("init")
    init_p.add_argument("--project", required=True)
    set_p = sub.add_parser("set-stage")
    set_p.add_argument("--stage", choices=STAGES, required=True)
    set_p.add_argument("--status", choices=sorted(STATUSES), required=True)
    set_p.add_argument("--evidence", action="append", default=[])
    set_p.add_argument("--release-manifest", type=Path, help="Verified PASS manifest for the manufacturing release stage.")
    set_p.add_argument("--previous-release-manifest", type=Path,
                       help="Original frozen manifest for browser recovery when an older state lacks the pre-edit hashes.")
    approval_p = sub.add_parser("set-approval")
    approval_p.add_argument("--approval", choices=APPROVALS, required=True)
    approval_p.add_argument("--status", choices=("PENDING", "APPROVED", "REJECTED"), required=True)
    approval_p.add_argument("--evidence", action="append", default=[])
    inv_p = sub.add_parser("invalidate")
    inv_p.add_argument("--change", choices=sorted(INVALIDATION), required=True)
    inv_p.add_argument("--reason", required=True)
    sub.add_parser("validate")
    args = parser.parse_args()
    state_dir = args.file.parent.resolve()
    verified_records = None

    if args.command == "init":
        if args.file.exists():
            raise SystemExit(f"refusing to overwrite existing state: {args.file}")
        state = initial(args.project)
    else:
        state = load(args.file)
        if args.command == "set-stage":
            if args.status in {"PASS", "USER_REVIEW"} and not has_evidence(args.evidence):
                raise SystemExit(f"{args.status} requires nonempty --evidence text entries")
            if args.stage == "placement" and args.status in {"PASS", "USER_REVIEW"} and state["stages"]["sourcing"]["status"] != "PASS":
                raise SystemExit("placement freeze requires sourcing PASS at the transition")
            if args.stage == "manufacturing_release" and args.status == "PASS":
                if args.release_manifest is None:
                    raise SystemExit("manufacturing_release PASS requires --release-manifest")
                try:
                    verified_records = record_release(state, args.release_manifest, args.previous_release_manifest, state_dir)
                except ValueError as exc:
                    raise SystemExit(str(exc)) from exc
            elif args.release_manifest is not None or args.previous_release_manifest is not None:
                raise SystemExit("release manifest arguments apply to manufacturing_release PASS")
            state["stages"][args.stage] = {"status": args.status, "evidence": args.evidence}
        elif args.command == "set-approval":
            if args.status in {"APPROVED", "REJECTED"} and not has_evidence(args.evidence):
                raise SystemExit("an approval decision requires nonempty --evidence text entries")
            if args.approval == "assembly_placement" and args.status == "APPROVED" and browser_edits_pending(state):
                raise SystemExit("assembly placement cannot be approved with manual browser edits")
            state["approvals"][args.approval] = args.status
            state["approval_evidence"][args.approval] = args.evidence
        elif args.command == "invalidate":
            affected = INVALIDATION[args.change]
            for stage in affected:
                state["stages"][stage]["status"] = "BLOCKED"
                state["stages"][stage]["evidence"] = []
            if "assembly_placement" in affected:
                state["approvals"]["assembly_placement"] = "PENDING"
                state["approval_evidence"]["assembly_placement"] = []
            if "order" in affected:
                state["approvals"]["final_price"] = "PENDING"
                state["approvals"]["payment"] = "PENDING"
                state["approval_evidence"]["final_price"] = []
                state["approval_evidence"]["payment"] = []
            if args.change in {"product-definition", "netlist", "circuit", "mpn-package", "bom"}:
                state["approvals"]["design_critical_substitution"] = "PENDING"
                state["approval_evidence"]["design_critical_substitution"] = []
            entry = {
                "time_utc": now(), "change": args.change,
                "reason": args.reason, "affected_stages": list(affected),
            }
            if args.change == "browser-placement":
                entry["previous_release"] = (
                    last_browser_edit(state).get("previous_release", {}) if browser_edits_pending(state)
                    else release_hashes(state["artifacts"])
                )
            state["invalidation_log"].append(entry)
            state["manual_browser_edits_present"] = browser_edits_pending(state)

    errors = validate(state, state_dir, verified_records)
    if not errors and args.command != "validate":
        save(args.file, state)
    print(json.dumps({
        "status": "PASS" if not errors else "BLOCKED", "scope": "program_state",
        "file": str(args.file), "manual_browser_edits_present": browser_edits_pending(state), "errors": errors,
    }, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
