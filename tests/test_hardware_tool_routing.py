"""Check local path boundaries and the wrapper's reported plan."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROUTER = Path(__file__).resolve().parents[1] / "skills" / "hardware" / "scripts" / "hardware_tool.py"


class HardwareToolRouting(unittest.TestCase):
    def test_formal_evidence_flag_reaches_only_the_three_matching_checkers(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            measurements = Path(directory) / "measurements.csv"
            source.write_text("{}", encoding="utf-8")
            measurements.write_text("test_id,value\n", encoding="utf-8")
            for name, extras in (
                ("release-check", []), ("kicad-report-check", ["--kind", "drc"]),
                ("bench-check", ["--measurements", measurements]),
            ):
                with self.subTest(name=name):
                    result = self.plan(name, source, "--formal", *extras)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    plan = json.loads(result.stdout)
                    self.assertEqual(plan["level"], "L0")
                    self.assertEqual(plan["parameters"].count("--formal"), 1)
                    if name == "release-check":
                        self.assertIn("--confine-to-manifest-dir", plan["parameters"])

    def plan(self, *arguments):
        return subprocess.run(
            [sys.executable, "-X", "utf8", str(ROUTER), "--plan", *map(str, arguments)],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )

    def test_linked_parent_cannot_hide_input_or_output_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            actual = root / "real"
            actual.mkdir()
            link = root / "alias"
            if os.name == "nt":
                from _winapi import CreateJunction

                CreateJunction(str(actual), str(link))
            else:
                link.symlink_to(actual, target_is_directory=True)
            source = actual / "parts.csv"
            source.write_text("MPN\nExample\n", encoding="utf-8")

            read = self.plan("sourcing-lock-check", link / source.name)
            write = self.plan("bom-archive", source, "--output", link / "archive.csv")
            for result in (read, write):
                self.assertEqual(result.returncode, 2)
                self.assertIn("符号链接或 Windows 重解析点", result.stderr)
                self.assertEqual(result.stdout, "")
            self.assertFalse((actual / "archive.csv").exists())

    @unittest.skipUnless(os.name == "nt", "Windows UNC boundary")
    def test_unc_is_rejected_before_path_access(self):
        unc = "\\" * 2 + "hardware-routing.invalid" + "\\" + "share" + "\\" + "parts.csv"
        result = self.plan("sourcing-lock-check", unc)
        self.assertEqual(result.returncode, 2)
        self.assertIn("网络盘或 UNC", result.stderr)

    def test_normal_plan_reports_scope_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            bom, cpl = root / "BOM.csv", root / "CPL.csv"
            for file in (bom, cpl):
                file.write_text("", encoding="utf-8")
            result = self.plan("assembly-check", bom, "--cpl", cpl, "--exclude", "R2,R3")
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["level"], "L0")
            self.assertEqual(report["inputs"], [str(bom), str(cpl)])
            self.assertEqual(report["outputs"], [])
            self.assertIn("--exclude=R2,R3", report["parameters"])

            output = root / "derived" / "archive.csv"
            result = self.plan("bom-archive", bom, "--output", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["level"], "L2")
            self.assertEqual(report["outputs"], [str(output)])
            self.assertFalse(output.parent.exists())

    def test_native_runners_report_isolated_l2_output_without_launching(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for command, name in (("kicad-native-check", "test.kicad_pcb"), ("spice-run", "test.json")):
                with self.subTest(command=command):
                    source = root / name
                    source.write_text("", encoding="utf-8")
                    output = root / command
                    result = self.plan(command, source, "--output-dir", output, "--timeout", 5)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    plan = json.loads(result.stdout)
                    self.assertEqual(plan["level"], "L2")
                    self.assertEqual(plan["outputs"], [str(output)])
                    self.assertEqual(plan["inputs"], [str(source)])
                    self.assertFalse(output.exists())
                    output.mkdir()
                    self.assertEqual(self.plan(command, source, "--output-dir", output).returncode, 2)


if __name__ == "__main__":
    unittest.main()
