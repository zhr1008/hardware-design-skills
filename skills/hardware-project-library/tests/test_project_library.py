import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "project_library.py"
spec = importlib.util.spec_from_file_location("project_library", SCRIPT)
library = importlib.util.module_from_spec(spec)
spec.loader.exec_module(library)


class ProjectLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources = self.root / "source"
        self.sources.mkdir()
        (self.sources / "design.txt").write_text("12 V reference circuit; not physically tested", encoding="utf-8")
        self.dest = self.root / "private-library"

    def record(self):
        return {"id": "charger-v1", "title": "充电 power-path", "revision": "v1",
                "source_root": str(self.sources), "source": {"kind": "company", "usage_basis": "User-provided test fixture"},
                "files": [{"id": "design", "path": "design.txt", "role": "documentation"}],
                "tags": ["charging"], "conditions": {"vin_v": 12},
                "evidence": {"schematic": {"status": "PASS", "file_ids": ["design"]},
                             "component_selection": {"status": "FAIL", "file_ids": ["design"], "note": "Known mismatch"}}}

    def test_register_search_and_failures_remain_separate(self):
        library.register(self.dest, self.record())
        result = library.verify(self.dest, "charger-v1")
        self.assertTrue(result["integrity_ok"])
        self.assertEqual(result["declared_failures"], ["component_selection"])
        self.assertEqual(result["evidence_status"]["bringup"], "NOT_TESTED")
        self.assertEqual(library.search(self.dest, "充电 power-path")["total_matches"], 1)

    def test_changed_and_missing_sources_are_detected(self):
        library.register(self.dest, self.record())
        (self.sources / "design.txt").write_text("changed", encoding="utf-8")
        self.assertFalse(library.verify(self.dest, "charger-v1")["integrity_ok"])
        (self.sources / "design.txt").unlink()
        self.assertFalse(library.verify(self.dest, "charger-v1")["integrity_ok"])

    def test_records_are_immutable_and_revisioned(self):
        original = library.register(self.dest, self.record())
        before = original.read_bytes()
        with self.assertRaises(ValueError): library.register(self.dest, self.record())
        self.assertEqual(original.read_bytes(), before)
        newer = self.record(); newer.update(id="charger-v2", revision="v2", supersedes="charger-v1")
        library.register(self.dest, newer)
        self.assertEqual(library.read_record(self.dest, "charger-v2")["supersedes"], "charger-v1")

    def test_traversal_absolute_and_unknown_evidence_are_rejected(self):
        for path in ["../outside", str(self.sources / "design.txt"), "C:outside"]:
            item = self.record(); item["files"][0]["path"] = path
            with self.assertRaises(ValueError): library.register(self.dest, item)
        item = self.record(); item["evidence"]["schematic"]["file_ids"] = ["missing"]
        with self.assertRaises(ValueError): library.register(self.dest, item)

    def test_links_are_not_followed(self):
        link = self.sources / "linked.txt"
        try: link.symlink_to(self.sources / "design.txt")
        except OSError as exc: self.skipTest(f"Symlinks unavailable: {exc}")
        item = self.record(); item["files"][0]["path"] = "linked.txt"
        with self.assertRaises(ValueError): library.register(self.dest, item)

    def test_unsubstantiated_pass_and_public_capture_rejected(self):
        item = self.record(); item["evidence"]["schematic"]["file_ids"] = []
        with self.assertRaises(ValueError): library.register(self.dest, item)
        item = self.record(); item["visibility"] = "public"
        with self.assertRaises(ValueError): library.register(self.dest, item)

    def test_corrupted_record_is_reported(self):
        path = library.register(self.dest, self.record())
        record = json.loads(path.read_text(encoding="utf-8")); record["revision"] = "invented"
        path.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaises(ValueError): library.verify(self.dest, "charger-v1")
        self.assertTrue(library.search(self.dest, "")["invalid_records"])

    def test_claims_require_scope_and_evidence(self):
        item = self.record(); item["claims"] = [{"statement": "All boards should use this", "classification": "project_rule", "file_ids": ["design"]}]
        with self.assertRaises(ValueError): library.register(self.dest, item)

    def test_cli_uses_persisted_record_and_detects_drift(self):
        request = self.root / "spec.json"; request.write_text(json.dumps(self.record(), ensure_ascii=False), encoding="utf-8")
        def run(*args):
            return subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), *args], capture_output=True, text=True, encoding="utf-8")
        result = run("register", "--library", str(self.dest), "--spec", str(request))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(run("verify", "--library", str(self.dest), "--id", "charger-v1").returncode, 0)
        (self.sources / "design.txt").write_text("drift", encoding="utf-8")
        result = run("verify", "--library", str(self.dest), "--id", "charger-v1")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertFalse(json.loads(result.stdout)["integrity_ok"])


if __name__ == "__main__":
    unittest.main()
