import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "project_library.py"


class ModulePackTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.library = self.root / "modules"
        self.path = self.library / "sample" / "0.1.0" / "module.json"
        self.path.parent.mkdir(parents=True)
        self.fixture = self.path.parent / "schematic.kicad_sch.fixture"
        self.fixture.write_bytes(b"synthetic schematic")
        self.manifest = {
            "schema": "hardware-module-pack-v1", "module_id": "sample", "revision": "0.1.0",
            "variant": "single", "function": "adc-front-end", "scope": "prototype", "tags": ["sar", "sampling"],
            "provenance": {"kind": "original", "sources": [], "license": "MIT", "distribution": "public-original"},
            "interfaces": [{"id": "IN", "role": "analog-input", "direction": "input",
                            "reference_domain": "AGND", "mapping": {"net": "INPUT"}}],
            "conditions": {
                "source_ohm": {"unit": "ohm", "min": 0, "max": 100, "required": True},
                "mode": {"enum": ["normal", "fast"], "required": False},
                "supply": {"unit": "V", "min": 0, "max": 5, "required": False, "hard": True},
            },
            "parts": [{"ref": "R1", "role": "filter", "manufacturer": "Synthetic", "mpn": "TEST-123",
                       "package": "0603", "pin_map": {"1": "INPUT", "2": "OUT"}, "dnp": False}],
            "files": {"circuit": {"role": "schematic", "relative_path": self.fixture.name,
                                  "sha256": hashlib.sha256(self.fixture.read_bytes()).hexdigest(),
                                  "license": "MIT", "materialize_as": "schematic.kicad_sch"}},
            "evidence": {slot: {"status": "pending", "receipt": None}
                         for slot in ("saved_eda", "calculation", "simulation", "bench")},
        }
        self.write_manifest()

    def write_manifest(self):
        self.path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def run_cli(self, command, *args, request=None, code=0):
        arguments = ["--library", str(self.library), *map(str, args)]
        if request is not None:
            path = self.root / "request.json"
            path.write_text(json.dumps(request), encoding="utf-8")
            arguments += ["--conditions", str(path)]
        result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(SCRIPT), command, *arguments],
                                capture_output=True, encoding="utf-8", timeout=10)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def fit(self, values=None, code=0, **request):
        return self.run_cli("module-fit", "--manifest", self.path,
                            request={"conditions": values or {}, **request}, code=code)

    def test_minimal_contract_without_optional_tables(self):
        found = self.run_cli("module-search", "--query", "sar adc-front-end")
        self.assertEqual(found["total_matches"], 1)
        self.assertEqual(self.run_cli("module-search", "--query", "reference_domain")["total_matches"], 0)
        candidate, = found["matches"]
        self.assertEqual(candidate["module"], {
            "module_id": "sample", "revision": "0.1.0", "variant": "single",
            "manifest_sha256": hashlib.sha256(self.path.read_bytes()).hexdigest(),
        })
        self.assertEqual(candidate["manifest"], "sample/0.1.0/module.json")
        self.assertEqual(candidate["fit"]["status"], "needs_input")
        result = self.run_cli("module-fit", "--manifest", candidate["manifest"],
                              "--manifest-sha256", candidate["module"]["manifest_sha256"],
                              request={"conditions": {"source_ohm": {"value": 50, "unit": "ohm"}}})
        self.assertEqual(result["status"], "fits")
        self.assertEqual(result["forbidden_combinations"]["status"], "undeclared")
        self.assertEqual(result["layout_constraints"]["status"], "undeclared")
        self.assertEqual(result["parts"][0]["mpn"], "TEST-123")
        self.assertEqual({entry["status"] for entry in result["evidence"].values()}, {"pending"})
        self.assertFalse(self.fixture.with_name("schematic.kicad_sch").exists())

    def test_numeric_endpoints_missing_values_units_and_hard_bounds(self):
        for raw, expected in [
            ({"value": 0, "unit": "ohm"}, "fits"),
            ({"value": 100, "unit": "ohm"}, "fits"),
            ({"value": 101, "unit": "ohm"}, "recheck"),
            ({"value": 1, "unit": "kohm"}, "needs_input"),
            (None, "needs_input"),
        ]:
            with self.subTest(raw=raw):
                result = self.fit({"source_ohm": raw} if raw is not None else {})
                self.assertEqual(result["status"], expected)
        result = self.fit({"source_ohm": {"value": 5, "unit": "ohm"},
                           "supply": {"value": 5.01, "unit": "V"}}, code=1)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["conditions"]["supply"]["status"], "outside")

    def test_forbidden_combinations_are_matched_clear_or_unknown(self):
        self.manifest["forbidden_combinations"] = [
            {"id": "fast-source", "reason": "fast source boundary",
             "when": {"mode": {"equals": "fast"}, "source_ohm": {"unit": "ohm", "min": 80, "max": 100}}}
        ]
        self.manifest["layout_constraints"] = [
            {"id": "return", "object": "IN", "criterion": "continuous ground return",
             "when": {"mode": {"equals": "fast"}}, "evidence": ["circuit"]}
        ]
        self.write_manifest()
        for mode, ohm, expected in [("fast", 80, "matched"), ("normal", 80, "clear"),
                                     (None, 80, "unknown"), (None, 10, "clear")]:
            with self.subTest(mode=mode, ohm=ohm):
                values = {"source_ohm": {"value": ohm, "unit": "ohm"}}
                if mode is not None:
                    values["mode"] = mode
                result = self.fit(values, code=int(expected == "matched"))
                self.assertEqual(result["forbidden_combinations"]["results"][0]["status"], expected)
                self.assertEqual(result["layout_constraints"]["results"][0]["applicability"],
                                 {None: "unknown", "normal": "does_not_apply", "fast": "applies"}[mode])
                self.assertEqual(result["status"], {"matched": "blocked", "clear": "fits", "unknown": "needs_input"}[expected])

    def test_reference_domain_mismatch_blocks_required_interface(self):
        values = {"source_ohm": {"value": 25, "unit": "ohm"}}
        result = self.fit(values, interfaces=[{"id": "IN", "direction": "input", "reference_domain": "AGND"}])
        self.assertEqual(result["interfaces"][0]["status"], "match")
        result = self.fit(values, code=1, interfaces=[{"id": "IN", "direction": "input", "reference_domain": "DGND"}])
        self.assertEqual(result["interfaces"][0]["differences"], ["reference_domain"])
        self.assertEqual(result["status"], "blocked")

    def test_explicit_eco_tracks_dependencies_and_retains_applicable_evidence(self):
        standalone = {"status": "pass", "receipt": "circuit", "conditions": {}}
        source_dependent = {**standalone, "conditions": {"source_ohm": {"unit": "ohm", "min": 0, "max": 100}}}
        self.manifest["evidence"].update(saved_eda=standalone, calculation=source_dependent, simulation=source_dependent)
        examples = [
            ("source_ohm", "filter", {"value": 50, "unit": "ohm"}, {"value": 120, "unit": "ohm"},
             {"unit": "ohm", "min": 0, "max": 150}, ["wcca"], ["calculation", "simulation"], ["saved_eda"]),
            ("R1", "part", "TEST-123", "TEST-456", {"enum": ["TEST-123", "TEST-456"]},
             ["component-qualification"], ["saved_eda"], ["calculation", "simulation"]),
            ("sample_window", "firmware", {"value": 1, "unit": "us"}, {"value": 2, "unit": "us"},
             {"unit": "us", "min": 1, "max": 3}, ["adc-timing"], ["simulation"], ["saved_eda", "calculation"]),
        ]
        self.manifest["allowed_changes"] = [
            {"parameter": key, "change_kind": kind, **bounds} for key, kind, _, _, bounds, _, _, _ in examples
            if key != "R1"
        ]
        self.manifest["change_impact"] = [
            {"parameter": key, "change_kind": kind, "checks": checks, "invalidates": slots, "reason": key}
            for key, kind, _, _, _, checks, slots, _ in examples
        ]
        self.write_manifest()
        for key, kind, before, after, _, checks, slots, remaining in examples:
            with self.subTest(key=key):
                values = {} if key == "source_ohm" else {"source_ohm": {"value": 50, "unit": "ohm"}}
                result = self.fit(values, changes=[{"object": key, "kind": kind, "before": before, "after": after}])
                self.assertEqual(result["status"], "recheck")
                impact = result["impact"]
                self.assertEqual(impact["changes"], [{"object": key, "kind": kind, "variant": "single",
                                                      "before": before, "after": after}])
                self.assertEqual(impact["local_recheck"][0]["checks"], checks)
                self.assertEqual(impact["local_recheck"][0]["allowance"], "undeclared" if key == "R1" else "within")
                self.assertEqual(impact["invalidated_evidence"], slots)
                self.assertEqual(impact["reuse_candidates"], remaining)

    def test_incomplete_optional_eco_rules_trigger_unknown_impact(self):
        result = self.fit({"source_ohm": {"value": 125, "unit": "ohm"}})
        self.assertEqual(result["status"], "recheck")
        change, = result["impact"]["changes"]
        self.assertEqual(change["kind"], "unknown")
        self.assertEqual(change["before"], {"unit": "ohm", "min": 0, "max": 100})
        self.assertEqual(change["after"], {"unit": "ohm", "value": 125})
        self.assertEqual(result["impact"]["local_recheck"][0]["allowance"], "undeclared")
        self.assertEqual(set(result["impact"]["invalidated_evidence"]), set(self.manifest["evidence"]))

    def test_outside_allowance_keeps_the_named_impact_for_unrelated_evidence(self):
        self.manifest["allowed_changes"] = [{"parameter": "source_ohm", "change_kind": "filter",
                                             "unit": "ohm", "min": 0, "max": 100}]
        self.manifest["change_impact"] = [{"parameter": "source_ohm", "change_kind": "filter",
                                           "checks": ["wcca"], "invalidates": ["calculation"], "reason": "RC settling"}]
        self.manifest["evidence"]["saved_eda"] = {"status": "pass", "receipt": "circuit", "conditions": {}}
        self.write_manifest()
        result = self.fit({"source_ohm": {"value": 101, "unit": "ohm"}})
        self.assertEqual(result["status"], "recheck")
        self.assertEqual(result["impact"]["changes"][0]["kind"], "filter")
        self.assertEqual(result["impact"]["local_recheck"][0]["allowance"], "outside")
        self.assertEqual(result["impact"]["reuse_candidates"], ["saved_eda"])

    def test_declared_evidence_scope_is_not_inferred_from_file_hash(self):
        self.manifest["evidence"].update(
            saved_eda={"status": "pass", "receipt": "circuit"},
            calculation={"status": "pass", "receipt": "circuit",
                         "conditions": {"source_ohm": {"unit": "ohm", "min": 0, "max": 50}}},
            simulation={"status": "fail", "receipt": "circuit", "conditions": {}},
        )
        self.write_manifest()
        result = self.fit({"source_ohm": {"value": 75, "unit": "ohm"}})
        self.assertEqual(result["evidence"]["saved_eda"]["coverage"], "undeclared")
        self.assertEqual(result["evidence"]["calculation"]["coverage"], "out_of_scope")
        self.assertEqual(result["evidence"]["simulation"]["status"], "fail")
        self.assertEqual(result["impact"]["reuse_candidates"], [])

    def test_detects_drift_and_manifest_identity_pin(self):
        original = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.manifest["scope"] = "changed"
        self.write_manifest()
        pin_error = self.run_cli("module-fit", "--manifest", self.path, "--manifest-sha256", original, code=2)
        self.assertIn("manifest SHA-256 mismatch", pin_error["error"])
        self.fixture.write_bytes(b"edited")
        report = self.run_cli("module-search", "--query", "sar", code=1)
        self.assertFalse(report["matches"])
        self.assertIn("SHA-256 mismatch", report["invalid_modules"][0]["error"])

    def test_rejects_paths_unknown_file_license_and_unregistered_receipts(self):
        entry = self.manifest["files"]["circuit"]
        for path in ("../outside", "C:outside", "/absolute", "same\\outside", "nested/../schematic.kicad_sch.fixture"):
            with self.subTest(path=path):
                entry["relative_path"] = path
                self.write_manifest()
                self.assertIn("normalized relative path", self.fit(code=2)["error"])
        entry["relative_path"] = self.fixture.name
        entry["license"] = "unknown"
        self.write_manifest()
        self.assertIn("unknown license", self.fit(code=2)["error"])
        entry["license"] = "MIT"
        self.manifest["evidence"]["saved_eda"] = {"status": "pass", "receipt": "unregistered"}
        self.write_manifest()
        self.assertIn("registered receipt", self.fit(code=2)["error"])

    def test_rejects_linked_files_and_library_subdirectories(self):
        outside = self.root / self.fixture.name
        self.fixture.replace(outside)
        try:
            self.fixture.symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"Symlinks unavailable: {exc}")
        self.assertIn("linked", self.fit(code=2)["error"])
        self.fixture.unlink()
        outside.replace(self.fixture)
        linked = self.library / "linked"
        linked.symlink_to(self.path.parent.parent, target_is_directory=True)
        report = self.run_cli("module-search", "--query", "sar", code=1)
        self.assertEqual(report["total_matches"], 1)
        self.assertEqual(report["invalid_modules"], [{"manifest": "linked", "error": "linked module path"}])

    def test_reference_only_unknown_provenance_cannot_be_adopted(self):
        self.manifest["files"] = {}
        self.manifest["provenance"].update(distribution="reference-only", license="unknown")
        self.write_manifest()
        result = self.fit({"source_ohm": {"value": 30, "unit": "ohm"}}, code=1)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["issues"][0]["field"], "provenance")
