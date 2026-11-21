import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ASSEMBLY = ROOT / "skills/release-pcba-fabrication/scripts/check_assembly.py"
KICAD = ROOT / "skills/pcb-layout-review/scripts/check_kicad_report.py"


class OfflinePcbChecks(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)

    def write(self, name, text, encoding="utf-8"):
        path = self.directory / name
        path.write_text(text, encoding=encoding)
        return path

    def invoke(self, script, *args):
        done = subprocess.run(
            [sys.executable, "-X", "utf8", str(script), *map(str, args)],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        return done.returncode, json.loads(done.stdout or done.stderr)

    def test_grouped_bom_and_placement_match_without_touching_files(self):
        bom = self.write("BOM.csv", 'Designator,DNP\n"R1, R2",FALSE\nTP1,yes\nU7,0\nH1,\n', "utf-8-sig")
        cpl = self.write("CPL.csv", "Ref,PosX,PosY,Side,Rot\nr1,1.2mm,-3mm,top,-90\nR2,0mm,0mm,bottom,180\nU7,5mm,2mm,B.Cu,0\n")
        before = {kind: hashlib.sha256(path.read_bytes()).hexdigest() for kind, path in (("bom", bom), ("cpl", cpl))}
        code, report = self.invoke(ASSEMBLY, bom, "--cpl", cpl, "--exclude", "H1")
        self.assertEqual(code, 0, report)
        self.assertEqual(report["sha256"], before)
        self.assertEqual(report["matched_reference_count"], 3)
        self.assertEqual(report["excluded_references"], ["H1", "TP1"])
        self.assertEqual(report["cpl_side_counts"], {"top": 1, "bottom": 2})
        self.assertEqual({p.name for p in self.directory.iterdir()}, {"BOM.csv", "CPL.csv"})

    def test_reports_assembly_mismatch_instead_of_freezing(self):
        bom = self.write("BOM.csv", "Designator,DNP\nR1,0\nU7,false\nH1,true\n")
        cpl = self.write("CPL.csv", "Designator,Mid X,Mid Y,Layer,Rotation\nR1,1,NaN,inner,Infinity\nR1,1mil,2mm,T,0\nR2,0mm,0mm,B,90\nH1,1mm,1mm,T,0\n")
        code, report = self.invoke(ASSEMBLY, bom, "--cpl", cpl, "--exclude", "Z1")
        self.assertEqual(code, 1, report)
        findings = {item["code"]: item for item in report["issues"]}
        self.assertEqual(findings["bom_missing_from_cpl"]["references"], ["U7"])
        self.assertEqual(findings["cpl_missing_from_bom"]["references"], ["R2"])
        self.assertEqual(findings["cpl_places_excluded_reference"]["references"], ["H1"])
        self.assertEqual(findings["cpl_duplicate_references"]["counts"], {"R1": 2})
        self.assertEqual(findings["exclusion_not_in_bom"]["references"], ["Z1"])
        self.assertTrue({"cpl_invalid_coordinate", "cpl_invalid_rotation", "cpl_invalid_side",
                         "cpl_coordinate_unit_mismatch", "cpl_mixed_coordinate_units"} <= findings.keys())

    def test_bom_ranges_and_ambiguous_headers_never_match(self):
        bom = self.write("BOM.csv", "Designator\nR1-R3\n")
        cpl = self.write("CPL.csv", "Ref,PosX,PosY,Side,Rot\nR1,1,2,T,0\n")
        code, report = self.invoke(ASSEMBLY, bom, "--cpl", cpl)
        self.assertEqual(code, 1, report)
        self.assertIn("bom_invalid_reference", [x["code"] for x in report["issues"]])
        bad = self.write("bad.csv", "Ref,Designator,PosX,PosY,Side,Rot\nR1,R1,1,2,T,0\n")
        self.assertEqual(self.invoke(ASSEMBLY, bom, "--cpl", bad)[0], 2)
        self.assertEqual(self.invoke(ASSEMBLY, bom, "--cpl", bom)[0], 2)

    def test_vendor_dnp_and_fusion_coordinates(self):
        bom = self.write("BOM.csv", "Designator,Customer Supply,DNP\nR1,Yes,no\nR2,DNP,no\n")
        cpl = self.write("CPL.csv", "Ref Des,Mid X (mm),Mid Y (mm),Layer,Rotation\nR1,0,2,Top,0\nR2,3mil,5,Bottom,90\n")
        code, report = self.invoke(ASSEMBLY, bom, "--cpl", cpl)
        self.assertEqual(code, 1, report)
        findings = {item["code"]: item for item in report["issues"]}
        self.assertEqual(findings["bom_conflicting_dnp"]["references"], ["R2"])
        self.assertEqual(findings["cpl_places_excluded_reference"]["references"], ["R2"])
        self.assertEqual(findings["cpl_coordinate_unit_conflict"]["header_unit"], "mm")
        self.assertEqual(report["cpl_coordinate_units"], ["mil", "mm"])
        bom = self.write("BOM.csv", "Designator,Customer Supply,DNP\nR1,Yes,no\nR2,DNP,\n")
        cpl = self.write("CPL.csv", "Ref Des,Mid X (mm),Mid Y (mm),Layer,Rotation\nR1,0,2,Top,0\n")
        self.assertEqual(self.invoke(ASSEMBLY, bom, "--cpl", cpl)[0], 0)

    def test_kibot_compatible_fixture_keeps_dnc_and_explicitly_excludes_dnf(self):
        bom = self.write("bom.csv", "References,Status\nR1,DNC\nR2,DNF\nC1,\n")
        populated = "Ref,PosX,PosY,Rot,Side\nR1,1mm,2mm,0,top\nC1,3mm,4mm,90,bottom\n"
        cpl = self.write("pos.csv", populated)
        code, report = self.invoke(ASSEMBLY, bom, "--cpl", cpl, "--exclude", "R2")
        self.assertEqual(code, 0, report)
        self.assertEqual(report["cpl_side_counts"], {"top": 1, "bottom": 1})
        self.assertEqual(report["excluded_references"], ["R2"])
        self.assertEqual(self.invoke(ASSEMBLY, bom, "--cpl", cpl)[0], 1)  # no implicit Status parsing
        cpl.write_text(populated + "R2,1mm,2mm,0,top\n", encoding="utf-8")
        self.assertEqual(self.invoke(ASSEMBLY, bom, "--cpl", cpl, "--exclude", "R2")[0], 1)

    def kicad_report(self, kind, **values):
        report = {
            "$schema": f"https://schemas.kicad.org/{kind}.v1.json",
            "source": "Board.kicad_pcb" if kind == "drc" else "Board.kicad_sch",
            "date": "2026-11-18T12:00:00+08:00",
            "kicad_version": "9.0.9",
            "coordinate_units": "mm",
            "included_severities": ["error", "warning", "exclusion"],
            **values,
        }
        return self.write("report.json", json.dumps(report))

    def test_kicad_distinguishes_parity_unconnected_excluded_and_active(self):
        def violation(rule, severity, excluded=False):
            return {"type": rule, "severity": severity, "excluded": excluded, "description": rule, "items": []}

        path = self.kicad_report(
            "drc", violations=[violation("clearance", "error", excluded=True)],
            unconnected_items=[violation("unconnected_items", "error")],
            schematic_parity=[violation("missing_footprint", "warning")],
        )
        code, report = self.invoke(KICAD, path, "--kind", "drc")
        self.assertEqual(code, 1)
        self.assertEqual(report["counts"], {"error": 1, "warning": 1, "excluded": 1})
        self.assertEqual(report["groups"]["schematic_parity"]["warning"], 1)
        self.assertEqual(report["rules"]["clearance"]["excluded"], 1)
        self.assertEqual(report["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_erc_clean_report_missing_severity_and_wrong_kind(self):
        sheet = {"uuid_path": "/a3a2e0d5-352d-4a11-b73f-1d8b18079c01", "path": "/", "violations": []}
        path = self.kicad_report("erc", kicad_version="10.0.1", sheets=[sheet])
        code, report = self.invoke(KICAD, path)
        self.assertEqual(code, 0, report)
        self.assertEqual(report["status"], "no_reported_findings")
        self.assertEqual(report["group_sheet_paths"], {"sheets[0]": "/"})
        self.assertEqual(self.invoke(KICAD, path, "--kind", "drc")[0], 2)
        partial = self.kicad_report("erc", sheets=[sheet], included_severities=["error"])
        code, report = self.invoke(KICAD, partial, "--kind", "erc")
        self.assertEqual(code, 2)
        self.assertEqual(report["missing_severities"], ["exclusion", "warning"])
        self.assertEqual(report["status"], "coverage_incomplete")

    def test_kicad_cannot_pass_missing_groups_or_duplicate_keys(self):
        missing = self.kicad_report("drc", violations=[], unconnected_items=[])
        self.assertEqual(self.invoke(KICAD, missing)[0], 2)
        duplicate = self.write("duplicate.json", '{"violations":[{}],"violations":[]}')
        code, report = self.invoke(KICAD, duplicate)
        self.assertEqual(code, 2)
        self.assertIn("duplicate JSON member", report["error"])

    def test_kicad_ignored_checks_are_visible_even_without_violations(self):
        ignored = [{"key": "shorting_items", "description": "Shorting items"}]
        path = self.kicad_report(
            "drc", kicad_version="10.0.1", violations=[], unconnected_items=[],
            schematic_parity=[], ignored_checks=ignored,
        )
        code, report = self.invoke(KICAD, path)
        self.assertEqual(code, 1, report)
        self.assertEqual(report["ignored_checks"], ignored)


if __name__ == "__main__":
    unittest.main()
