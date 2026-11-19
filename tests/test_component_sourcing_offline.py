import json
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "component-sourcing" / "scripts"


def run_cli(script, *args):
    return subprocess.run([sys.executable, "-X", "utf8", str(SCRIPTS / script), *map(str, args)],
                          capture_output=True, encoding="utf-8", check=False)


class PassiveIndexTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "standard-passives.json"

    def query(self, records, *args):
        source = json.dumps(records, ensure_ascii=False).encode("utf-8-sig")
        self.path.write_bytes(source)
        result = run_cli("query_passive_index.py", self.path, *args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.path.read_bytes(), source)
        return json.loads(result.stdout)

    def test_exact_identities_and_conflict(self):
        records = [
            {"lcsc_id": "C900000001", "code": "C900000001", "mpn": "SAMPLE-A", "package": "0402"},
            {"code": "C900000002", "mpn": "SAMPLE-A-1", "package": "0402"},
            {"lcsc_id": "C900000004", "code": "C900000003", "mpn": "SAMPLE-B"},
        ]
        self.assertEqual(self.query(records, "--mpn", "sample-a")["matched"], [records[0]])
        self.assertEqual(self.query(records, "--code", "c900000002")["matched"], [records[1]])
        conflict = self.query(records, "--code", "C900000003")
        self.assertEqual(conflict["matched_count"], 0)
        self.assertEqual(conflict["pending"][0]["unknown_conditions"], ["lcsc_id 与 code 冲突"])

    def test_units_hard_conditions_and_pending_evidence(self):
        sample = {"group": "贴片电容_0603", "package": "0603", "brand": "示例品牌"}
        records = [
            {**sample, "code": "C900000001", "parameters": {"容值": "100nF", "额定电压": "0.05kV", "温度系数": "X7R"}},
            {**sample, "code": "C900000002", "parameters": {"容值": "0.1µF", "额定电压": "63V", "温度系数": "X7R"}},
            {**sample, "code": "C900000003", "parameters": {"容值": "100nF", "额定电压": "-"}},
            {**sample, "code": "C900000004", "parameters": {"容值": "100nF", "额定电压": "25V", "温度系数": "X7R"}},
            {**sample, "code": "C900000005", "parameters": {"容值": "0.1mF", "额定电压": "100V", "温度系数": "X7R"}},
            {**sample, "code": "C900000006", "parameters": {"容值": "100nF", "工作电压(AC)": "250V", "温度系数": "X7R"}},
            {**sample, "code": "C900000007", "package": "0805", "parameters": {"容值": "100nF", "额定电压": "50V", "温度系数": "X7R"}},
        ]
        options = ("--group", sample["group"], "--package", "0603", "--brand", sample["brand"],
                   "--param", "容值=0.1uF", "--param", "额定电压>=50V", "--param", "温度系数=X7R")
        result = self.query(records, *options)
        self.assertEqual(result["matched"], records[:2])
        self.assertEqual({row["code"]: row["unknown_conditions"] for row in result["pending"]}, {
            "C900000003": ["额定电压", "温度系数"], "C900000006": ["额定电压"],
        })
        limited = self.query(records, *options, "--limit", 1)
        self.assertEqual((limited["matched_count"], limited["pending_count"]), (2, 2))
        self.assertEqual((len(limited["matched"]), len(limited["pending"])), (1, 1))
        self.assertTrue(limited["truncated"])

    def test_milliohm_does_not_match_megohm(self):
        result = self.query([
            {"code": "C900000001", "parameters": {"阻值": "2mΩ", "精度": "±1%"}},
            {"code": "C900000002", "parameters": {"阻值": "2MΩ", "精度": "±1%"}},
            {"code": "C900000003", "parameters": {"阻值": "0.002Ω", "精度": "-1%~+1%"}},
        ], "--param", "阻值=0.002Ω", "--param", "精度<=±1%")
        self.assertEqual([row["code"] for row in result["matched"]], ["C900000001"])
        self.assertEqual(result["pending"][0]["unknown_conditions"], ["精度"])

    def test_brand_preference_ranks_only_hard_matches_before_limiting(self):
        sample = {"package": "0603", "parameters": {"阻值": "10kΩ"}}
        records = [
            {**sample, "code": "C900000001", "brand": "其他品牌"},
            {**sample, "code": "C900000002", "brand": "FH(风华)示例"},
            {**sample, "code": "C900000003", "brand": "FH(风华)", "parameters": {"阻值": "1kΩ"}},
            {**sample, "code": "C900000004", "brand": "其他品牌", "parameters": {}},
            {**sample, "code": "C900000005", "brand": "FH(风华)"},
            {**sample, "code": "C900000006", "brand": "FH(风华)", "parameters": {}},
            {**sample, "code": "C900000007", "brand": "FH(风华)"},
            {**sample, "code": "C900000008", "brand": "其他品牌"},
            {**sample, "code": "C900000009"},
        ]
        options = ("--package", "0603", "--param", "阻值=10kΩ")
        preference = ("--preferred-brand", " fh(风华) ")
        original = self.query(records, *options)
        self.assertEqual(original["matched"], [records[i] for i in (0, 1, 4, 6, 7, 8)])
        preferred = self.query(records, *options, *preference)
        self.assertEqual(preferred["matched"], [records[i] for i in (4, 6, 0, 1, 7, 8)])
        self.assertEqual(preferred["pending"], [
            {**records[3], "unknown_conditions": ["阻值"]},
            {**records[5], "unknown_conditions": ["阻值"]},
        ])
        limited = self.query(records, *options, *preference, "--limit", 1)
        self.assertEqual(limited["matched"], [records[4]])
        self.assertEqual(limited["pending"], preferred["pending"][:1])
        self.assertEqual((limited["matched_count"], limited["pending_count"]), (6, 2))
        self.assertTrue(limited["truncated"])

        forced_other = self.query(records, *options, "--brand", "其他品牌", *preference)
        self.assertEqual(forced_other["matched"], [records[0], records[7]])
        self.assertEqual(forced_other["pending"], [
            {**records[3], "unknown_conditions": ["阻值"]},
            {**records[8], "unknown_conditions": ["brand"]},
        ])

    def test_brand_preference_requires_a_real_brand_and_a_filter(self):
        invalid_brand = run_cli("query_passive_index.py", self.path, "--package", "0603",
                                "--preferred-brand", "待核实")
        self.assertEqual(invalid_brand.returncode, 2)
        self.assertIn("筛选值需明确", invalid_brand.stderr)
        no_filter = run_cli("query_passive_index.py", self.path, "--preferred-brand", "FH(风华)")
        self.assertEqual(no_filter.returncode, 2)
        self.assertIn("至少提供一个料号或规格条件", no_filter.stderr)

    def test_rejects_malformed_index_and_unsupported_numeric_limit(self):
        self.path.write_text('{"parts": []}', encoding="utf-8")
        self.assertEqual(run_cli("query_passive_index.py", self.path, "--code", "C900000001").returncode, 1)
        result = run_cli("query_passive_index.py", self.path, "--param", "容值>=100")
        self.assertEqual(result.returncode, 2)
        self.assertIn("数值上下限需带支持的单位", result.stderr)


