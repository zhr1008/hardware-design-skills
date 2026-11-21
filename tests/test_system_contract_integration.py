"""Exercise the public contract, evidence, stage, and ECO entry points."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_specialist_artifact_guards import RELEASE_SCRIPTS, release_fixture


SKILLS = Path(__file__).resolve().parents[1] / "skills"
FLOW = SKILLS / "hardware/scripts/design_flow.py"
STATE = SKILLS / "manage-pcba-program/scripts/program_state.py"
POLICY = json.loads((SKILLS / "hardware/assets/engineering-policy.json").read_bytes())


class SystemContractTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.workflow = self.root / ".pcba-workflow"
        self.workflow.mkdir()
        self.case_path = self.workflow / "case.json"
        self.contract_path = self.workflow / "system-contract.json"
        self.baseline = {"project": "fixture", "revision": "A", "variant": "sealed"}
        both = {"variants": ["sealed", "vented"]}
        brief = self.write(self.workflow / "product-brief.yaml", {"requirements": {"R_BOOT": "fixture limit"}})
        raw = self.write(self.root / "native.json", {"fixture": "synthetic observed state"})
        self.input_ref = self.ref(raw)
        self.contract = {
            "schema": "hardware-system-contract-v1",
            "baseline": {"project": "fixture", "revision": "A", **both},
            "brief_ref": {**self.ref(brief), "requirements": {"R_BOOT": "/requirements/R_BOOT"}},
            "blocks": {"soc": {"role": "receiver", **both}},
            "ports": {"soc.reset": {"block": "soc", "kind": "timing", "role": "input", "domain": "io", **both}},
            "links": [],
            "conditions": {"boot": {"state": "cold start", "window": "first 10 ms", **both}},
            "criteria": {"sealed-limit": {"requirement": "R_BOOT", "condition": "boot", "point": "soc.reset",
                                           "op": "<=", "limit": 5, "unit": "ms",
                                           "variants": ["sealed"], "allocations": [2, 3]},
                         "vented-limit": {"requirement": "R_BOOT", "condition": "boot", "point": "soc.reset",
                                          "op": "<=", "limit": 6, "unit": "ms", "variants": ["vented"]}},
            "decisions": {"shell": {"statement": "sealed cover and thermal pad arrangement",
                                    "variants": ["sealed"]}},
            "anchors": {"observed": {**self.input_ref, "role": "test-fixture", **both}},
            "dependencies": [{"source": "shell", "target": "sealed-limit", "variants": ["sealed"]},
                             {"source": "sealed-limit", "target": "check:firmware-interface", "variants": ["sealed"]}],
        }
        self.case = {"schema": "hardware-engineering-case-v1", "mode": "plan", "baseline": self.baseline,
                     "artifacts": {"observed": self.input_ref}, "checks": {}, "evidence": {}}
        self.sync()

    def write(self, path, value):
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def ref(self, path):
        return {"path": path.relative_to(self.root).as_posix(), "sha256": sha256(path.read_bytes()).hexdigest()}

    def sync(self):
        self.case["artifacts"]["system_contract"] = self.ref(self.write(self.contract_path, self.contract))
        self.write(self.case_path, self.case)

    def call(self, script, *args, code=0, output=True):
        proc = subprocess.run([sys.executable, "-X", "utf8", "-B", str(script), *map(str, args)],
                              capture_output=True, text=True, encoding="utf-8", timeout=20)
        self.assertEqual(proc.returncode, code, proc.stdout + proc.stderr)
        return json.loads(proc.stdout) if output else proc

    def flow(self, cmd, *args, **kwargs):
        return self.call(FLOW, cmd, "--case", self.case_path, "--root", self.root, *args, **kwargs)

    def assess(self, code=0, target="handoff"):
        return self.flow("assess", "--require-system-contract", "--target", target, code=code)

    def check(self, code=0):
        return self.flow("contract-check", "--contract", self.contract_path, code=code)

    def close_case(self, bound_check="requirements", criterion="sealed-limit", extras=None, *, condition_id="boot"):
        checks = set(POLICY["modes"][self.case["mode"]]) | set(extras or {})
        self.case["checks"].clear()
        self.case["evidence"].clear()
        for name in sorted(checks):
            condition = f"contract:condition:{condition_id}" if name == bound_check else "same sample"
            limit = f"contract:criterion:{criterion}" if name == bound_check else "fixture criterion"
            inputs = {"observed": self.input_ref, **(extras or {}).get(name, {})}
            execution = f"fixture:{name}"
            base = {"schema": "hardware-evidence-envelope-v1", "backend": "test-fixture",
                    "evidence_stage": POLICY["checks"][name]["stages"][0], "execution_status": "completed",
                    "mutation_outcome": "unchanged", "verification_status": "pass", "checks_executed": [execution],
                    "checks_skipped": [], "inputs": inputs, "outputs": {}, "native": {}, "coverage": {}}
            raw_path = self.write(self.root / ("raw-" + name + ".json"), base)
            row = {"status": "pass", "finding": "synthetic test observation", "condition": condition,
                   "criterion": limit, "artifacts": list(inputs), "evidence": [name]}
            self.case["checks"][name] = row
            self.write(self.case_path, self.case)
            bound = self.flow("bind", "--check", name, "--condition", condition, "--criterion", limit,
                              "--execution", execution, "--evidence", raw_path)
            self.case["evidence"][name] = self.ref(self.write(self.root / (name + ".json"), bound))
        self.write(self.case_path, self.case)

    def test_limit_or_condition_change_deterministically_rejects_prior_proof(self):
        self.close_case()
        self.assertEqual(self.assess()["engineering_evidence"], "covered")
        self.assertIn("requirements", self.check()["bindings"])
        original = deepcopy(self.contract)
        for change in ("limit", "condition"):
            with self.subTest(change=change):
                self.contract = deepcopy(original)
                if change == "limit":
                    self.contract["criteria"]["sealed-limit"]["limit"] = 5.5
                else:
                    self.contract["conditions"]["boot"]["window"] = "first 11 ms"
                self.sync()  # case now points at the new bytes; old receipt must still be rejected
                self.assertEqual(self.assess(1)["system_contract"]["status"], "blocked")
                self.assertEqual(self.check(1)["engineering_evidence"], "blocked")
        self.close_case()
        self.assess()

    def test_one_contract_reference_still_binds_its_condition(self):
        row = {"status": "open", "condition": "specified in the criterion",
               "criterion": "contract:criterion:sealed-limit"}
        self.case["checks"]["requirements"] = row
        self.sync()
        before = self.check()["bindings"]["requirements"]
        self.contract["conditions"]["boot"]["window"] = "first 11 ms"
        self.sync()
        self.assertNotEqual(self.check()["bindings"]["requirements"], before)

    def test_point_changes_stale_own_receipt_and_keep_sibling_valid(self):
        ports = self.contract["ports"]
        ports["soc.reset"]["variants"] = ["sealed"]
        ports["soc.reset"]["anchor"] = "observed"
        ports["soc.vented-reset"] = {
            "block": "soc", "kind": "timing", "role": "input", "domain": "io", "variants": ["vented"],
        }
        self.contract["anchors"]["observed"]["variants"] = ["sealed"]
        self.contract["criteria"]["vented-limit"]["point"] = "soc.vented-reset"
        self.sync()
        self.close_case()
        self.assess()
        original = deepcopy(self.contract)
        for group, name, field, new in (
                ("ports", "soc.reset", "domain", "secondary-io"),
                ("ports", "soc.reset", "gap", "missing receiver access"),
                ("ports", "soc.reset", "locator", "J2.1"),
                ("anchors", "observed", "locator", "capture channel 2")):
            with self.subTest(field=field):
                self.contract = deepcopy(original)
                self.contract[group][name][field] = new
                self.sync()
                self.assertEqual(self.assess(1)["system_contract"]["status"], "blocked")
                self.assertEqual(self.check(1)["engineering_evidence"], "blocked")
        self.contract = deepcopy(original)
        self.baseline["variant"] = "vented"
        self.sync()
        self.close_case(criterion="vented-limit")
        digest = self.check()["bindings"]["requirements"]
        self.contract["ports"]["soc.reset"].update(domain="secondary-io", gap="not yet reachable", locator="J2.1")
        self.sync()
        self.assertEqual(self.check()["bindings"]["requirements"], digest)
        self.assess()

    def test_direct_block_point_fingerprint_covers_its_definition(self):
        self.contract["criteria"]["sealed-limit"]["point"] = "soc"
        self.sync()
        self.close_case()
        self.assess()
        self.contract["blocks"]["soc"]["role"] = "buffered receiver"
        self.sync()
        self.assess(1)

    def test_distinguishes_conflicts_from_missing_evidence(self):
        saved = deepcopy(self.contract)
        for problem, code in (("budget", 1), ("cycle", 1), ("variant", 1), ("wrong-condition", 1),
                              ("hash", 1), ("receipt-hash", 1), ("receipt-digest", 2),
                              ("missing-entry", 2), ("missing-file", 2)):
            with self.subTest(problem=problem):
                self.contract = deepcopy(saved)
                self.sync()
                self.close_case()
                if problem == "budget":
                    self.contract["criteria"]["sealed-limit"]["allocations"] = [2, 3.00001]
                if problem == "cycle":
                    self.contract["dependencies"].append({"source": "sealed-limit", "target": "shell",
                                                          "variants": ["sealed"]})
                if problem == "variant":
                    self.case["checks"]["requirements"]["criterion"] = "contract:criterion:vented-limit"
                if problem == "wrong-condition":
                    self.contract["conditions"]["hot"] = {"state": "hot", "window": "2 ms", "variants": ["sealed"]}
                    self.case["checks"]["requirements"]["condition"] = "contract:condition:hot"
                if problem == "missing-entry":
                    self.case["checks"]["requirements"]["criterion"] = "contract:criterion:missing"
                if problem.startswith("receipt-"):
                    path = self.root / "requirements.json"
                    value = json.loads(path.read_bytes())
                    del value["coverage"]["engineering"]["checks"]["requirements"]["contract_sha256"]
                    self.write(path, value)
                    if problem == "receipt-digest":
                        self.case["evidence"]["requirements"] = self.ref(path)
                self.sync()
                if problem == "hash":
                    self.contract_path.write_text("{}", encoding="utf-8")
                if problem == "missing-file":
                    self.contract_path.unlink()
                expected = {1: "blocked", 2: "needs_evidence"}[code]
                self.assertEqual(self.assess(code)["engineering_evidence"], expected)
                self.assertEqual(self.check(code)["engineering_evidence"], expected)

    def test_enclosure_eco_walks_bound_variant_and_retains_sibling_proof(self):
        self.baseline["variant"] = "vented"
        self.close_case(criterion="vented-limit")
        change = {"schema": "hardware-engineering-change-v1", "baseline": self.baseline,
                  "changes": [{"object": "shell", "kind": "enclosure-thermal", "variant": "*",
                               "before": "35 mm", "after": "32 mm"}]}
        path = self.write(self.root / "change.json", change)
        impact = self.flow("impact", "--change", path)
        self.assertEqual({row["variant"] for row in impact["recheck"]}, {"sealed"})
        targeted = next(row for row in impact["recheck"] if row["check"] == "firmware-interface")
        self.assertEqual(targeted["contract_path"], ["shell", "sealed-limit", "check:firmware-interface"])
        self.assertTrue({"thermal", "layout-coverage", "assembly"} <= {row["check"] for row in impact["recheck"]})
        self.assertEqual(impact["invalidated_baseline_checks"], [])
        self.contract["criteria"]["sealed-limit"]["limit"] = 5.5
        self.sync()
        self.assertIn("requirements", impact["reuse_candidates"])
        self.assess()
        change["changes"][0]["variant"] = "vented"
        self.flow("impact", "--change", self.write(path, change), code=1, output=False)

    def test_formal_stage_rechecks_bound_contract_and_release_without_hash_cycle(self):
        self.close_case()
        file = self.workflow / "program-state.json"
        self.call(STATE, "--file", file, "init", "--project", "fixture", "--formal-engineering")
        stage = ("--file", file, "set-stage", "--stage", "product_definition", "--status", "PASS",
                 "--evidence", "synthetic", "--engineering-case", self.case_path, "--require-system-contract")
        self.call(STATE, *stage)
        snapshot = json.loads(file.read_bytes())
        self.assertIs(snapshot["stages"]["product_definition"]["engineering_case"]["require_system_contract"], True)
        self.contract["criteria"]["sealed-limit"]["limit"] = 5.5
        self.sync()
        self.call(STATE, "--file", file, "validate", code=1)

        package = self.root / "release"
        manifest = self.write_package(package)
        release = {"manifest": self.ref(manifest), "cpl": self.ref(package / "cpl.csv")}
        self.case["mode"] = "release"
        self.case["artifacts"].update(release)
        self.close_case(bound_check="release-identity", extras={"release-identity": release})
        self.assertEqual(self.assess(target="fabrication")["engineering_evidence"], "covered")
        self.assertFalse("case.json" in manifest.read_text(encoding="utf-8"))

    def write_package(self, package):
        data = release_fixture(package)
        path = self.write(package / "release-manifest.json", data)
        self.call(RELEASE_SCRIPTS / "validate_release_manifest.py", path, "--confine-to-manifest-dir")
        return path
