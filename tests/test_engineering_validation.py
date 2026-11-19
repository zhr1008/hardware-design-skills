import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "skills/hardware/scripts/engineering_validation.py"


class EngineeringValidationTests(unittest.TestCase):
    def run_check(self, exit_code, *args):
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-B", str(SCRIPT), *map(str, args)],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(exit_code, result.returncode, (result.stdout, result.stderr))
        return json.loads(result.stdout or result.stderr)

    def test_limit_boundary_and_uncertainty(self):
        cases = (
            ("max", "14.2", "1", "15", 2, "indeterminate", "-0.2"),
            ("max", "38.2", "1.4", "40", 0, "within_limit", "0.4"),
            ("min", "6.14", ".08", "6", 0, "within_limit", "0.06"),
            ("min", "7.90", ".05", "8", 1, "outside_limit", "-0.15"),
            ("min", "8.02", ".05", "8", 2, "indeterminate", "-0.03"),
            ("min", "8.05", ".05", "8.00", 0, "within_limit", "0.00"),
        )
        for direction, value, uncertainty, bound, code, status, margin in cases:
            with self.subTest(direction=direction, value=value, bound=bound):
                report = self.run_check(code, "limit", "--direction", direction, "--value", value,
                                        "--uncertainty", uncertainty, "--limit", bound, "--unit", "unit")
                self.assertEqual(status, report["status"])
                self.assertEqual(margin, report["worst_margin"])

    def test_stub_and_junction_against_independent_examples(self):
        slow = self.run_check(0, "rs485-stub", "--rise-ns", 700, "--velocity-factor", ".78", "--length-m", "3.048")
        fast = self.run_check(1, "rs485-stub", "--rise-ns", 7, "--velocity-factor", ".78", "--length-m", "3.048")
        self.assertAlmostEqual(16.3686682068, float(slow["maximum_length_m"]))
        self.assertAlmostEqual(0.163686682068, float(fast["maximum_length_m"]))
        args = ("junction", "--top-c", 104, 108, "--psi-c-per-w", "1.1", "1.5", "--power-w", "2.0", "2.4")
        thermal = self.run_check(2, *args, "--limit-c", 110)
        self.assertEqual("indeterminate", thermal["status"])
        self.assertEqual([106.2, 111.6], list(map(float, thermal["interval"])))
        self.assertEqual("within_limit", self.run_check(0, *args, "--limit-c", "111.6")["status"])

    def test_round_hole_geometry_guard_checks_offset(self):
        args = ("annular-ring", "--hole-max-mm", "1.13", "--offset-max-mm", ".075", "--minimum-ring-mm", ".18")
        first = self.run_check(2, *args, "--pad-min-mm", "1.58")
        self.assertEqual("lower_bound_below_limit", first["status"])
        self.assertEqual("0.150", first["lower_bound_mm"])
        self.assertEqual("0.200", self.run_check(0, *args, "--pad-min-mm", "1.68")["lower_bound_mm"])

    def test_coverage_keeps_unknown_and_missed_in_denominator(self):
        common = b"fault_id,status\nA,detected\nB,detected\nC,detected\nD,detected\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "faults.csv"
            args = ("coverage", "--faults", path, "--minimum-percent", 90)
            for state, lower, upper, code, status in (
                (b"unknown", "80", "100", 2, "indeterminate"),
                (b"missed", "80", "80", 1, "outside_limit"),
                (b"detected", "100", "100", 0, "within_limit"),
            ):
                data = common + b"E," + state + b"\n"
                path.write_bytes(data)
                result = self.run_check(code, *args)
                self.assertEqual(status, result["status"])
                self.assertEqual([lower, upper], result["percent_interval"])
                self.assertEqual(hashlib.sha256(data).hexdigest(), result["csv_sha256"])
            path.write_bytes(common + b"A,missed\n")
            self.assertIn("duplicate fault", self.run_check(2, *args)["error"])
