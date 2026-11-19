import hashlib
from importlib.util import find_spec
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
FIXTURES = ROOT / "tests" / "fixtures" / "native-eda"
SPICE = SKILLS / "design-and-review-circuit"
CAM = SKILLS / "release-pcba-fabrication"
ROUTER = SKILLS / "hardware/scripts/hardware_tool.py"
KICAD_CLI = os.environ.get("HARDWARE_TEST_KICAD_CLI") or shutil.which("kicad-cli")
KICAD_PYTHON = os.environ.get("HARDWARE_TEST_KICAD_PYTHON")
NGSPICE_CLI = (os.environ.get("HARDWARE_TEST_NGSPICE_CLI") or
              shutil.which("ngspice_con") or shutil.which("ngspice"))


class NativeEdaContract(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name)
        self.environment = {
            **os.environ,
            "KICAD_CONFIG_HOME": str(self.work / "kicad-config"),
            "KICAD_DOCUMENTS_HOME": str(self.work / "kicad-documents"),
        }

    def command(self, *args):
        return subprocess.run(
            list(map(str, args)), cwd=self.work, env=self.environment, capture_output=True, encoding="utf-8",
            errors="replace", check=False, timeout=150,
        )

    def invoke(self, script, *args):
        result = self.command(sys.executable, "-X", "utf8", "-B", script, *args)
        self.assertTrue(result.stdout.strip(), result.stderr)
        return result.returncode, json.loads(result.stdout)

    def fixture(self, name):
        path = self.work / name
        path.write_bytes((FIXTURES / f"{name}.txt").read_bytes())
        return path

    @unittest.skipUnless(KICAD_CLI, "需要 KiCad CLI 或 HARDWARE_TEST_KICAD_CLI")
    def test_kicad_native_zero_finding_violation_and_erc_match_real_report(self):
        script = SKILLS / "pcb-layout-review/scripts/run_kicad_checks.py"
        for fixture, kind, native_code in [
            ("outline.kicad_pcb", "drc", 0), ("no-outline.kicad_pcb", "drc", 5), ("empty.kicad_sch", "erc", 0),
        ]:
            with self.subTest(fixture=fixture):
                source = self.fixture(fixture)
                before = hashlib.sha256(source.read_bytes()).hexdigest()
                dest = self.work / f"run-{fixture}"
                code, value = self.invoke(script, source, "--kicad-cli", KICAD_CLI, "--output-dir", dest)
                self.assertEqual(value["execution_status"], "completed", value)
                self.assertEqual(value["checks_executed"], [f"native_{kind}", "report_readback"])
                self.assertEqual(value["native"]["returncode"], native_code)
                self.assertEqual(value["mutation_outcome"], "unchanged")
                self.assertEqual(before, hashlib.sha256(source.read_bytes()).hexdigest())
                self.assertEqual(before, value["inputs"][fixture]["sha256"])
                report = json.loads((dest / f"{kind}.json").read_bytes())
                self.assertEqual(value["outputs"][kind]["sha256"],
                                 hashlib.sha256((dest / f"{kind}.json").read_bytes()).hexdigest())
                self.assertNotEqual(value["verification_status"], "pass")
                if "included_severities" not in report:
                    self.assertEqual(value["verification_status"], "coverage_incomplete")
                if native_code == 5:
                    self.assertEqual(value["native"]["report"]["rules"]["invalid_outline"]["error"], 1)
                    self.assertNotEqual(code, 0)
                self.assertEqual(json.loads((dest / "evidence.json").read_bytes()), value)
                self.assertEqual(self.invoke(script, source, "--kicad-cli", KICAD_CLI, "--output-dir", dest)[0], 2)

    @unittest.skipUnless(NGSPICE_CLI, "需要 ngspice CLI 或 HARDWARE_TEST_NGSPICE_CLI")
    def test_ngspice_rc_rlc_missing_measure_and_missing_model_use_real_solver(self):
        fixture_root = SPICE / "assets/spice-fixtures"
        for fixture, execution, verification in [
            ("rc", "completed", "pass"),
            ("rlc", "completed", "pass"),
            ("rc-missing", "completed", "missing"),
            ("missing-model", "failed", "not_evaluated"),
        ]:
            with self.subTest(fixture=fixture):
                dest = self.work / fixture
                _, result = self.invoke(ROUTER, "spice-run", fixture_root / f"{fixture}.json",
                                        "--ngspice-cli", NGSPICE_CLI, "--output-dir", dest)
                self.assertEqual(result["execution_status"], execution)
                self.assertEqual(result["verification_status"], verification)
                self.assertEqual(result["mutation_outcome"], "unchanged")
                self.assertIn("native", result["outputs"])
                if fixture == "rc":
                    measured = float(result["native"]["measurements"]["tau"]["value"])
                    self.assertAlmostEqual(measured, 1000 * 1e-6, delta=1e-6)
                if fixture == "rlc":
                    resistance, inductance, capacitance = 100, 10e-3, 100e-9
                    damping = resistance / (2 * inductance)
                    angular_frequency = math.sqrt(1 / (inductance * capacitance) - damping**2)
                    expected_peak = 1 + math.exp(-damping * math.pi / angular_frequency)
                    measured = float(result["native"]["measurements"]["peak"]["value"])
                    self.assertAlmostEqual(measured, expected_peak, delta=0.002)

    @unittest.skipUnless(KICAD_CLI, "需要 KiCad CLI 验证自定义规则实际执行")
    def test_kicad_custom_rule_sentinel_detects_strict_edge_clearance(self):
        board = self.fixture("pads.kicad_pcb")
        board_digest = hashlib.sha256(board.read_bytes()).hexdigest()
        rules = board.with_suffix(".kicad_dru")
        for limit, violations in ((1, 0), (5, 3)):
            with self.subTest(minimum_edge_clearance_mm=limit):
                rule = f'(version 1)\n(rule "fixture_edge_clearance" (severity error) (constraint edge_clearance (min {limit}mm)))\n'
                rules.write_text(rule, encoding="utf-8")
                digest = hashlib.sha256(rules.read_bytes()).hexdigest()
                output = self.work / f"sentinel-{limit}"
                _, evidence = self.invoke(ROUTER, "kicad-native-check", board,
                                          "--kicad-cli", KICAD_CLI, "--output-dir", output)
                self.assertEqual(evidence["execution_status"], "completed")
                self.assertEqual(evidence["inputs"][rules.name]["sha256"], digest)
                self.assertEqual(hashlib.sha256(rules.read_bytes()).hexdigest(), digest)
                self.assertEqual(evidence["inputs"][board.name]["sha256"], board_digest)
                self.assertEqual(hashlib.sha256(board.read_bytes()).hexdigest(), board_digest)
                report = json.loads((output / "drc.json").read_bytes())
                matches = [item for item in report["violations"] if item["type"] == "copper_edge_clearance"
                           and "fixture_edge_clearance" in item["description"]]
                self.assertEqual(len(matches), violations, report["violations"])

    @unittest.skipUnless(find_spec("gerbonara"), "需要 Gerbonara 做独立 CAM 读回")
    def test_cam_gerber_and_excellon_geometry_and_negatives(self):
        script = CAM / "scripts/check_cam.py"
        copied = self.work / "cam-fixtures"
        shutil.copytree(CAM / "assets/cam-fixtures", copied)
        path = copied / "board.json"
        spec = json.loads(path.read_bytes())
        code, result = self.invoke(script, path)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["native"]["layers"]["outline"]["bounds_mm"], [-0.05, -0.05, 20.05, 10.05])
        self.assertEqual(result["native"]["layers"]["plated_drill"]["drills"], 2)
        spec["layers"]["front_copper"]["unit"] = "inch"
        path.write_text(json.dumps(spec), encoding="utf-8")
        code, result = self.invoke(script, path)
        self.assertEqual(code, 1, result)
        self.assertEqual(result["native"]["layers"]["front_copper"]["issues"], ["unit_mismatch"])
        spec["layers"]["front_copper"]["unit"] = "mm"
        spec["layers"]["outline"]["bounds_mm"] = [0, 0, 20, 10]
        path.write_text(json.dumps(spec), encoding="utf-8")
        self.assertEqual(self.invoke(script, path)[1]["native"]["layers"]["outline"]["issues"], ["geometry_mismatch"])
        del spec["layers"]["front_copper"]
        path.write_text(json.dumps(spec), encoding="utf-8")
        self.assertEqual(self.invoke(script, path)[1]["verification_status"], "missing")
        (copied / spec["layers"]["plated_drill"]["path"]).write_text("M48\nM30\n", encoding="utf-8")
        self.assertEqual(self.invoke(script, path)[1]["verification_status"], "invalid")

    def test_offline_canonical_connectivity_positive_and_omitted_pin(self):
        comparer = SKILLS / "schematic-humanizer/scripts/compare_connectivity.py"
        kicad_xml = self.work / "kicad.xml"
        kicad_xml.write_text(
            '<export><components><comp ref="J1"><value>CONTACT</value><footprint>FIXTURE</footprint>'
            '<libsource lib="" part=""/></comp></components><nets><net name="SENSE">'
            '<node ref="J1" pin="1"/><node ref="J1" pin="2"/></net></nets></export>',
            encoding="utf-8",
        )
        canonical = self.work / "saved-altium.json"
        value = {
            "schema": "schematic-connectivity-v1",
            "components": [{"ref": "J1", "value": "CONTACT", "footprint": "FIXTURE", "device": ""}],
            "nets": [{"name": "SENSE", "pins": [{"ref": "J1", "pin": "1"}, {"ref": "J1", "pin": "2"}]}],
        }
        canonical.write_text(json.dumps(value), encoding="utf-8")
        positive = self.command(sys.executable, "-X", "utf8", "-B", comparer, kicad_xml, canonical)
        self.assertEqual(positive.returncode, 0, positive.stdout + positive.stderr)
        value["nets"][0]["pins"].pop()
        canonical.write_text(json.dumps(value), encoding="utf-8")
        negative = self.command(sys.executable, "-X", "utf8", "-B", comparer, kicad_xml, canonical)
        self.assertEqual(negative.returncode, 1, negative.stdout + negative.stderr)

    @unittest.skipUnless(KICAD_PYTHON and KICAD_CLI and find_spec("altium_monkey"),
                         "需要 KiCad CLI、HARDWARE_TEST_KICAD_PYTHON 和 altium-monkey")
    def test_same_saved_pcb_contacts_on_kicad_and_altium_with_native_export(self):
        from altium_monkey import AltiumPcbDoc

        source = self.fixture("pads.kicad_pcb")
        altium = self.work / "pads.PcbDoc"
        board = AltiumPcbDoc()
        board.add_net("SENSE")
        for designator, position, side in (("J1", (400, 400), "TOP"), ("J2", (800, 800), "BOTTOM")):
            board.add_component(designator=designator, footprint="FIXTURE", position_mils=position, layer=side)
            pad = board.add_pad(designator="1", position_mils=position,
                                width_mils=40, height_mils=40, net="SENSE", layer=side)
            pad.component_index = len(board.components) - 1
        pad = board.add_pad(designator="2", position_mils=(480, 400),
                            width_mils=40, height_mils=40)
        pad.component_index = 0
        board.set_outline_rectangle_mils(200, 200, 1200, 1000)
        board.save(altium)
        inputs = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in (source, altium)}
        parsed = AltiumPcbDoc.from_file(altium)
        actual_ad = sorted(
            [parsed.components[pad.component_index].designator, pad.designator,
             parsed.nets[pad.net_index].name if pad.net_index is not None else None,
             parsed.components[pad.component_index].layer]
            for pad in parsed.pads
        )
        expected = [["J1", "1", "SENSE", "TOP"], ["J1", "2", None, "TOP"], ["J2", "1", "SENSE", "BOTTOM"]]
        code = (
            "import json,sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "from tools.kicad.pcb_parser_kicad import PCBParserKiCad\n"
            "board=PCBParserKiCad(sys.argv[2]).board\n"
            "sides={'F.Cu':'TOP','B.Cu':'BOTTOM'}\n"
            "print(json.dumps(sorted([fp.GetReference(), pad.GetNumber(), pad.GetNetname() or None, "
            "sides[fp.GetLayerName()]] for fp in board.GetFootprints() for pad in fp.Pads())))"
        )
        result = self.command(KICAD_PYTHON, "-X", "utf8", "-B", "-c", code,
                              SKILLS / "schematic-analyzer/scripts", source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(actual_ad, expected)
        self.assertEqual(json.loads(result.stdout), expected)
        native = self.work / "native.d356"
        export = self.command(KICAD_CLI, "pcb", "export", "ipcd356", "--output", native, source)
        self.assertEqual(export.returncode, 0, export.stderr)
        native_rows = [line for line in native.read_text(encoding="ascii").splitlines() if line.startswith("327")]
        export_contacts = sorted(
            [line[20:26].strip(), line[27:31].strip(), None if line[3:17].strip() == "N/C" else line[3:17].strip(),
             {"A01": "TOP", "A02": "BOTTOM"}[line[38:41]]]
            for line in native_rows
        )
        self.assertEqual(export_contacts, expected)
        self.assertEqual(inputs, {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs})
