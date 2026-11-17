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
BOM_ARCHIVE = SKILLS / "bom-material-archive" / "scripts" / "bom_archive.py"
SELECTION_EXPORT = SKILLS / "component-sourcing" / "scripts" / "render_ad_selection.py"


def run_cli(script, *arguments):
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(script), *(str(arg) for arg in arguments)],
        capture_output=True, text=True, encoding="utf-8", check=False,
    )


class ReleaseGuard(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.manifest = self.root / "manifest.json"
        self.artifacts = {}
        for role in (
            "board_source", "eda_project", "gerber", "drill", "bom", "cpl", "constraints",
            "render_top", "render_bottom", "circuit_review", "schematic_connectivity",
            "schematic_visual_audit", "layout_review", "sourcing_lock",
        ):
            content = f"fixture: {role}".encode()
            artifact = self.root / f"{role}.dat"
            artifact.write_bytes(content)
            self.artifacts[role] = {
                "path": artifact.name, "revision": "A", "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest().upper(),
            }
        self.data = {
            "schema": "pcba-release-manifest-v1", "revision": "A", "status": "PASS",
            "artifacts": self.artifacts,
            "constraints": {"board_width_mm": 12, "board_height_mm": 18, "layer_count": 2,
                            "thickness_mm": 1.6, "surface_finish": "ENIG", "assembly_sides": ["Top"],
                            "quantity_pcbs": 5, "quantity_assembled": 4},
            "verification": {"unexplained_raw_disconnects": "0", "real_drc_errors": "DRC_VALUE",
                             "layout_check_failures": 0.0, "circuit_gate": "PASS", "layout_gate": "PASS",
                             "raw_connectivity": "PASS", "power_connectivity": "PASS",
                             "visual_mechanical_review": "PASS", "dfm_review": "PASS",
                             "sourcing_lock_current": "PASS", "revision_reconciled": "PASS",
                             "design_critical_substitution_required": False},
            "approvals": {"design_critical_substitution": "PENDING", "assembly_placement": "PENDING",
                          "final_price": "PENDING", "payment": "PENDING"},
        }

    def validate(self, raw_count="0", *, confined=True):
        self.manifest.write_text(json.dumps(self.data).replace('"DRC_VALUE"', raw_count), encoding="utf-8")
        flags = ["--confine-to-manifest-dir"] if confined else []
        return run_cli(RELEASE_SCRIPTS / "validate_release_manifest.py", self.manifest, *flags)

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