class SavedLibraryTest(unittest.TestCase):
    def test_filter_and_limit_select_only_needed_schematic_streams(self):
        def make_item(name, path):
            return SimpleNamespace(
                name=name, description="合成器件", virtual_path=path, models=[
                    SimpleNamespace(model_type="PcbLib", name="TEST-0402"),
                    SimpleNamespace(model_type="SIM", name="TEST-SIM"),
                ],
            )

        class IntLib:
            component_parse_error = None
            components = [make_item("FIRST", "source0"), make_item("SECOND", "source0"),
                          make_item("THIRD", "source1")]

            def __init__(self):
                self.read = []

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                pass

            def read_stream(self, path):
                self.read.append(path)
                return path.encode("ascii")

        class SchLib:
            def __init__(self, path):
                self.stream = path.read_bytes()

            def get_symbol(self, name):
                if self.stream == b"source0":
                    return SimpleNamespace(pins=[1, 2], parameters=[SimpleNamespace(name="阻值", text="10Ω")])
                return None

        library = IntLib()
        backend = SimpleNamespace(AltiumIntLib=SimpleNamespace(from_file=lambda path: library), AltiumSchLib=SchLib)
        inspect = runpy.run_path(str(SCRIPTS / "inspect_saved.py"))["inspect"]
        with patch.dict(sys.modules, {"altium_monkey": backend}):
            summary = inspect(Path("test.IntLib"), designator=None, limit=2)
            self.assertEqual(library.read, ["source0"])
            self.assertEqual((summary["component_count"], summary["matched_count"], summary["truncated"]), (3, 3, True))
            self.assertEqual(summary["components"][0]["parameters"], [{"name": "阻值", "value": "10Ω"}])
            self.assertEqual(summary["components"][0]["pin_count"], 2)
            self.assertEqual(summary["components"][0]["footprints"], ["TEST-0402"])
            selected = inspect(Path("test.IntLib"), designator=None, component="third", limit=2)
            self.assertEqual(library.read, ["source0", "source1"])
            self.assertEqual((selected["matched_count"], selected["truncated"]), (1, False))
            self.assertIn("warning", selected["components"][0])
            self.assertNotIn("parameters", selected["components"][0])
            library.component_parse_error = "invalid cross-reference"
            with self.assertRaisesRegex(ValueError, "交叉引用无法读取"):
                inspect(Path("test.IntLib"), designator=None, limit=2)


class ExportCandidateCompatibilityTest(unittest.TestCase):
    def test_new_and_legacy_descriptions_in_review_draft(self):
        part = {"ad_comment": "10K", "ad_description": "旧版通用描述", "component_type": "贴片电阻",
                "package": "0402", "evidence": {"product_url": "https://example.org/sample"}}
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "candidates.json"
            draft = Path(directory) / "review.json"
            source.write_text(json.dumps({"results": [
                {**part, "lcsc_code": "C900000001", "generic_description": "新版通用描述", "specific_description": "新版具体描述"},
                {**part, "lcsc_code": "C900000002"},
            ]}, ensure_ascii=False), encoding="utf-8")
            result = run_cli("render_ad_selection.py", source, "--draft", "--write-rows", draft, "--no-clobber")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(draft.read_text(encoding="utf-8"))
            self.assertIs(data["reviewed"], False)
            current, legacy = data["rows"]
            self.assertEqual((current["generic_description"], current["specific_description"]), ("新版通用描述", "新版具体描述"))
            self.assertEqual(current["source"]["specific_description"], "新版具体描述")
            self.assertEqual((legacy["generic_description"], legacy["specific_description"]), ("旧版通用描述", "待核实"))


if __name__ == "__main__":
    unittest.main()
