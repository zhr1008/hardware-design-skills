import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HARDWARE = Path(__file__).resolve().parents[1] / "skills/hardware"


def run(script, *args):
    return subprocess.run(
        [sys.executable, "-X", "utf8", "-B", str(HARDWARE / "scripts" / script), *args],
        capture_output=True, encoding="utf-8", timeout=15, check=False,
    )


class DesignFlowTest(unittest.TestCase):
    def command(self, *args):
        result = run("design_flow.py", *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_start_covers_cross_domain_candidates_and_intent_boundaries(self):
        design = self.command("start", "design", "--topic", "analog", "--topic", "sampling",
                              "--topic", "filtering", "--rule", "filter-q-gain")
        ids = [rule["id"] for rule in design["candidate_rules"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue({"analog-capacitive-load", "adc-antialias-budget",
                         "adc-acquisition-settling", "filter-q-gain",
                         "filter-high-frequency-stopband"}.issubset(ids))
        self.assertLess(design["phases"].index("knowledge"), design["phases"].index("decision"))
        for mode in ("plan", "review"):
            output = self.command("start", mode)
            self.assertNotIn("implementation", output["phases"])
            self.assertFalse(output["has_seed_rules"])
            self.assertEqual(output["candidate_rules"], [])

    def test_missing_public_text_keeps_rules_and_reports_gap(self):
        output = self.command("basis", "--rule", "filter-q-gain", "--rule", "filter-high-frequency-stopband")
        self.assertEqual(len(output["rules"]), 2)
        page, = output["source_pages"]
        self.assertEqual(page["requested_pdf_page"], 67)
        self.assertEqual(page["status"], "unavailable")
        self.assertNotIn("text", page)

    def test_reads_one_shared_page_only_from_matching_source_version(self):
        rules = json.loads((HARDWARE / "assets/review-knowledge/rules.json").read_text(encoding="utf-8"))
        citation = rules["sources"]["LIBEE21AAFB7FF12E57"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "assets/engineering-library/manifest.json"
            manifest.parent.mkdir(parents=True)
            (root / "scripts").mkdir()
            source = root / "sample.md"
            source.write_text("## PDF page 67\n\nSynthetic reference page for a parser test.\n", encoding="utf-8")
            document = {"id": "LIBEE21AAFB7FF12E57", "title": "Fixture",
                        "reference_file": "sample.md", "source_sha256": citation["source_sha256"]}
            for digest, status in ((citation["source_sha256"], "retrieved"), ("1" * 64, "unavailable")):
                document["source_sha256"] = digest
                manifest.write_text(json.dumps({"schema_version": 1, "documents": [document]}),
                                    encoding="utf-8")
                result = run("knowledge.py", "--library", directory, "build-index", "--replace")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                output = self.command("--library", directory, "basis", "--rule", "filter-q-gain",
                                      "--rule", "filter-high-frequency-stopband")
                page, = output["source_pages"]
                self.assertEqual(page["status"], status)
                if status == "retrieved":
                    self.assertIn("Synthetic reference page", page["text"])
                else:
                    self.assertNotIn("text", page)

    def test_unrecognized_rule_fails_without_hallucinating_an_empty_basis(self):
        result = run("design_flow.py", "basis", "--rule", "absent-rule")
        self.assertEqual(result.returncode, 2)
        self.assertIn("absent-rule", result.stderr)
        self.assertEqual(result.stdout, "")
