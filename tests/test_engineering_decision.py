import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SKILLS = Path(__file__).resolve().parents[1] / "skills"
HARDWARE = SKILLS / "hardware"
FLOW = HARDWARE / "scripts/design_flow.py"
STATE = SKILLS / "manage-pcba-program/scripts/program_state.py"
POLICY = json.loads((HARDWARE / "assets/engineering-policy.json").read_text(encoding="utf-8"))
IDENTITY = {"project": "Fixture", "revision": "R1", "variant": "industrial"}


def invoke(script, *args):
    return subprocess.run([sys.executable, "-X", "utf8", "-B", str(script), *map(str, args)],
                          encoding="utf-8", capture_output=True, timeout=20, check=False)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def ref(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class EngineeringDecisionTests(unittest.TestCase):
    def run_json(self, script, *args, code=0):
        result = invoke(script, *args)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_all_profiles_and_prototypes_have_valid_rules_and_references(self):
        outcome = self.run_json(FLOW, "start", "design", *(
            word for name in POLICY["prototypes"] for word in ("--prototype", name)))
        self.assertGreater(len(outcome["prototypes"]), 8)
        available = {row["id"] for row in outcome["candidate_rules"]}
        self.assertTrue(set(outcome["required_rules"]) <= available)
        for node in POLICY["checks"].values():
            self.assertTrue(all((HARDWARE / item).is_file() for item in node["references"]))
            self.assertTrue(set(node["affects"]) <= POLICY["checks"].keys())
        for mode in POLICY["modes"]:
            out = self.run_json(FLOW, "start", mode)
            self.assertTrue({row["id"] for row in out["required_checks"]} >= set(POLICY["modes"][mode]))

    def test_adc_alias_expands_risks_without_case_or_named_failure(self):
        result = self.run_json(FLOW, "start", "design", "--intent", "设计一块 ADC 接口给 MCU 采样",
                               "--model-limit", "device-dynamics")
        self.assertEqual(set(result["prototype_matches"]), {"mixed-signal-mcu", "adc-front-end"})
        ids = {row["id"] for row in result["required_checks"]}
        self.assertTrue({"analog-drive", "effective-capacitance", "power-states",
                         "return-path", "practical-design", "pre-mortem", "adc-timing"} <= ids)
        self.assertIn("analog-capacitive-load", result["required_rules"])
        self.assertIn("adc-kickback-filter", result["required_rules"])
        self.assertEqual(result["model_upgrades"][0]["trigger"], "device-dynamics")

    def test_eco_propagation_preserves_unchanged_variant_and_price_only_stays_commercial(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = save(root / "case.json", {
                "schema": "hardware-engineering-case-v1", "mode": "eco", "baseline": IDENTITY,
                "checks": {label: {"status": "open"} for label in (
                    "commercial-fit", "component-qualification", "release-identity")}})
            change = {"schema": "hardware-engineering-change-v1", "baseline": IDENTITY,
                      "changes": [{"object": "U17", "variant": "consumer", "kind": "production-config",
                                   "before": "fab A", "after": "fab B"}]}
            result = self.run_json(FLOW, "impact", "--case", case, "--change", save(root / "change.json", change))
            self.assertEqual(result["invalidated_baseline_checks"], [])
            self.assertTrue({"component-qualification", "assembly", "release-identity"} <=
                            {row["check"] for row in result["recheck"]})
            change["changes"][0]["variant"] = IDENTITY["variant"]
            result = self.run_json(FLOW, "impact", "--case", case, "--change", save(root / "change.json", change))
            self.assertEqual(result["invalidated_baseline_checks"], ["component-qualification", "release-identity"])
            change["changes"][0]["kind"] = "price-stock"
            result = self.run_json(FLOW, "impact", "--case", case, "--change", save(root / "change.json", change))
            self.assertEqual(result["invalidated_baseline_checks"], ["commercial-fit"])
            self.assertEqual(len(result["recheck"]), 1)

    def test_source_rules_follow_each_engineering_mode(self):
        cases = {
            "analog-drive": ("电压跟随器直接驱动 10 nF", "analog-capacitive-load", "analog"),
            "edge-termination": ("接收端振铃并重复跨越门限", "si-source-termination", "si"),
            "emc-current-path": ("屏蔽线互联，EFT 后偶发复位", "emc-shield-current-path", "emc"),
        }
        for mode in POLICY["modes"]:
            with self.subTest(mode=mode):
                result = self.run_json(FLOW, "start", mode, "--intent", "；".join(
                    case[0] for case in cases.values()))
                checks = {row["id"]: row for row in result["required_checks"]}
                themes = {row["id"] for row in result["knowledge_route"]["themes"]}
                for check, (_, rule, theme) in cases.items():
                    self.assertEqual(checks[check]["phase_action"], POLICY["checks"][check]["phase_actions"][mode])
                    self.assertIn(rule, result["required_rules"])
                    self.assertIn(theme, themes)
        ordinary = self.run_json(FLOW, "start", "plan", "--intent", "整理按键尺寸与面板需求")
        self.assertTrue(cases.keys().isdisjoint(row["id"] for row in ordinary["required_checks"]))

    def test_carried_checks_remain_open_when_handoff_lacks_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, record = self.synthetic_case(root)
            case = save(root / "case.json", record)
            self.run_json(FLOW, "assess", "--case", case, "--target", "handoff")
            record["intent"] = "EFT 后复位，给出几个工程处理方向"
            save(case, record)
            result = self.run_json(FLOW, "assess", "--case", case, "--target", "handoff", code=2)
            self.assertIn("emc-current-path", {x["id"] for x in result["results"] if x["status"] == "open"})
            record["intent"] = "同版冻结交接"
            record["checks"]["emc-current-path"] = {"status": "open"}
            for mode, target in (("plan", "handoff"), ("release", "fabrication")):
                record["mode"] = mode
                result = self.run_json(FLOW, "assess", "--case", save(case, record), "--target", target, code=2)
                row = next(x for x in result["results"] if x["id"] == "emc-current-path")
                self.assertEqual(row["status"], "open")
                self.assertEqual(row["phase_action"], POLICY["checks"]["emc-current-path"]["phase_actions"][mode])
                start = self.run_json(FLOW, "start", mode, "--case", case)
                self.assertIn("emc", {x["id"] for x in start["knowledge_route"]["themes"]})

    def test_signal_and_emc_evidence_invalidates_by_variant(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scoped = {"analog-drive", "edge-termination", "emc-current-path"}
            case = save(root / "case.json", {
                "schema": "hardware-engineering-case-v1", "mode": "eco", "baseline": IDENTITY,
                "checks": {name: {"status": "open"} for name in scoped},
            })
            change = {"schema": "hardware-engineering-change-v1", "baseline": IDENTITY,
                      "changes": [{"object": "PCB and chassis return", "variant": IDENTITY["variant"], "kind": "layout",
                                   "before": "R1", "after": "R2"}]}
            path = save(root / "change.json", change)
            result = self.run_json(FLOW, "impact", "--case", case, "--change", path)
            self.assertEqual(set(result["invalidated_baseline_checks"]), scoped)
            change["changes"][0]["variant"] = "consumer"
            result = self.run_json(FLOW, "impact", "--case", case, "--change", save(path, change))
            self.assertEqual(result["invalidated_baseline_checks"], [])

    def synthetic_case(self, root):
        subject = root / "requirements.txt"
        subject.write_text("Synthetic controlled planning input.", encoding="utf-8")
        manifest = {
            "schema": "hardware-engineering-case-v1", "mode": "plan", "baseline": IDENTITY,
            "artifacts": {"spec": ref(subject)}, "checks": {}, "evidence": {},
        }
        for item in POLICY["modes"]["plan"]:
            stage = POLICY["checks"][item]["stages"][0]
            claim = {"condition": "specified input", "criterion": "fixture criterion",
                     "execution": f"fixture:{item}", "disposition": "pass"}
            result = {
                "schema": "hardware-evidence-envelope-v1", "backend": "test-fixture", "evidence_stage": stage,
                "execution_status": "completed", "mutation_outcome": "unchanged", "verification_status": "pass",
                "inputs": {"spec": ref(subject)}, "outputs": {}, "checks_executed": [claim["execution"]],
                "checks_skipped": [], "coverage": {"engineering": {**IDENTITY, "checks": {item: claim}}}, "native": {},
            }
            receipt = save(root / (item + ".json"), result)
            manifest["evidence"][item] = ref(receipt)
            manifest["checks"][item] = {
                "status": "pass", "condition": claim["condition"], "criterion": claim["criterion"],
                "finding": "synthetic record", "artifacts": ["spec"], "evidence": [item],
            }
        return subject, manifest

    def test_formal_separates_coverage_from_approval_and_checks_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subject, record = self.synthetic_case(root)
            case = save(root / "case.json", record)
            def assessment(code):
                return self.run_json(FLOW, "assess", "--case", case, "--target", "handoff", code=code)
            result = assessment(0)
            self.assertEqual(result["engineering_evidence"], "covered")
            self.assertEqual(result["project_signoff"], "verify_separately")
            self.assertEqual(result["operation_authorization"], "check_user_or_host_separately")
            record["model_limits"] = {"power-states": ["device-dynamics"]}
            save(case, record)
            self.assertEqual(assessment(2)["engineering_evidence"], "needs_evidence")
            record.pop("model_limits")
            save(case, record)
            subject.write_text("Content changed at the same revision.", encoding="utf-8")
            self.assertIn("spec", assessment(2)["artifact_issues"])

    @unittest.skipUnless(os.name == "nt", "Windows short-path spelling")
    def test_formal_evidence_accepts_existing_windows_short_path_alias(self):
        from ctypes import create_unicode_buffer, windll

        with tempfile.TemporaryDirectory(prefix="hardware engineering evidence ") as directory:
            root = Path(directory).resolve()
            alias = create_unicode_buffer(32768)
            size = windll.kernel32.GetShortPathNameW(str(root), alias, len(alias))
            if not 0 < size < len(alias) or Path(alias.value) == root:
                self.skipTest("Windows volume did not assign this directory a short alias")
            _, record = self.synthetic_case(Path(alias.value))
            case = save(root / "case.json", record)
            result = self.run_json(FLOW, "assess", "--case", case, "--target", "handoff")
            self.assertEqual(result["engineering_evidence"], "covered")

    def test_formal_keeps_an_existing_file_outside_the_root_out_of_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "root"
            root.mkdir()
            _, record = self.synthetic_case(root)
            outside = parent / "external.txt"
            outside.write_text("Existing fixture outside the evidence root.", encoding="utf-8")
            record["artifacts"]["spec"] = ref(outside)
            result = self.run_json(FLOW, "assess", "--case", save(root / "case.json", record),
                                   "--target", "handoff", code=2)
            self.assertIn("证据文件不在明确指定的工程范围内", result["artifact_issues"]["spec"])

    def test_stale_or_conflicting_receipt_cannot_be_bound_to_a_formal_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, record = self.synthetic_case(root)
            item = "power-states"
            file = Path(record["evidence"][item]["path"])
            evidence = json.loads(file.read_text(encoding="utf-8"))
            evidence["coverage"]["engineering"]["revision"] = "older"
            record["evidence"][item] = ref(save(file, evidence))
            case = save(root / "case.json", record)
            hold = self.run_json(FLOW, "assess", "--case", case, "--target", "handoff", code=2)
            self.assertEqual(next(x["status"] for x in hold["results"] if x["id"] == item), "open")
            evidence["coverage"]["engineering"]["revision"] = IDENTITY["revision"]
            evidence["verification_status"] = "fail"
            evidence["coverage"]["engineering"]["checks"][item]["disposition"] = "fail"
            record["evidence"][item] = ref(save(file, evidence))
            record["checks"][item]["status"] = "fail"
            save(case, record)
            result = self.run_json(FLOW, "assess", "--case", case, "--target", "handoff", code=1)
            self.assertEqual(result["engineering_evidence"], "blocked")

    def test_project_state_formal_pass_is_bound_to_a_live_case(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subject, record = self.synthetic_case(root)
            case = save(root / "case.json", record)
            file = root / "state.json"
            self.run_json(STATE, "--file", file, "init", "--project", "Fixture", "--formal-engineering")
            stage = ("--file", file, "set-stage", "--stage", "product_definition", "--status",
                     "PASS", "--evidence", "synthetic")
            self.run_json(STATE, *stage, code=1)
            self.run_json(STATE, *stage, "--engineering-case", case)
            subject.write_text("modified", encoding="utf-8")
            result = self.run_json(STATE, "--file", file, "validate", code=1)
            self.assertIn("engineering case", result["errors"][0])

    def test_sourcing_receipt_cannot_prove_power_state_and_premortem_cannot_be_waived(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, record = self.synthetic_case(root)
            case = save(root / "case.json", record)
            proof = Path(record["evidence"]["power-states"]["path"])
            value = json.loads(proof.read_text(encoding="utf-8"))
            value["backend"] = "sourcing-lock-checker"
            result = invoke(FLOW, "bind", "--case", case, "--evidence", save(proof, value),
                            "--check", "power-states", "--execution", "fixture:power-states",
                            "--condition", "specified input", "--criterion", "fixture criterion")
            self.assertEqual(result.returncode, 2)
            self.assertIn("后端的检查范围", result.stderr)
            proof = Path(record["evidence"]["pre-mortem"]["path"])
            result = invoke(FLOW, "bind", "--case", case, "--evidence", proof, "--check", "pre-mortem",
                            "--execution", "fixture:pre-mortem", "--condition", "specified input",
                            "--criterion", "fixture criterion", "--disposition", "not_applicable")
            self.assertEqual(result.returncode, 2)
            self.assertIn("必须有实际结论", result.stderr)


if __name__ == "__main__":
    unittest.main()
