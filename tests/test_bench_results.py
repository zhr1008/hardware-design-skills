from hashlib import sha256
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


TOOL = Path(__file__).resolve().parents[1] / "skills/hardware-design-review/scripts/check_bench_results.py"
FIRMWARE = sha256(b"fixture firmware bytes").hexdigest()
FIELDS = "test_id,value,unit,board_id,hardware_revision,firmware_sha256\n"


class BenchResultsTest(unittest.TestCase):
    def setUp(self):
        self.spec = {
            "schema_version": 1, "limit_set_id": "limits-r3",
            "board_id": "board-1", "hardware_revision": "A2", "firmware_sha256": FIRMWARE,
            "tests": {
                "rail": {"unit": "V", "min": "3.135", "max": "3.465"},
                "boot": {"unit": "ms", "max": 500},
            },
        }

    def evaluate(self, records, raw_spec=None, fields=FIELDS):
        limits = json.dumps(self.spec).encode() if raw_spec is None else raw_spec
        measurements = (fields + "".join(records)).encode()
        with tempfile.TemporaryDirectory() as folder:
            limits_path = Path(folder) / "limits.json"
            table_path = Path(folder) / "measurements.csv"
            limits_path.write_bytes(limits)
            table_path.write_bytes(measurements)
            result = subprocess.run(
                [sys.executable, "-X", "utf8", str(TOOL), "--limits", str(limits_path),
                 "--measurements", str(table_path)],
                capture_output=True, encoding="utf-8", check=False, timeout=15,
            )
        report = json.loads(result.stdout)
        self.assertEqual(report["sha256"], {
            "limits": sha256(limits).hexdigest(), "measurements": sha256(measurements).hexdigest(),
        })
        return result.returncode, report, {row["test_id"]: row for row in report["results"]}

    def row(self, test, value, unit, board="board-1", firmware=FIRMWARE):
        return f"{test},{value},{unit},{board},A2,{firmware}\n"

    def test_exact_decimal_endpoints_pass_with_provenance(self):
        status, report, rows = self.evaluate([self.row("rail", "3.135", "V"),
                                             self.row("boot", "500", "ms", firmware=FIRMWARE.upper())])
        self.assertEqual((status, report["status"], report["limit_set_id"]), (0, "pass", "limits-r3"))
        self.assertEqual(report["board"]["firmware_sha256"], FIRMWARE)
        self.assertEqual(rows["rail"]["lines"], [2])
        self.assertEqual(rows["rail"]["value"], "3.135")

    def test_fail_and_missing_are_visible_in_same_report(self):
        status, report, rows = self.evaluate([self.row("rail", "3.46500000000000000000001", "V")])
        self.assertEqual((status, report["status"]), (1, "fail"))
        self.assertEqual((rows["rail"]["status"], rows["boot"]["status"]), ("fail", "missing"))

    def test_empty_data_with_valid_header_is_missing(self):
        status, report, rows = self.evaluate([])
        self.assertEqual((status, report["status"], report["counts"]["missing"]), (3, "missing", 2))
        self.assertEqual(rows["boot"]["lines"], [])

    def test_units_identity_duplicates_and_nonfinite_measurements_are_invalid(self):
        rail = self.row("rail", "3.3", "V")
        cases = {
            "unit": ([self.row("rail", "3300", "mV")], "单位"),
            "board": ([self.row("rail", "3.3", "V", board="board-2")], "板号"),
            "firmware": ([self.row("rail", "3.3", "V", firmware="0" * 64)], "固件摘要"),
            "duplicate": ([rail, rail], "重复"),
            "nonfinite": ([self.row("rail", "Infinity", "V")], "有限十进制"),
        }
        for case, (records, reason) in cases.items():
            with self.subTest(case=case):
                status, report, rows = self.evaluate(records)
                self.assertEqual((status, report["status"], rows["rail"]["status"]), (2, "invalid", "invalid"))
                self.assertIn(reason, rows["rail"]["reason"])

    def test_bad_limits_and_unknown_test_do_not_pass(self):
        status, report, _ = self.evaluate([self.row("alternate", "3.3", "V")])
        self.assertEqual((status, report["issues"][0]["test_id"]), (2, "alternate"))
        self.spec["tests"]["rail"]["min"] = "3.5"
        status, report, _ = self.evaluate([])
        self.assertEqual(status, 2)
        self.assertIn("min 大于 max", report["issues"][0]["reason"])
        for raw in (b'{"schema_version": 1, "schema_version": 1}', b'{"schema_version": NaN}'):
            status, report, _ = self.evaluate([], raw_spec=raw)
            self.assertEqual((status, report["status"]), (2, "invalid"))

    def test_synthetic_waveform_and_can_log_metrics_feed_existing_contract(self):
        # Fixture acquisition data already scaled and restricted to the test window.
        voltage_samples = tuple(map(Decimal, ("-1.5", "-1", "0")))
        can_seconds = tuple(map(Decimal, ("0", "0.010", "0.030")))
        vpp = max(voltage_samples) - min(voltage_samples)
        gap_ms = max(b - a for a, b in zip(can_seconds, can_seconds[1:])) * 1000
        self.spec["tests"] = {"screen_vpp": {"unit": "V", "max": "1.5"},
                              "can_max_gap": {"unit": "ms", "max": "20"}}
        scope = self.row("screen_vpp", vpp, "V")
        can = self.row("can_max_gap", gap_ms, "ms")
        self.assertEqual(self.evaluate([scope, can])[0], 0)
        self.assertEqual(self.evaluate([scope, self.row("can_max_gap", "20.001", "ms")])[0], 1)
        self.assertEqual(self.evaluate([self.row("screen_vpp", "1500", "mV"), can])[0], 2)
        self.assertEqual(self.evaluate([scope, self.row("can_max_gap", gap_ms, "ms", board="other")])[0], 2)
        self.assertEqual(self.evaluate([scope])[0], 3)


if __name__ == "__main__":
    unittest.main()
