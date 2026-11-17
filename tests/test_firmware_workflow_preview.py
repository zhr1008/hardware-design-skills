"""Exercise the published firmware preview without toolchain or probe dependencies."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


RUNNER = Path(__file__).resolve().parents[1] / "skills" / "workflow" / "scripts" / "workflow_runner.py"


class WorkflowPreview(unittest.TestCase):
    def run_preview(self, *arguments):
        return subprocess.run(
            [sys.executable, "-X", "utf8", str(RUNNER), *arguments],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )

    def test_single_build_lists_only_build(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "CMakeLists.txt").write_text("# sample", encoding="utf-8")
            result = self.run_preview("--project", directory, "--build-system", "cmake")
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "planned")
            self.assertFalse(report["executed"])
            self.assertEqual([step["step"] for step in report["steps"]], ["build"])

    def test_monitor_requires_device_and_serial_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "platformio.ini").write_text("[env:example]\n", encoding="utf-8")
            result = self.run_preview(
                "--project", directory, "--build-system", "platformio", "--target", "example",
                "--run", "build-flash-monitor", "--dry-run",
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            report = json.loads(result.stdout)
            self.assertFalse(report["executed"])
            self.assertEqual([step["step"] for step in report["steps"]], ["build", "flash", "monitor"])
            self.assertEqual([len(step["missing_inputs"]) for step in report["steps"]], [0, 2, 2])


if __name__ == "__main__":
    unittest.main()
