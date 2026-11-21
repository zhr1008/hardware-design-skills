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

    def test_topology_options_and_sampling_risk_are_scoped_to_forward_design(self):
        for mode in ("plan", "design"):
            with self.subTest(mode=mode):
                result = self.command("start", mode, "--topic", "sampling")
                self.assertEqual(result["prototypes"], ["adc-front-end"])
                self.assertIn("adc-timing", {check["id"] for check in result["required_checks"]})
                self.assertLess(result["phases"].index("knowledge"), result["phases"].index("topology-options"))
                self.assertLess(result["phases"].index("topology-options"), result["phases"].index("decision"))
                self.assertNotIn("module_catalogues", result)
        review = self.command("start", "review", "--topic", "sampling")
        self.assertNotIn("adc-front-end", review["prototypes"])
        self.assertNotIn("topology-options", review["phases"])

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

    def test_sar_module_lookup_at_boundary_and_three_eco_handoffs(self):
        base = {"project": "sar-fixture", "revision": "A", "variant": "lab-board"}
        conditions = {
            "source_ohm": {"value": 50, "unit": "ohm"},
            "acquisition_us": {"value": 2, "unit": "us"},
            "step_v": {"value": 2.5, "unit": "V"},
            "input_cap_pf": {"value": 18, "unit": "pF"},
            "input_mode": "single-ended",
        }
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            request = root / "module-request.json"
            case = root / "case.json"
            changes = root / "change.json"
            case.write_text(json.dumps({"schema": "hardware-engineering-case-v1", "mode": "eco",
                                         "baseline": base, "prototypes": ["adc-front-end"],
                                         "checks": {"adc-timing": {"status": "open"}}}), encoding="utf-8")

            def module(mode, values, edits=()):
                request.write_text(json.dumps({"conditions": values, "changes": list(edits)}), encoding="utf-8")
                response = self.command("start", mode, "--prototype", "adc-front-end", "--module-query",
                                        "adc-front-end", "--module-conditions", str(request))
                catalogue, = response["module_catalogues"]
                match, = catalogue["matches"]
                return match["fit"]

            for mode in ("plan", "design", "eco"):
                fit = module(mode, conditions)
                self.assertEqual(fit["status"], "fits", fit["issues"])
                self.assertIn("simulation", fit["impact"]["reuse_candidates"])
                self.assertEqual(fit["evidence"]["bench"]["status"], "pending")

            variants = (
                ("source_ohm", "filter", {"value": 20, "unit": "ohm"}, conditions["source_ohm"], "filter", True),
                ("R1", "part", "original-resistor", "unqualified-resistor", "part", False),
                ("acquisition_us", "firmware", {"value": 4, "unit": "us"}, conditions["acquisition_us"], "firmware", True),
            )
            for field, kind, before, after, effective_kind, reuse_eda in variants:
                with self.subTest(field=field):
                    fit = module("eco", conditions, [{"object": field, "kind": kind, "before": before,
                                                      "after": after}])
                    self.assertEqual(fit["status"], "recheck")
                    self.assertIn("simulation", fit["impact"]["invalidated_evidence"])
                    self.assertEqual("saved_eda" in fit["impact"]["reuse_candidates"], reuse_eda)
                    proposal, = fit["impact"]["changes"]
                    self.assertEqual(proposal["kind"], effective_kind)
                    changes.write_text(json.dumps({"schema": "hardware-engineering-change-v1", "baseline": base,
                                                    "changes": [{**proposal, "variant": base["variant"]}]}),
                                       encoding="utf-8")
                    affected = self.command("impact", "--case", str(case), "--change", str(changes))
                    self.assertIn("adc-timing", affected["invalidated_baseline_checks"])
                    self.assertTrue(all(item["object"] == field for item in affected["recheck"]))

    def test_plain_start_does_not_trigger_module_lookup(self):
        result = self.command("start", "design", "--intent", "GPIO LED 3.3V 单点限流电阻核算")
        self.assertNotIn("module_catalogues", result)
