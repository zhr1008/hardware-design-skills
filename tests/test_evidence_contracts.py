import hashlib
from importlib.util import find_spec
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
HARDWARE = SKILLS / "hardware" / "scripts"
sys.path.insert(0, str(HARDWARE))

from evidence_adapter import artifact, envelope, validate


def invoke(script, *args):
    process = subprocess.run(
        [sys.executable, "-X", "utf8", "-B", str(script), *map(str, args)],
        check=False, capture_output=True, encoding="utf-8",
    )
    return process.returncode, json.loads(process.stdout)


class EvidenceContracts(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name)

    def json_file(self, name, value):
        path = self.work / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    @unittest.skipUnless(find_spec("pymupdf"), "需要 PyMuPDF 后端核对真实 PDF 页数")
    def test_component_facts_can_verify_declared_pages_against_same_pdf_bytes(self):
        import pymupdf

        script = SKILLS / "ee-datasheet-master/scripts/validate_component_facts.py"
        pdf = self.work / "datasheet.pdf"
        with pymupdf.open() as document:
            document.new_page()
            document.save(pdf)
        identity = {"manufacturer": "Fixture Co.", "mpn": "FIX-01", "package": "QFN-8"}
        record = {
            "schema": "hardware-component-facts-v1", "identity": identity,
            "datasheet": {"kind": "manufacturer_datasheet", "revision": "A1",
                          "url": "https://example.invalid/fixture.pdf", "applies_to": [identity],
                          "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest()},
            "facts": [{"id": "pin1", "category": "pin", "status": "supported", "conditions": [],
                       "value": {"number": "1", "name": "GND", "role": "ground"},
                       "source": {"page": 1, "location": "Pin table"}}],
        }
        facts = self.json_file("pin-facts.json", record)
        code, result = invoke(script, facts, "--pdf", pdf, "--verify-pages")
        self.assertEqual(code, 0)
        self.assertEqual(result["pdf_page_count"], 1)
        record["facts"][0]["source"]["page"] = 2
        self.json_file("pin-facts.json", record)
        self.assertEqual(invoke(script, facts, "--pdf", pdf)[0], 0)
        code, result = invoke(script, facts, "--pdf", pdf, "--verify-pages")
        self.assertEqual(code, 2)
        self.assertIn("超出原件 1 页", result["error"])

    def test_engaged_check_requires_artifact_and_stable_mutation(self):
        with self.assertRaises(ValueError):
            envelope(backend="checker", stage="saved_artifact", verification="pass",
                     native={}, executed=["measure"])
        report = self.json_file("artifact.json", {})
        with self.assertRaises(ValueError):
            envelope(backend="checker", stage="saved_artifact", verification="no_reported_findings",
                     native={}, executed=["measure"], inputs={"input": artifact(report)},
                     mutation="outcome_unknown")
        allowed = envelope(
            backend="checker", stage="saved_artifact", verification="not_evaluated",
            native={}, execution="timed_out", mutation="outcome_unknown",
        )
        validate(allowed)

    def test_legacy_kicad_report_scope_and_formal_missing(self):
        report = self.json_file("erc.json", {
            "$schema": "https://schemas.kicad.org/erc.v1.json", "source": "model.kicad_sch",
            "date": "2026-01-01", "kicad_version": "10.0.1",
            "included_severities": ["error", "warning", "exclusion"],
            "sheets": [{"path": "/", "violations": []}],
        })
        script = SKILLS / "pcb-layout-review/scripts/check_kicad_report.py"
        self.assertEqual(invoke(script, report)[1]["status"], "no_reported_findings")
        code, formal = invoke(script, "--formal", report)
        self.assertEqual(code, 0)
        self.assertEqual(formal["verification_status"], "no_reported_findings")
        self.assertEqual(formal["checks_executed"], ["report_readback"])
        self.assertEqual(formal["checks_skipped"][0]["check"], "native_erc_drc")
        self.assertEqual(formal["inputs"]["report"]["sha256"], hashlib.sha256(report.read_bytes()).hexdigest())
        self.assertEqual(invoke(script, "--formal", self.work / "missing.json")[1]["verification_status"], "missing")

    def test_evidence_reader_detects_byte_drift_and_missing_artifacts(self):
        source = self.json_file("input.json", {"version": "A"})
        report = self.json_file("report.json", {})
        evidence = self.json_file("evidence.json", envelope(
            backend="fixture", stage="simulation", verification="pass", native={}, executed=["measure"],
            inputs={"source": artifact(source)}, outputs={"report": artifact(report)},
        ))
        script = HARDWARE / "evidence_adapter.py"
        args = ("validate", evidence, "--verify-artifacts")
        self.assertEqual(invoke(script, *args)[1]["status"], "artifacts_match")
        self.json_file(source.name, {"version": "B"})
        report.unlink()
        code, result = invoke(script, *args)
        self.assertEqual(code, 2)
        self.assertEqual({row["role"]: row["status"] for row in result["artifacts"]},
                         {"inputs.source": "changed", "outputs.report": "missing"})
        self.assertEqual(invoke(script, "validate", evidence)[1]["status"], "valid_format")

    def test_release_bare_manifest_and_malformed_manifest_use_same_entry(self):
        script = SKILLS / "release-pcba-fabrication/scripts/validate_release_manifest.py"
        example = SKILLS / "release-pcba-fabrication/assets/release-manifest.example.json"
        legacy, prior = invoke(script, example)
        code, formal = invoke(script, "--formal", example)
        self.assertEqual(code, legacy)
        self.assertEqual(formal["native"], prior)
        self.assertEqual(formal["inputs"]["manifest"]["sha256"], hashlib.sha256(example.read_bytes()).hexdigest())
        corrupt = self.work / "broken.json"
        corrupt.write_text("{", encoding="utf-8")
        self.assertEqual(invoke(script, "--formal", corrupt)[1]["verification_status"], "invalid")

    def test_bench_missing_and_invalid_are_not_ordinary_fail(self):
        identity = {"board_id": "TEST", "hardware_revision": "A", "firmware_sha256": "a" * 64}
        limits = self.json_file("limits.json", {
            "schema_version": 1, "limit_set_id": "L0", **identity,
            "tests": {"rail": {"unit": "V", "min": 3, "max": 3.6}},
        })
        measurements = self.work / "measurements.csv"
        measurements.write_text(
            "test_id,value,unit,board_id,hardware_revision,firmware_sha256\n"
            f"rail,3.3,V,TEST,A,{'a' * 64}\n", encoding="utf-8",
        )
        script = HARDWARE / "evidence_adapter.py"
        args = ("bench", limits, "--measurements", measurements)
        code, formal = invoke(script, *args)
        self.assertEqual(code, 0)
        self.assertEqual(formal["checks_executed"], ["compare:rail"])
        self.assertEqual(formal["native"]["board"], identity)
        self.assertEqual(formal["verification_status"], "pass")
        measurements.write_text("not,the,right,header\n", encoding="utf-8")
        self.assertEqual(invoke(script, *args)[1]["verification_status"], "invalid")
        measurements.unlink()
        code, formal = invoke(script, *args)
        self.assertEqual(code, 3)
        self.assertEqual(formal["verification_status"], "missing")

    def test_doctor_distinguishes_installation_from_provided_call_receipt(self):
        observed = {
            "type": "object", "required": ["identifier"], "properties": {
                "identifier": {"type": "string"}, "refresh": {"type": "boolean"},
                "include_procurement": {"type": "boolean"},
            },
        }
        signature = hashlib.sha256(json.dumps(observed, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        receipt = {"tool": "szlcsc_get_part", "status": "success", "input_schema_sha256": signature}
        path = self.json_file("observed.json", {
            "schema": "hardware-runtime-observation-v1",
            "backends": {"components": {
                "observed_at": "2026-01-01T00:00:00Z", "tools": {"szlcsc_get_part": observed},
                "read_only_call": receipt,
            }},
        })
        _, report = invoke(
            HARDWARE / "backend_doctor.py", "--backend", "kicad-cli", "--backend", "components",
            "--kicad-cli", self.work / "uninstalled.exe", "--runtime-observation", path,
        )
        self.assertFalse(report["backends"]["kicad-cli"]["installed"])
        self.assertIsNone(report["backends"]["kicad-cli"]["connected"])
        self.assertTrue(report["backends"]["components"]["connected"])
        self.assertTrue(report["backends"]["components"]["call_verified"])
        self.assertFalse(report["backends"]["components"]["current_session_probed"])
        mismatched = json.loads(path.read_bytes())
        mismatched["backends"]["components"]["tools"]["szlcsc_get_part"]["properties"]["identifier"]["type"] = "integer"
        self.json_file(path.name, mismatched)
        report = invoke(HARDWARE / "backend_doctor.py", "--backend", "components", "--runtime-observation", path)[1]
        self.assertFalse(report["backends"]["components"]["contract_compatible"])
        self.assertFalse(report["backends"]["components"]["call_verified"])

    def test_component_evidence_is_bound_to_package_full_mpn_and_pdf(self):
        script = SKILLS / "ee-datasheet-master/scripts/validate_component_facts.py"
        pdf = self.work / "fixture.pdf"
        pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
        identity = {"manufacturer": "Fixture Co.", "mpn": "FIX-01Q1", "package": "QFN-8"}
        fact = {
            "id": "supply", "category": "recommended_operating", "status": "supported",
            "conditions": ["-40 C <= Ta <= 85 C"],
            "value": {"unit": "V", "min": 2, "typ": None, "max": 3.6},
            "source": {"page": 2, "location": "Table 2, supply voltage row"},
        }
        record = {
            "schema": "hardware-component-facts-v1", "identity": identity.copy(),
            "datasheet": {
                "kind": "manufacturer_datasheet", "revision": "A1", "url": "https://example.invalid/fixture.pdf",
                "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(), "applies_to": [identity.copy()],
            },
            "facts": [fact],
        }
        args = (self.json_file("facts.json", record), "--pdf", pdf)
        code, result = invoke(script, *args, "--expected-mpn", "FIX-01Q1")
        self.assertEqual(code, 0)
        self.assertTrue(result["pdf_digest_verified"])
        self.assertEqual(invoke(script, *args, "--expected-mpn", "FIX-01Q")[0], 2)
        record["datasheet"]["applies_to"][0]["package"] = "SOIC-8"
        self.json_file("facts.json", record)
        self.assertEqual(invoke(script, *args)[0], 2)
        record["datasheet"]["applies_to"][0]["package"] = "QFN-8"
        record["facts"][0] = {**fact, "status": "unknown", "value": None, "conditions": None,
                              "reason": "reported for another revision"}
        self.json_file("facts.json", record)
        code, result = invoke(script, *args)
        self.assertEqual(code, 1)
        self.assertEqual(result["unknown_facts"], ["supply"])
        pdf.write_bytes(b"%PDF-1.5\n%%EOF\n")
        self.assertEqual(invoke(script, *args)[0], 2)
