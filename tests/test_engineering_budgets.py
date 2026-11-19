import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "skills/hardware/scripts/engineering_checks.py"


class EngineeringBudgetTests(unittest.TestCase):
    def run_check(self, expected_exit, *args):
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-B", str(SCRIPT), *map(str, args)],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(expected_exit, result.returncode, (result.stdout, result.stderr))
        return json.loads(result.stdout or result.stderr)

    def test_sar_uses_acquisition_window_and_reports_model_bound(self):
        args = ("adc-settling", "--step-v", "2", "--acquisition-s", "1e-6", "--error-budget-v", ".0005",
                "--resistance-ohm", "1000", "--capacitance-f")
        report = self.run_check(0, *args, "100e-12")
        self.assertEqual("within_model_budget", report["status"])
        self.assertAlmostEqual(90.7998595e-6, report["residual_v"], places=12)
        self.assertAlmostEqual(120.568364e-9, report["tau_limit_s"], places=13)
        self.assertEqual("exceeds_model_budget", self.run_check(1, *args, "150e-12")["status"])

    def test_sar_handles_small_step_and_invalid_time(self):
        args = ("adc-settling", "--step-v", ".001", "--error-budget-v", ".002",
                "--resistance-ohm", "1000", "--capacitance-f", "100e-12", "--acquisition-s")
        self.assertIsNone(self.run_check(0, *args, "1e-6")["tau_limit_s"])
        self.assertEqual("invalid_input", self.run_check(2, *args, "0")["status"])

    def test_pdn_reports_observed_exceedance_and_missing_endpoints(self):
        args = ("pdn-target", "--delta-v", ".03", "--delta-i-a", ".6", "--fmin-hz", "1000",
                "--fmax-hz", "1000000")
        self.assertEqual("0.05", self.run_check(0, *args)["target_ohm"])
        cases = (
            ("1000,0.05\n2000,0.035\n1000000,0.049\n", 0, "within_sampled_points"),
            ("1000,0.05\n2000,0.0500000000000000000000000001\n", 1, "sample_limit_exceeded"),
            ("1000,0.05\n2000,0.035\n", 2, "sample_coverage_incomplete"),
            ("1000,0.049\n1e3,0.049\n", 2, "invalid_input"),
        )
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sweep.csv"
            for body, code, status in cases:
                with self.subTest(status=status):
                    data = ("frequency_hz,impedance_ohm\n" + body).encode()
                    path.write_bytes(data)
                    result = self.run_check(code, *args, "--sweep", path)
                    self.assertEqual(status, result["status"])
                    if status != "invalid_input":
                        self.assertEqual(hashlib.sha256(data).hexdigest(), result["sweep_sha256"])


if __name__ == "__main__":
    unittest.main()
