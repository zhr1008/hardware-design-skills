#!/usr/bin/env python3
"""Create, validate, update, and invalidate pcba-program-state-v1 files."""

from __future__ import annotations

import argparse
import datetime as dt
from decimal import InvalidOperation
import hashlib
import json
from pathlib import Path
import subprocess
import sys


STAGES = (
    "product_definition", "sourcing", "circuit", "schematic_visual",
    "placement", "routing", "manufacturing_release", "assembly_placement",
    "order",
)
STATUSES = {"PASS", "BLOCKED", "USER_REVIEW"}
APPROVALS = ("design_critical_substitution", "assembly_placement", "final_price", "payment")
RELEASE_EVIDENCE_ROLES = ("release_manifest", "cpl")
DECISION_CLI = Path(__file__).absolute().parents[2] / "hardware/scripts/design_flow.py"
ENGINEERING_STAGES = {"product_definition", "sourcing", "circuit", "placement", "routing", "manufacturing_release"}
CHECK_STAGES = {
    "commercial-fit": ("sourcing", "order"),
    "component-qualification": ("sourcing", "manufacturing_release"),
    "firmware-interface": ("circuit", "manufacturing_release"),
    "layout-coverage": ("routing", "manufacturing_release"),
    "return-path": ("routing", "manufacturing_release"),
    "analog-drive": ("circuit", "manufacturing_release"),
    "edge-termination": ("circuit", "routing", "manufacturing_release"),
    "emc-current-path": ("circuit", "routing", "manufacturing_release"),
    "assembly": ("manufacturing_release",),
    "factory-capability": ("manufacturing_release",),
    "production-evidence": ("manufacturing_release",),
    "thermal": ("placement", "manufacturing_release"),
    "release-identity": ("manufacturing_release",),
}
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


def decision_result(*args):
    result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(DECISION_CLI), *map(str, args)],
                            encoding="utf-8", capture_output=True, timeout=60, check=False)
    if result.returncode:
        raise ValueError(result.stdout.strip() or result.stderr.strip() or "engineering evidence not covered")
    return json.loads(result.stdout)


def evidence_root(state_dir: Path) -> Path:
    return state_dir.parent if state_dir.name == ".pcba-workflow" else state_dir


def case_record(path: Path, state_dir: Path, stage: str, project: str, release=None, *, require_contract=False) -> dict:
    root = evidence_root(state_dir)
    path = path.resolve(strict=True)
    if not path.is_relative_to(root):
        raise ValueError("engineering case must be inside the project evidence root")
    before = path.read_bytes()
    target = "fabrication" if stage == "manufacturing_release" else "handoff"
    options = ("--require-system-contract",) if require_contract else ()
    verdict = decision_result("assess", "--target", target, "--case", path, "--root", root, *options)
    after = path.read_bytes()
    if before != after or verdict["baseline"]["project"] != project:
        raise ValueError("engineering case changed or points to another project")
    if release is not None:
        manifest = release["release_manifest"]
        case = json.loads(after.decode("utf-8-sig"))
        covered = case["checks"]["release-identity"]["artifacts"]
        subjects = {
            ((root / item["path"]).resolve(), item["sha256"].lower())
            for item in (case["artifacts"][key] for key in covered)
        }
        matched = all(((state_dir / rec["path"]).resolve(), rec["sha256"].lower()) in subjects
                      for rec in release.values())
        if verdict["baseline"]["revision"] != manifest["revision"] or not matched:
            raise ValueError("engineering case does not bind the current release and CPL")
    return {"path": str(path.relative_to(root)), "sha256": hashlib.sha256(after).hexdigest(),
            "target": target, "baseline": verdict["baseline"],
            **({"require_system_contract": True} if require_contract else {})}


def propagate_invalidation(state, affected, design_critical):
    for stage in affected:
        state["stages"][stage] = {"status": "BLOCKED", "evidence": []}
    approvals = []
    if "assembly_placement" in affected:
        approvals.append("assembly_placement")
    if "order" in affected:
        approvals.extend(("final_price", "payment"))
    if design_critical:
        approvals.append("design_critical_substitution")
    for approval in approvals:
        state["approvals"][approval] = "PENDING"
        state["approval_evidence"][approval] = []


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


