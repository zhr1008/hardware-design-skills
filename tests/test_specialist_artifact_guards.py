"""Exercise offline catalog, selection, and manufacturing artifact boundaries."""

import csv
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest


SKILLS = Path(__file__).resolve().parents[1] / "skills"
RELEASE_SCRIPTS = SKILLS / "release-pcba-fabrication" / "scripts"
PROGRAM_STATE = SKILLS / "manage-pcba-program" / "scripts" / "program_state.py"
BOM_ARCHIVE = SKILLS / "bom-material-archive" / "scripts" / "bom_archive.py"
SELECTION_EXPORT = SKILLS / "component-sourcing" / "scripts" / "render_ad_selection.py"
VALID_BOM = b"Designator,DNP\nR1,false\nR2,true\n"
VALID_CPL = b"Designator,Mid X (mm),Mid Y (mm),Layer,Rotation\nR1,1,2,Top,0\n"


def run_cli(script, *arguments):
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(script), *(str(arg) for arg in arguments)],
        capture_output=True, text=True, encoding="utf-8", check=False,
    )


def artifact_record(root, role, content, revision="A"):
    extension = "csv" if role in ("bom", "cpl") else "dat"
    artifact = root / f"{role}.{extension}"
    artifact.write_bytes(content)
    return {"path": artifact.name, "revision": revision, "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest().upper()}


def release_fixture(root, *, cpl=VALID_CPL):
    root.mkdir(parents=True, exist_ok=True)
    contents = {"bom": VALID_BOM, "cpl": cpl}
    artifacts = {}
    for role in (
        "board_source", "eda_project", "gerber", "drill", "bom", "cpl", "constraints",
        "render_top", "render_bottom", "circuit_review", "schematic_connectivity",
        "schematic_visual_audit", "layout_review", "sourcing_lock",
    ):
        artifacts[role] = artifact_record(root, role, contents.get(role, f"fixture: {role}".encode()))
    return {
        "schema": "pcba-release-manifest-v1", "revision": "A", "status": "PASS", "artifacts": artifacts,
        "constraints": {"board_width_mm": 12, "board_height_mm": 18, "layer_count": 2, "thickness_mm": 1.6,
                        "surface_finish": "ENIG", "assembly_sides": ["Top"], "quantity_pcbs": 5, "quantity_assembled": 4},
        "verification": {"unexplained_raw_disconnects": "0", "real_drc_errors": 0,
                         "layout_check_failures": 0.0, "circuit_gate": "PASS", "layout_gate": "PASS",
                         "raw_connectivity": "PASS", "power_connectivity": "PASS",
                         "visual_mechanical_review": "PASS", "dfm_review": "PASS",
                         "sourcing_lock_current": "PASS", "revision_reconciled": "PASS",
                         "design_critical_substitution_required": False},
        "approvals": {"design_critical_substitution": "PENDING", "assembly_placement": "PENDING",
                      "final_price": "PENDING", "payment": "PENDING"},
    }


class ReleaseGuard(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.manifest = self.root / "manifest.json"
        self.data = release_fixture(self.root)
        self.artifacts = self.data["artifacts"]

    def build(self, *flags):
        arguments = ["--output", self.manifest, "--release", "fixture", "--revision", "A", "--status", "PASS"]
        for role, artifact in self.artifacts.items():
            arguments.extend(("--artifact", f"{role}={self.root / artifact['path']}", "--artifact-revision", f"{role}=A"))
        for key, value in self.data["constraints"].items():
            arguments.extend(("--constraint", f"{key}={','.join(value) if isinstance(value, list) else value}"))
        for key, value in self.data["verification"].items():
            arguments.extend(("--verification", f"{key}={value}"))
        return run_cli(RELEASE_SCRIPTS / "build_release_manifest.py", *arguments, *flags)

    def validate(self, raw_count="0", *, confined=True):
        data = {**self.data, "verification": {**self.data["verification"], "real_drc_errors": "DRC_VALUE"}}
        self.manifest.write_text(json.dumps(data).replace('"DRC_VALUE"', raw_count), encoding="utf-8")
        flags = ["--confine-to-manifest-dir"] if confined else []
        return run_cli(RELEASE_SCRIPTS / "validate_release_manifest.py", self.manifest, *flags)

    def test_bom_cpl_conflict_blocks_builder_and_legacy_manifest(self):
        self.artifacts["cpl"] = artifact_record(self.root, "cpl", VALID_CPL + b"R2,3,4,Top,0\n")
        built = self.build()
        self.assertNotEqual(built.returncode, 0)
        self.assertIn("cpl_places_excluded_reference", built.stderr)
        self.assertFalse(self.manifest.exists())
        legacy = self.validate()
        self.assertEqual(legacy.returncode, 1)
        self.assertIn("cpl_places_excluded_reference", " ".join(json.loads(legacy.stdout)["errors"]))

    def test_kibot_compatible_fixture_freezes_actual_output_bytes(self):
        bom = b"References,Status\nR1,DNC\nR2,DNF\nC1,\n"
        cpl = b"Ref,PosX,PosY,Rot,Side\nR1,1mm,2mm,0,top\nC1,3mm,4mm,90,bottom\n"
        self.artifacts["bom"] = artifact_record(self.root, "bom", bom)
        self.artifacts["cpl"] = artifact_record(self.root, "cpl", cpl)
        self.data["constraints"]["assembly_sides"] = ["Top", "Bottom"]
        built = self.build("--exclude", "R2")
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        result = run_cli(RELEASE_SCRIPTS / "validate_release_manifest.py", self.manifest,
                         "--confine-to-manifest-dir", "--formal")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (self.root / "cpl.csv").write_bytes(cpl.replace(b",90,", b",91,"))
        changed = run_cli(RELEASE_SCRIPTS / "validate_release_manifest.py", self.manifest,
                          "--confine-to-manifest-dir", "--formal")
        self.assertNotEqual(changed.returncode, 0, changed.stdout)

    def test_formal_release_records_artifact_hashes_for_downstream_recheck(self):
        checked = self.validate()
        self.assertEqual(checked.returncode, 0, checked.stderr)
        validator = RELEASE_SCRIPTS / "validate_release_manifest.py"
        formal = run_cli(validator, self.manifest, "--confine-to-manifest-dir", "--formal")
        self.assertEqual(formal.returncode, 0, formal.stderr)
        record = json.loads(formal.stdout)
        self.assertEqual(record["native"], json.loads(checked.stdout))
        self.assertEqual({role: item["sha256"] for role, item in record["inputs"].items() if role != "manifest"},
                         {f"package:{role}": item["sha256"].lower() for role, item in self.artifacts.items()})
        path = self.root / "release-evidence.json"
        path.write_text(formal.stdout, encoding="utf-8")
        adapter = SKILLS / "hardware/scripts/evidence_adapter.py"
        args = ("validate", path, "--verify-artifacts")
        self.assertEqual(run_cli(adapter, *args).returncode, 0)
        (self.root / self.artifacts["gerber"]["path"]).write_bytes(b"changed after validation")
        changed = run_cli(adapter, *args)
        self.assertEqual(changed.returncode, 2, changed.stderr)
        self.assertEqual([item["role"] for item in json.loads(changed.stdout)["artifacts"]
                          if item["status"] == "changed"], ["inputs.package:gerber"])

    def test_explicit_exclusion_is_bound_to_the_checked_pair(self):
        bom = VALID_BOM + b"TP1,false\n"
        self.artifacts["bom"] = artifact_record(self.root, "bom", bom)
        legacy = self.validate()
        self.assertIn("bom_missing_from_cpl", " ".join(json.loads(legacy.stdout)["errors"]))
        self.assertNotEqual(self.build("--exclude", "TP9").returncode, 0)
        built = self.build("--exclude", "tp1")
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        self.data = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.artifacts = self.data["artifacts"]
        self.assertEqual(self.data["verification"]["assembly_check"], {
            "status": "matched", "explicit_exclusions": ["TP1"],
            "sha256": {"bom": hashlib.sha256(bom).hexdigest().upper(),
                       "cpl": hashlib.sha256(VALID_CPL).hexdigest().upper()},
        })
        valid = self.validate()
        self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)

        # The new CPL is valid by itself. Replacing the artifact entry cannot
        # carry over the previously checked pair and its explicit exclusion.
        self.artifacts["cpl"] = artifact_record(self.root, "cpl", VALID_CPL.replace(b",1,2,", b",3,2,"))
        swapped = self.validate()
        self.assertEqual(swapped.returncode, 1)
        self.assertIn("bound to the listed BOM/CPL SHA-256", " ".join(json.loads(swapped.stdout)["errors"]))

    def test_drift_and_unsupported_legacy_artifact_are_blocked(self):
        (self.root / "bom.csv").write_bytes(VALID_BOM.replace(b"false", b"true"))
        drifted = self.validate()
        self.assertEqual(drifted.returncode, 1)
        self.assertIn("bom: SHA-256 mismatch", json.loads(drifted.stdout)["errors"])
        self.artifacts["bom"] = artifact_record(self.root, "bom", b"fixture: not BOM CSV\n")
        unsupported = self.validate()
        self.assertEqual(unsupported.returncode, 1)
        self.assertIn("requires supported same-revision CSV", " ".join(json.loads(unsupported.stdout)["errors"]))

    def test_only_exact_zero_passes(self):
        valid = self.validate()
        self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)
        self.assertEqual(json.loads(valid.stdout)["status"], "PASS")
        for raw_count in ("false", "1e-400", '"1e-400"'):
            with self.subTest(raw_count=raw_count):
                result = self.validate(raw_count)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("PASS requires real_drc_errors=0", json.loads(result.stdout)["errors"])

    def test_malformed_approval_is_blocked_without_traceback(self):
        self.data["approvals"] = []
        result = self.validate()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("approvals must be an object", json.loads(result.stdout)["errors"])
        self.assertEqual(result.stderr, "")

    def test_boolean_is_not_approval_evidence(self):
        self.data["verification"]["design_critical_substitution_required"] = True
        self.data["approvals"]["design_critical_substitution"] = "APPROVED"
        self.data["approval_evidence"] = {"design_critical_substitution": True}
        result = self.validate()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        errors = json.loads(result.stdout)["errors"]
        self.assertTrue(any("design_critical_substitution" in error and "evidence" in error for error in errors))

    def test_confined_rejects_a_link_even_within_the_package(self):
        dir_path = self.root / "board-files"
        dir_path.mkdir()
        artifact = dir_path / "board_source.dat"
        (self.root / artifact.name).rename(artifact)
        alias = self.root / "aliased-files"
        try:
            alias.symlink_to(dir_path, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symbolic links unavailable: {exc}")
        self.artifacts["board_source"]["path"] = f"{alias.name}/{artifact.name}"
        allowed = self.validate(confined=False)
        self.assertEqual(allowed.returncode, 0, allowed.stdout + allowed.stderr)
        blocked = self.validate()
        self.assertEqual(blocked.returncode, 1, blocked.stdout + blocked.stderr)
        self.assertTrue(any("symbolic links or reparse points" in error for error in json.loads(blocked.stdout)["errors"]))

    def test_builder_reports_blocked_state_and_preserves_artifact(self):
        builder = RELEASE_SCRIPTS / "build_release_manifest.py"
        artifact = self.root / "board_source.dat"
        content = artifact.read_bytes()
        arguments = ("--release", "preview", "--revision", "A", "--artifact", f"board_source={artifact}",
                     "--artifact-revision", "board_source=A")
        report = run_cli(builder, *arguments, "--output", self.manifest)
        self.assertEqual(report.returncode, 0, report.stdout + report.stderr)
        self.assertEqual(json.loads(report.stdout)["status"], "BLOCKED")
        self.assertEqual(json.loads(self.manifest.read_text(encoding="utf-8"))["status"], "BLOCKED")
        collision = run_cli(builder, *arguments, "--output", artifact)
        self.assertNotEqual(collision.returncode, 0)
        self.assertIn("cannot overwrite an artifact", collision.stderr)
        self.assertEqual(artifact.read_bytes(), content)


class ProgramStateGuard(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.state = self.root / "program-state.json"
        self.call("init", "--project", "fixture", success=True)

    def call(self, *arguments, success):
        result = run_cli(PROGRAM_STATE, "--file", self.state, *arguments)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def read_state(self):
        return json.loads(self.state.read_text(encoding="utf-8"))

    def stage(self, name, status, *arguments, evidence="review evidence", success=True):
        return self.call("set-stage", "--stage", name, "--status", status, "--evidence", evidence, *arguments,
                         success=success)

    def advance_upstream(self):
        for stage in ("product_definition", "sourcing", "circuit", "schematic_visual", "placement", "routing"):
            self.stage(stage, "PASS")

    def frozen_release(self, name, *, cpl=VALID_CPL):
        package = self.root / name
        payload = release_fixture(package, cpl=cpl)
        payload["release"] = name
        path = package / "manifest.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def invalidate(self, change):
        return self.call("invalidate", "--change", change, "--reason", "test fixture", success=True)

    def test_stage_and_approval_require_nonblank_text(self):
        report = self.call("validate", success=True)
        self.assertEqual(json.loads(report.stdout)["scope"], "program_state")
        self.assertTrue(all(stage["status"] == "BLOCKED" for stage in self.read_state()["stages"].values()))
        before = self.state.read_bytes()
        for status in ("PASS", "USER_REVIEW"):
            result = self.stage("product_definition", status, evidence="  ", success=False)
            self.assertIn("nonempty --evidence", result.stderr)
        for status in ("APPROVED", "REJECTED"):
            result = self.call("set-approval", "--approval", "design_critical_substitution", "--status", status,
                               "--evidence", "acknowledgement", "--evidence", " ", success=False)
            self.assertIn("nonempty --evidence", result.stderr)
        self.assertEqual(self.state.read_bytes(), before)

        state = self.read_state()
        state["stages"]["product_definition"] = {"status": "PASS", "evidence": [" "]}
        state["approvals"]["design_critical_substitution"] = "APPROVED"
        state["approval_evidence"]["design_critical_substitution"] = [True]
        self.state.write_text(json.dumps(state), encoding="utf-8")
        invalid = json.loads(self.call("validate", success=False).stdout)
        self.assertTrue(any("product_definition" in error and "evidence" in error for error in invalid["errors"]))
        self.assertTrue(any("design_critical_substitution" in error and "evidence" in error for error in invalid["errors"]))

    def test_browser_recovery_needs_two_new_verified_hashes(self):
        self.advance_upstream()
        original = self.frozen_release("original")
        missing = self.stage("manufacturing_release", "PASS", evidence="missing.json", success=False)
        self.assertIn("requires --release-manifest", missing.stderr)
        self.stage("manufacturing_release", "PASS", "--release-manifest", original)
        self.stage("assembly_placement", "USER_REVIEW")
        self.call("set-approval", "--approval", "assembly_placement", "--status", "APPROVED", "--evidence", "user fixture", success=True)
        self.stage("assembly_placement", "PASS")

        self.invalidate("browser-placement")
        report = self.invalidate("cpl")
        self.assertTrue(json.loads(report.stdout)["manual_browser_edits_present"])
        self.assertEqual(self.read_state()["approvals"]["assembly_placement"], "PENDING")
        self.stage("assembly_placement", "USER_REVIEW", success=False)
        before = self.state.read_bytes()
        missing = self.stage("manufacturing_release", "PASS", "--release-manifest", self.root / "missing.json", success=False)
        self.assertIn("cannot verify release manifest", missing.stderr)
        unchanged = self.stage("manufacturing_release", "PASS", "--release-manifest", self.frozen_release("renamed"), success=False)
        self.assertIn("new SHA-256: cpl", unchanged.stderr)
        bad = self.frozen_release("bad", cpl=VALID_CPL + b"R2,3,4,Top,0\n")
        invalid = self.stage("manufacturing_release", "PASS", "--release-manifest", bad, success=False)
        self.assertIn("cpl_places_excluded_reference", invalid.stderr)
        self.assertEqual(self.state.read_bytes(), before)

        new_cpl = VALID_CPL.replace(b",1,2,", b",9,2,")
        replacement = self.frozen_release("replacement", cpl=new_cpl)
        self.stage("manufacturing_release", "PASS", "--release-manifest", replacement)
        state = self.read_state()
        self.assertFalse(state["manual_browser_edits_present"])
        self.assertEqual(state["artifacts"]["release_manifest"]["sha256"], hashlib.sha256(replacement.read_bytes()).hexdigest().upper())
        self.assertEqual(state["artifacts"]["cpl"]["sha256"], hashlib.sha256(new_cpl).hexdigest().upper())
        self.stage("assembly_placement", "USER_REVIEW")
        self.stage("assembly_placement", "PASS", success=False)

        replacement.write_bytes(replacement.read_bytes() + b"\n")
        report = json.loads(self.call("validate", success=False).stdout)
        self.assertTrue(any("differs from the recorded" in error for error in report["errors"]))
        self.invalidate("cpl")
        self.assertEqual(self.read_state()["stages"]["manufacturing_release"]["status"], "BLOCKED")

    def test_older_browser_history_requires_original_manifest(self):
        self.advance_upstream()
        self.invalidate("browser-placement")
        state = self.read_state()
        state["manual_browser_edits_present"] = False
        state["invalidation_log"][-1].pop("previous_release")
        state["invalidation_log"][-1]["regenerated_release"] = "renewal claimed without hashes"
        state["invalidation_log"].append({"change": "cpl", "reason": "older script cleared the flag"})
        state["stages"]["manufacturing_release"] = {"status": "PASS", "evidence": ["unverified old record"]}
        self.state.write_text(json.dumps(state), encoding="utf-8")
        report = json.loads(self.call("validate", success=False).stdout)
        self.assertTrue(report["manual_browser_edits_present"])
        self.invalidate("cpl")

        original = self.frozen_release("original")
        new = self.frozen_release("replacement", cpl=VALID_CPL.replace(b",1,2,", b",8,2,"))
        result = self.stage("manufacturing_release", "PASS", "--release-manifest", new, success=False)
        self.assertIn("missing pre-edit release hashes", result.stderr)
        self.stage("manufacturing_release", "PASS", "--release-manifest", new, "--previous-release-manifest", original)
        self.assertFalse(self.read_state()["manual_browser_edits_present"])


class BomGuard(unittest.TestCase):
    def test_v1_dnp_false_keeps_default_enabled_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "bom.csv"
            output = root / "archive.csv"
            source.write_text("Designator,Qty,DNP\nR1,1,FALSE\nR2,1,0\nR3,1,True\nR4,1,否\n", encoding="utf-8")
            result = run_cli(BOM_ARCHIVE, source, "--output", output)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with output.open(encoding="utf-8-sig", newline="") as handle:
                records = list(csv.DictReader(handle))
            self.assertEqual([(row["位号"], row["状态"], row["备注"]) for row in records], [
                ("R1", "启用", "DNP=FALSE"), ("R2", "启用", "DNP=0"),
                ("R3", "", "DNP=True"), ("R4", "启用", "DNP=否"),
            ])


class SelectionGuard(unittest.TestCase):
    def test_no_clobber_preflights_all_requested_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "selection.json"
            target = root / "selection"
            excel = target.with_suffix(".xlsx")
            html = target.with_suffix(".html")
            excel.write_bytes(b"existing workbook")
            source.write_text(json.dumps({"reviewed": True, "rows": [{
                "ad_comment": "DEMO", "lcsc_code": "C900000001", "package": "0805",
                "component_type": "Connector", "specific_description": "Connector/DEMO/0805",
                "product_url": "https://example.org/product/C900000001",
            }]}), encoding="utf-8")
            result = run_cli(SELECTION_EXPORT, source, "--output", target, "--xlsx", "--no-clobber")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(excel.read_bytes(), b"existing workbook")
            self.assertFalse(html.exists())

    def test_actual_commit_rejects_a_target_created_since_preflight(self):
        write_atomic = runpy.run_path(str(SELECTION_EXPORT))["write_atomic"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "selection.html"
            target.write_bytes(b"other writer")
            with self.assertRaises(FileExistsError):
                write_atomic(target, b"new selection", no_clobber=True)
            self.assertEqual(target.read_bytes(), b"other writer")
            self.assertEqual(list(root.iterdir()), [target])
            write_atomic(target, b"approved replacement")
            self.assertEqual(target.read_bytes(), b"approved replacement")


if __name__ == "__main__":
    unittest.main()
