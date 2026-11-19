"""Exercise the installed CLI boundary with synthetic positive, negative and sentinel inputs."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "skills/hardware/scripts/engineering_checks.py"
CASES = json.loads(
    (ROOT / "tests/fixtures/engineering-models.json").read_text(encoding="utf-8")
)
CODES = {"pass": 0, "fail": 1, "indeterminate": 2}


class EngineeringModelTests(unittest.TestCase):
    def evaluate(self, case, override=None, context=None):
        request = {
            "check": case["check"],
            "context": case["context"] if context is None else context,
            "inputs": {**case["inputs"], **(override or {})},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "request.json"
            path.write_text(json.dumps(request), encoding="utf-8")
            process = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-X",
                    "utf8",
                    str(ENTRY),
                    "evaluate",
                    "--file",
                    str(path),
                ],
                text=True,
                encoding="utf-8",
                capture_output=True,
            )
        return process.returncode, json.loads(process.stdout or process.stderr)

    def test_model_cases_and_missing_context(self):
        for case in CASES:
            for override, context, expected in (
                ({}, case["context"], "pass"),
                (
                    case["counterexample"],
                    case["context"],
                    case["expected_counterexample"],
                ),
                ({}, {}, "indeterminate"),
            ):
                with self.subTest(
                    check=case["check"], expected=expected, context=context
                ):
                    code, report = self.evaluate(case, override, context)
                    self.assertEqual(code, CODES[expected], report)
                    self.assertEqual(report["status"], expected)
                    self.assertIn(case["result_field"], report["result"])
                    self.assertFalse(report["physical_validation"])
                    if not context:
                        self.assertEqual(report["numeric_status"], "pass")
                        self.assertTrue(report["missing_context"])

    def test_known_analytic_values(self):
        results = {case["check"]: self.evaluate(case)[1]["result"] for case in CASES}
        self.assertEqual(results["divider-wcca"]["output_v"], [4.5, 5.5])
        self.assertAlmostEqual(
            results["hot-copper"]["total_drop_v"], 0.09130797, places=7
        )
        self.assertAlmostEqual(results["zero-failure"]["upper_probability"], 0.00299125)
        self.assertAlmostEqual(results["stencil-ratio"]["area_ratio"], 15 / 22)
        self.assertAlmostEqual(results["i2c-pullup"]["window_ohm"][0], 2900 / 3)

    def test_envelope_crossing_depends_on_attainability(self):
        for case in CASES:
            if case["check"] in ("divider-wcca", "tolerance-stack", "i2c-pullup"):
                with self.subTest(check=case["check"]):
                    context = {**case["context"], "corners_reachable": False}
                    code, report = self.evaluate(case, case["counterexample"], context)
                    self.assertEqual((code, report["status"]), (2, "indeterminate"))
        case = next(c for c in CASES if c["check"] == "measurement-guardband")
        self.assertEqual(self.evaluate(case, {"value": 10.2})[0], 2)

    def test_explicitly_inapplicable_or_incomplete_model_stays_pending(self):
        for case in CASES:
            context = {**case["context"], "model_applicable": False}
            self.assertEqual(self.evaluate(case, context=context)[0], 2)
        divider = next(c for c in CASES if c["check"] == "divider-wcca")
        self.assertEqual(self.evaluate(divider, {"load_ohm": 100})[0], 2)
        ports = next(c for c in CASES if c["check"] == "s-passivity")
        self.assertEqual(self.evaluate(ports, context={**ports["context"], "coverage": "full_band"})[0], 2)

    def test_rejects_invalid_model_inputs(self):
        changes = {
            "zero-failure": {"failure_count": True},
            "s-passivity": {"samples": []},
            "stencil-ratio": {"thickness_mm": 0},
            "hot-copper": {"current_a": "NaN"},
        }
        for case in CASES:
            if case["check"] in changes:
                with self.subTest(check=case["check"]):
                    code, report = self.evaluate(case, changes[case["check"]])
                    self.assertEqual((code, report["status"]), (2, "invalid_input"))

    def test_single_point_without_document_wrapper(self):
        process = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ENTRY),
                "evaluate",
                "--check",
                "zero-failure",
                "--assume-model",
                "iid_same_mission_zero_failures",
                "--bounded",
                "--input",
                "sample_count=1000",
                "--input",
                "failure_count=0",
                "--input",
                "target_probability=0.003",
                "--input",
                "confidence=0.95",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["status"], "pass")