def validate(state: dict, state_dir: Path, verified_records: dict | None = None,
             verified_case_stage=None) -> list[str]:
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
        record = stages.get(stage, {}).get("engineering_case")
        if stage in ENGINEERING_STAGES and status == "PASS" and state.get("formal_engineering") and record is None:
            errors.append(f"{stage}: requires a formal engineering case")
        if record is not None and stage != verified_case_stage:
            try:
                root = evidence_root(state_dir)
                bound_release = ({key: state["artifacts"][key] for key in RELEASE_EVIDENCE_ROLES}
                                 if stage == "manufacturing_release" else None)
                actual = case_record(root / record["path"], state_dir, stage, state["project_id"], bound_release,
                                     require_contract=record.get("require_system_contract") is True)
                if actual != record:
                    errors.append(f"{stage}: engineering case no longer matches its record")
            except (ValueError, TypeError, KeyError, OSError, subprocess.TimeoutExpired) as exc:
                errors.append(f"{stage}: invalid engineering case: {exc}")
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
    init_p.add_argument("--formal-engineering", action="store_true", help="Require covered case evidence for engineering PASS transitions.")
    set_p = sub.add_parser("set-stage")
    set_p.add_argument("--stage", choices=STAGES, required=True)
    set_p.add_argument("--status", choices=sorted(STATUSES), required=True)
    set_p.add_argument("--evidence", action="append", default=[])
    set_p.add_argument("--engineering-case", type=Path, help="Recheck the case for this stage before recording PASS.")
    set_p.add_argument("--require-system-contract", action="store_true",
                       help="Require the engineering case to bind a valid system contract.")
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
    impact_p = sub.add_parser("invalidate-impact")
    impact_p.add_argument("--case", type=Path, required=True)
    impact_p.add_argument("--change-file", type=Path, required=True)
    impact_p.add_argument("--reason", required=True)
    sub.add_parser("validate")
    args = parser.parse_args()
    state_dir = args.file.parent.resolve()
    verified_records = None
    verified_case_stage = None

    if args.command == "init":
        if args.file.exists():
            raise SystemExit(f"refusing to overwrite existing state: {args.file}")
        state = initial(args.project)
        if args.formal_engineering:
            state["formal_engineering"] = True
    else:
        state = load(args.file)
        if args.command == "set-stage":
            if args.require_system_contract and not args.engineering_case:
                raise SystemExit("--require-system-contract requires --engineering-case")
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
            if args.engineering_case:
                if args.status != "PASS" or args.stage not in ENGINEERING_STAGES:
                    raise SystemExit("--engineering-case applies to engineering PASS transitions")
                try:
                    state["stages"][args.stage]["engineering_case"] = case_record(
                        args.engineering_case, state_dir, args.stage, state["project_id"], verified_records,
                        require_contract=args.require_system_contract)
                    verified_case_stage = args.stage
                except (ValueError, KeyError, OSError, subprocess.TimeoutExpired) as exc:
                    raise SystemExit(str(exc)) from exc
        elif args.command == "set-approval":
            if args.status in {"APPROVED", "REJECTED"} and not has_evidence(args.evidence):
                raise SystemExit("an approval decision requires nonempty --evidence text entries")
            if args.approval == "assembly_placement" and args.status == "APPROVED" and browser_edits_pending(state):
                raise SystemExit("assembly placement cannot be approved with manual browser edits")
            state["approvals"][args.approval] = args.status
            state["approval_evidence"][args.approval] = args.evidence
        elif args.command == "invalidate":
            affected = INVALIDATION[args.change]
            propagate_invalidation(state, affected, args.change in {
                "product-definition", "netlist", "circuit", "mpn-package", "bom"})
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
        elif args.command == "invalidate-impact":
            try:
                root = evidence_root(state_dir)
                inputs = [path.resolve(strict=True) for path in (args.case, args.change_file)]
                if any(not path.is_relative_to(root) for path in inputs):
                    raise ValueError("impact inputs must be inside the project evidence root")
                impact = decision_result("impact", "--case", inputs[0], "--change", inputs[1], "--root", root)
                baseline = impact["baseline"]
                stored = [data["engineering_case"]["baseline"] for data in state["stages"].values()
                          if data.get("engineering_case")]
                if baseline["project"] != state["project_id"] or baseline not in stored:
                    raise ValueError("impact does not match a recorded engineering baseline")
                rows = [row for row in impact["recheck"] if row["variant"] in (baseline["variant"], "*")]
                affected = set(stage for row in rows for stage in CHECK_STAGES.get(row["check"], ("circuit",)))
                for stage in STAGES:
                    if any(dep in affected for dep in STAGE_PREREQUISITES.get(stage, ())):
                        affected.add(stage)
                if "manufacturing_release" in affected:
                    affected.add("assembly_placement")
                    affected.add("order")
                propagate_invalidation(state, affected, any(row["check"] in {
                    "component-qualification", "rating-limits", "fault-propagation"} for row in rows))
                state["invalidation_log"].append({
                    "time_utc": now(), "change": "engineering-impact", "reason": args.reason,
                    "affected_stages": [stage for stage in STAGES if stage in affected], "impact": rows,
                })
            except (ValueError, KeyError, OSError, subprocess.TimeoutExpired) as exc:
                raise SystemExit(str(exc)) from exc

    errors = validate(state, state_dir, verified_records, verified_case_stage)
    if not errors and args.command != "validate":
        save(args.file, state)
    print(json.dumps({
        "status": "PASS" if not errors else "BLOCKED", "scope": "program_state",
        "file": str(args.file), "manual_browser_edits_present": browser_edits_pending(state), "errors": errors,
    }, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
