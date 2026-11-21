"""Derive engineering checks and verify formal evidence without executing hardware tools."""

from collections import deque
import hashlib
import json
import os
from pathlib import Path
import re

import evidence_adapter
from hardware_tool import local_file
import system_contract


SKILL = Path(__file__).resolve().parents[1]
POLICY_FILE = SKILL / "assets/engineering-policy.json"
CASE_VERSION = "hardware-engineering-case-v1"
CHANGE_VERSION = "hardware-engineering-change-v1"
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
IDENTITY = ("project", "revision", "variant")
TARGET_MODES = {
    "formal_review": {"review", "verify"},
    "handoff": {"plan", "design", "review", "eco", "verify", "bringup", "release"},
    "formal_eco": {"eco"},
    "fabrication": {"release"},
    "evt": {"verify", "bringup"},
    "dvt": {"verify", "bringup"},
    "pvt": {"release"},
    "first_article": {"release"},
    "production": {"release"},
    "smt_release": {"release"},
}
PHYSICAL_TARGETS = {"evt", "dvt", "pvt", "first_article", "production", "smt_release"}
MODEL_LIMITS = {
    "nominal-only": ("补保证 min/max 和有界工况，重算可达角点。", None),
    "margin-crosses-limit": ("证明角点可达性或用独立模型/量测缩小跨限区间。", None),
    "device-dynamics": ("核原厂模型对相关动态的支持，执行适用瞬态/AC，或用实测验证。", ("simulation", "bench_record")),
    "parasitics-dominate": ("用实际几何、寄生或夹具建模校核，保留提取和验证工况。", ("simulation", "bench_record", "cam_readback", "native_eda")),
    "measurement-conflict": ("先消除测量伪影，做同参考面、同时间基准的独立对照。", ("bench_record",)),
    "sample-required": ("当前判据要求代表性实物证据，离线阶段可交计划和剩余缺口。", ("bench_record",)),
}
REQUIRED_APPLICABILITY = {"requirements", "pre-mortem", "change-impact", "release-identity", "production-evidence"}
BACKEND_CHECKS = {
    "sourcing-lock-checker": {"component-qualification", "commercial-fit"},
    "release-manifest-validator": {"release-identity", "assembly"},
    "kicad-report-check": {"layout-coverage"},
    "kicad-cli": {"layout-coverage"},
    "bench-result-checker": {"verification-coverage", "test-coverage"},
    "gerbonara": {"layout-coverage"},
    "ngspice": {"rating-limits", "power-states", "fault-propagation", "wcca", "analog-drive",
                "adc-timing", "filter-stability", "effective-capacitance", "power-stability",
                "power-path", "thermal", "bus-window", "verification-coverage"},
}


def read_json(path):
    return evidence_adapter.strict_json(path.read_text(encoding="utf-8-sig"))


def policy():
    data = read_json(POLICY_FILE)
    if data.get("schema") != "hardware-engineering-policy-v1":
        raise ValueError("不支持的工程策略版本")
    return data


def text(value):
    return isinstance(value, str) and bool(value.strip())


def matches(intent, alias):
    if alias.isascii():
        return re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])",
                         intent, flags=re.I) is not None
    return alias.casefold() in intent.casefold()


def intent_matches(intent, keywords):
    return any(matches(intent, term) for term in keywords)


def affirmed_change(intent, terms):
    for term in terms:
        for hit in re.finditer(re.escape(term), intent):
            prefix = intent[:hit.start()].rstrip()
            suffix = intent[hit.end():].lstrip()
            excluded = re.search(r"(?:不涉及|不做|不计划|不需要|无需|无须|不要|不|未|没)(?:更)?$", prefix)
            if not excluded and not suffix.startswith(("不在", "不做", "取消")):
                return True
    return False


def inferred_trigger(trigger, mode, examples, intent):
    return mode in trigger.get("modes", (mode,)) and (
        examples.intersection(trigger.get("prototypes", ()))
        or intent_matches(intent, trigger.get("keywords", ()))
        or affirmed_change(intent, trigger.get("change_terms", ()))
        or any(all(intent_matches(intent, group) for group in conjunction)
               for conjunction in trigger.get("all_of", ()))
    )


def active_branches(policy_data, mode, examples, intent, target, facts):
    selected = {}
    examples = set(examples)
    for key, branch in policy_data.get("branches", {}).items():
        trigger = branch["trigger"]
        if target in trigger.get("targets", ()):
            selected[key] = "target"
            continue
        if mode not in trigger.get("modes", policy_data["modes"]) or target in trigger.get("exclude_targets", ()):
            continue
        state = facts.get(key)
        if state == "absent":
            continue
        if state == "present" or (state == "unknown" and not trigger.get("unknown_requires_trigger")):
            selected[key] = state
        elif any(inferred_trigger(scope, mode, examples, intent) for scope in trigger.get("scopes", [trigger])):
            selected[key] = state or "scope_candidate"
    return selected


def select(policy_data, mode, prototypes, intent="", target=None, facts=None, model_limits=(),
           carried_checks=()):
    inferred = [
        name for name, record in policy_data["prototypes"].items()
        if any(matches(intent, alias) for alias in record["aliases"])
    ]
    examples = list(dict.fromkeys([*prototypes, *inferred]))
    unknown = set(examples) - policy_data["prototypes"].keys()
    if unknown:
        raise ValueError(f"未知电路原型：{', '.join(sorted(unknown))}")
    identifiers = list(policy_data["modes"][mode])
    if target:
        identifiers.extend(policy_data["targets"][target])
    for name in examples:
        identifiers.extend(policy_data["prototypes"][name]["checks"])
    identifiers.extend(
        key for key, check in policy_data["checks"].items()
        if (intent_matches(intent, check.get("intent_keywords", ()))
            or ("phase_actions" in check and key in carried_checks))
    )
    facts = facts or {}
    branches = policy_data.get("branches", {})
    for item, value in facts.items():
        if item not in policy_data["checks"] and item not in branches:
            raise ValueError(f"未知风险事实：{item}")
        if value not in ("present", "absent", "unknown"):
            raise ValueError(f"风险事实状态无效：{item}")
        if item in policy_data["checks"] and value != "absent":
            identifiers.append(item)
    branch_checks = {}
    for key, match in active_branches(policy_data, mode, examples, intent, target, facts).items():
        branch = branches[key]
        check = branch["check"]
        identifiers.append(check)
        branch_checks.setdefault(check, []).append({
            "id": key, "title": branch["title"], "matched_by": match,
            "phase_action": branch["phase_actions"][mode],
            "closure": branch["closure"], "redline": branch["redline"], "prototype": branch["prototype"],
            "sources": branch["sources"], "rules": branch["rules"],
            **({"related_sources": branch["related_sources"]} if "related_sources" in branch else {}),
        })
    required = []
    for identifier in dict.fromkeys(identifiers):
        row = policy_data["checks"][identifier]
        required.append({
            "id": identifier, "severity": row["severity"], "reason": row["reason"],
            "rules": list(dict.fromkeys([*row["rules"], *(
                rule for branch in branch_checks.get(identifier, ()) for rule in branch["rules"]
            )])), "references": row["references"],
            **({"phase_action": row["phase_actions"][mode]} if "phase_actions" in row else {}),
            **({"knowledge_theme": row["knowledge_theme"]} if "knowledge_theme" in row else {}),
            **({"branches": branch_checks[identifier]} if identifier in branch_checks else {}),
        })
    return {
        "prototypes": examples,
        "prototype_matches": inferred,
        "confirm_functional_scope": not examples,
        "required_checks": required,
        "required_rules": list(dict.fromkeys(rule for row in required for rule in row["rules"])),
        "model_upgrades": [
            {"trigger": name, "next": MODEL_LIMITS[name][0]} for name in dict.fromkeys(model_limits)
        ],
        "proceed_with_assumptions": (
            "非关键缺项可用有来源或有界的工业假设推进，注明首板关闭方法、"
            "可测点、隔离预留及零件供货。高后果待证项限制相关结论，独立部分继续。"
        ),
    }


def inspect_baseline(value):
    if not isinstance(value, dict) or any(not text(value.get(field)) for field in IDENTITY):
        raise ValueError("基线需要明确 project/revision/variant")
    return {field: value[field] for field in IDENTITY}


def identity(scope):
    return tuple(scope[field] for field in IDENTITY)


def load_case(path, policy_data):
    data = read_json(path)
    if not isinstance(data, dict) or data.get("schema") != CASE_VERSION:
        raise ValueError("工程记录 schema 无效")
    if data.get("mode") not in policy_data["modes"]:
        raise ValueError("工程记录的 mode 无效")
    inspect_baseline(data.get("baseline"))
    if not isinstance(data.get("intent", ""), str):
        raise ValueError("intent 需要文字")
    prototypes = data.get("prototypes", [])
    if not isinstance(prototypes, list) or not all(text(item) for item in prototypes):
        raise ValueError("prototypes 需要名称列表")
    for key in ("facts", "artifacts", "evidence", "checks", "model_limits"):
        if not isinstance(data.get(key, {}), dict):
            raise ValueError(f"{key} 需要对象")
    if any(not isinstance(row, dict) or row.get("status") not in ("open", "pass", "fail", "not_applicable")
           for row in data.get("checks", {}).values()):
        raise ValueError("每个工程检查需要明确的记录状态")
    for check, flags in data.get("model_limits", {}).items():
        if (check not in policy_data["checks"] or not isinstance(flags, list)
                or any(not text(flag) or flag not in MODEL_LIMITS for flag in flags)):
            raise ValueError(f"{check} 的模型边界无效")
    return data


def scoped_path(value, root):
    if not text(value):
        raise ValueError("证据缺文件路径")
    path = Path(os.path.abspath(root / value))
    outside = not path.is_relative_to(root)
    if outside and (os.name != "nt" or path.drive.casefold() != root.drive.casefold()):
        raise ValueError("证据文件不在明确指定的工程范围内")
    # Windows may spell the same local directory using an 8.3 alias. Check
    # every component for reparse points before resolving either spelling.
    checked = local_file(path).resolve(strict=True)
    if not checked.is_relative_to(root.resolve(strict=True)):
        raise ValueError("证据文件不在明确指定的工程范围内")
    return checked


def reference(spec, root):
    if not isinstance(spec, dict) or not DIGEST.fullmatch(str(spec.get("sha256", ""))):
        raise ValueError("证据或基线缺 SHA-256")
    path = scoped_path(spec.get("path"), root)
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != spec["sha256"]:
        raise system_contract.ContractConflict("文件内容与记录摘要不一致")
    return str(path), actual


def contract_reference(condition, criterion):
    return any(isinstance(value, str) and value.startswith("contract:") for value in (condition, criterion))


def contract_context(data, policy_data, root, *, required=False, expected_path=None):
    baseline = inspect_baseline(data["baseline"])
    rows = {
        name: row for name, row in data.get("checks", {}).items()
        if contract_reference(row.get("condition"), row.get("criterion"))
    }
    spec = data.get("artifacts", {}).get("system_contract")
    if spec is None and not (required or rows or expected_path is not None):
        return None, {}, {}
    try:
        contract = system_contract.load(spec, root, baseline, policy_data["checks"], expected_path=expected_path)
    except (system_contract.ContractConflict, system_contract.ContractMissing) as exc:
        return None, {}, {"system_contract": exc}
    bindings, issues = {}, {}
    for name, row in rows.items():
        try:
            bindings[name] = system_contract.binding(contract, baseline, row.get("condition"), row.get("criterion"))
        except (system_contract.ContractConflict, system_contract.ContractMissing) as exc:
            issues[name] = exc
    return contract, bindings, issues


def contract_status(issues):
    if any(isinstance(exc, system_contract.ContractConflict) for exc in issues.values()):
        return "blocked"
    return "needs_evidence" if issues else "covered"


def check_scope(raw, check, disposition):
    if disposition == "not_applicable" and check in REQUIRED_APPLICABILITY:
        raise ValueError("该正式检查必须有实际结论")
    if raw["backend"] in BACKEND_CHECKS and check not in BACKEND_CHECKS[raw["backend"]]:
        raise ValueError("该后端的检查范围不能用于这项工程结论")


def bind(raw, baseline, check, condition, criterion, execution, disposition, stages, branches=(),
         *, contract_sha256=None):
    evidence_adapter.validate(raw)
    check_scope(raw, check, disposition)
    if any(not text(item) for item in (condition, criterion, execution)):
        raise ValueError("工况、判据和执行项不能为空")
    if (raw["evidence_stage"] not in stages or raw["execution_status"] != "completed"
            or raw["mutation_outcome"] == "outcome_unknown" or execution not in raw["checks_executed"]
            or raw["verification_status"] != ("fail" if disposition == "fail" else "pass")):
        raise ValueError("指定执行项、状态或证据层与工程结论不匹配")
    original = raw["coverage"].get("engineering", {})
    if not isinstance(original, dict) or not isinstance(original.get("checks", {}), dict):
        raise ValueError("原证据的工程覆盖结构无效")
    if original and any(original.get(key) != baseline[key] for key in IDENTITY):
        raise ValueError("证据已绑定其他工程、版次或变体")
    claim = {"condition": condition, "criterion": criterion, "execution": execution, "disposition": disposition}
    if contract_reference(condition, criterion):
        if contract_sha256 is None:
            raise system_contract.ContractMissing("契约检查必须绑定当前判据和工况摘要")
        claim["contract_sha256"] = contract_sha256
    if branches:
        claim["branches"] = sorted(set(branches))
    existing = original.get("checks", {})
    if check in existing and existing[check] != claim:
        raise ValueError("证据已绑定该检查的另一工况或判据")
    raw["coverage"]["engineering"] = {**baseline, "checks": {**existing, check: claim}}
    return raw


def make_proof(check, record, evidence, artifacts, baseline, root, stages, cache, branch_stages=None,
               *, contract_sha256=None):
    if not text(record.get("condition")) or not text(record.get("finding")):
        raise ValueError("缺工况或观察结果")
    if not text(record.get("criterion")):
        raise ValueError("缺判据")
    ids = record.get("evidence")
    subjects = record.get("artifacts")
    if not isinstance(ids, list) or not ids or any(not text(item) for item in ids):
        raise ValueError("未提交证据引用")
    if not isinstance(subjects, list) or not subjects or any(item not in artifacts for item in subjects):
        raise ValueError("缺少已核对的基线工件")
    required = {artifacts[item] for item in subjects}
    expected = {"pass": "pass", "fail": "fail", "not_applicable": "pass"}[record["status"]]
    branch_stages = branch_stages or {}
    if branch_stages and record["status"] == "not_applicable":
        raise ValueError("已触发分支需要适用性定界或实际证据")
    covered = set()
    for item in ids:
        if item not in cache:
            try:
                path, _ = reference(evidence[item], root)
                raw = read_json(Path(path))
                evidence_adapter.validate(raw)
                files = {
                    reference(spec, root) for section in ("inputs", "outputs")
                    for spec in raw[section].values()
                }
                cache[item] = (raw, files)
            except (KeyError, ValueError, OSError) as exc:
                cache[item] = exc
        proof = cache[item]
        if isinstance(proof, Exception):
            if contract_sha256 is not None and isinstance(proof, system_contract.ContractConflict):
                raise proof
            raise ValueError(f"{item}：{proof}")
        raw, files = proof
        check_scope(raw, check, record["status"])
        cover = raw["coverage"].get("engineering")
        if not isinstance(cover, dict) or any(cover.get(key) != baseline[key] for key in IDENTITY):
            if contract_sha256 is not None and isinstance(cover, dict) and all(text(cover.get(key)) for key in IDENTITY):
                raise system_contract.ContractConflict(f"{item} 绑定到不同工程、版次或变体")
            raise ValueError(f"{item} 未绑定同工程、版次和变体")
        if (raw["evidence_stage"] not in stages or raw["execution_status"] != "completed"
                or raw["mutation_outcome"] == "outcome_unknown"
                or raw["verification_status"] != expected):
            raise ValueError(f"{item} 的执行、证据类型或结果不能支撑结论")
        observations = cover.get("checks", {})
        if not isinstance(observations, dict):
            raise ValueError(f"{item} 的检查覆盖无效")
        claim = observations.get(check)
        if not isinstance(claim, dict):
            raise ValueError(f"{item} 未覆盖 {check}")
        if contract_sha256 is not None:
            if "contract_sha256" not in claim:
                raise system_contract.ContractMissing(f"{item} 缺契约判据与工况摘要")
            if claim["contract_sha256"] != contract_sha256:
                raise system_contract.ContractConflict(f"{item} 的契约判据或工况已变更，必须重验")
            if claim.get("condition") != record["condition"] or claim.get("criterion") != record["criterion"]:
                raise system_contract.ContractConflict(f"{item} 的契约工况或判据引用不符")
        execution = claim.get("execution")
        if execution not in raw["checks_executed"]:
            raise ValueError(f"{item} 未实际执行所引检查")
        if (claim.get("condition") != record["condition"] or claim.get("criterion") != record["criterion"]
                or claim.get("disposition") != record["status"] or not required <= files):
            raise ValueError(f"{item} 的工况、判据、适用性或工件不符")
        declared = claim.get("branches", [])
        if not isinstance(declared, list) or not all(text(key) for key in declared):
            raise ValueError(f"{item} 的分支覆盖无效")
        covered.update(key for key in declared if raw["evidence_stage"] in branch_stages.get(key, ()))
    missing = branch_stages.keys() - covered
    # A single proven failure is enough to reject the check. A pass needs all active branches.
    if missing and record["status"] != "fail":
        raise ValueError(f"缺同工况的分支证据或证据层不符：{', '.join(sorted(missing))}")


def accepted_stages(stages, flags):
    permitted = set(stages)
    for name in flags:
        if MODEL_LIMITS[name][1] is not None:
            permitted &= set(MODEL_LIMITS[name][1])
    return permitted


def assess(data, policy_data, target, root, *, require_system_contract=False, contract_path=None):
    if data["mode"] not in TARGET_MODES[target]:
        raise ValueError("工程 mode 与正式交付目标不匹配")
    root = Path(os.path.abspath(root))
    if root.drive.startswith("\\\\") or not root.is_dir():
        raise ValueError("root 需要指定证据根目录")
    baseline = inspect_baseline(data["baseline"])
    check_state = data.get("checks", {})
    extra = set(check_state) - policy_data["checks"].keys()
    if extra:
        raise ValueError(f"不认识的工程检查：{', '.join(sorted(extra))}")
    contract, bindings, contract_issues = contract_context(
        data, policy_data, root, required=require_system_contract, expected_path=contract_path)
    facts = dict(data.get("facts", {}))
    for name in bindings:
        if facts.get(name) != "unknown":
            facts[name] = "present"
    chosen = select(policy_data, data["mode"], data.get("prototypes", []), data.get("intent", ""),
                    target, facts, carried_checks=check_state)
    artifacts = {}
    issues = {}
    artifact_conflicts = {}
    for key, spec in data.get("artifacts", {}).items():
        try:
            artifacts[key] = reference(spec, root)
        except (ValueError, OSError) as exc:
            issues[key] = str(exc)
            if isinstance(exc, system_contract.ContractConflict):
                artifact_conflicts[key] = exc
    results = []
    cache = {}
    for check in chosen["required_checks"]:
        name = check["id"]
        row = check_state.get(name)
        status = "open"
        reason = "缺可用的关闭记录"
        branches = check.get("branches", [])
        if isinstance(row, dict) and row.get("status") in ("pass", "fail", "not_applicable"):
            try:
                fingerprint = bindings.get(name)
                if contract_reference(row.get("condition"), row.get("criterion")) and fingerprint is None:
                    raise ValueError(str(contract_issues.get(name) or contract_issues.get("system_contract")
                                         or "缺契约绑定"))
                if fingerprint is not None:
                    for subject in row.get("artifacts", ()):
                        if subject in artifact_conflicts:
                            raise artifact_conflicts[subject]
                flags = data.get("model_limits", {}).get(name, [])
                if (row["status"] != "fail" and check["severity"] == "redline"
                        and data.get("facts", {}).get(name) == "unknown"):
                    raise ValueError("红线工况仍未确认")
                if row["status"] != "fail" and any(branch["matched_by"] == "unknown" for branch in branches):
                    raise ValueError("已标为未知的分支仍需确认适用工况")
                if row["status"] != "fail" and any(flag in {"nominal-only", "margin-crosses-limit"} for flag in flags):
                    raise ValueError("仍只有名义工况或保守区间跨限；先关闭模型边界再采用通过结论")
                stages = accepted_stages(policy_data["checks"][name]["stages"], flags)
                branch_stages = {}
                for branch in branches:
                    key = branch["id"]
                    rule = policy_data["branches"][key]
                    minimum = rule.get("physical_stages") if target in PHYSICAL_TARGETS else None
                    branch_stages[key] = stages & set(minimum) if minimum and row["status"] == "pass" else stages
                make_proof(name, row, data.get("evidence", {}), artifacts, baseline, root, stages, cache,
                           branch_stages, contract_sha256=fingerprint)
                status = row["status"]
                reason = row["finding"]
            except system_contract.ContractConflict as exc:
                contract_issues[name] = exc
                reason = str(exc)
            except (ValueError, TypeError) as exc:
                reason = str(exc)
        results.append({"id": name, "status": status, "severity": check["severity"], "reason": reason,
                        **({"phase_action": check["phase_action"]} if "phase_action" in check else {}),
                        **({"branches": branches} if branches else {})})
    formal = contract_status(contract_issues)
    hard_failure = formal == "blocked" or any(row["status"] == "fail" for row in results)
    open_check = any(row["status"] == "open" for row in results)
    status = "blocked" if hard_failure else "needs_evidence" if open_check or issues or contract_issues else "covered"
    return {
        "schema": "hardware-engineering-assessment-v1", "target": target, "baseline": baseline,
        "engineering_evidence": status, "artifact_issues": issues, "results": results,
        **({"system_contract": {"status": formal, "issues": {key: str(exc) for key, exc in contract_issues.items()}}}
           if contract is not None or contract_issues else {}),
        "project_signoff": "verify_separately",
        "operation_authorization": "check_user_or_host_separately",
    }


def contract_check(data, policy_data, root, path):
    baseline = inspect_baseline(data["baseline"])
    _, bindings, issues = contract_context(data, policy_data, root, required=True, expected_path=path)
    cache = {}
    for name, fingerprint in bindings.items():
        row = data["checks"][name]
        if row["status"] == "open":
            continue
        try:
            artifacts = {subject: reference(data["artifacts"][subject], root) for subject in row.get("artifacts", [])}
            make_proof(name, row, data.get("evidence", {}), artifacts, baseline, root,
                       policy_data["checks"][name]["stages"], cache, contract_sha256=fingerprint)
        except (ValueError, KeyError, OSError, TypeError) as exc:
            issues[name] = exc
    return {"schema": "hardware-system-contract-check-v1", "baseline": baseline,
            "engineering_evidence": contract_status(issues),
            "issues": {key: str(exc) for key, exc in issues.items()}, "bindings": bindings}


def contract_paths(contract, obj, variant):
    """Return check targets and their project-specific dependency paths."""
    outgoing = {}
    for edge in contract["dependencies"]:
        if variant in edge["variants"]:
            outgoing.setdefault(edge["source"], []).append(edge["target"])
    paths = {}
    queue = deque([(obj, [obj])])
    while queue:
        node, path = queue.popleft()
        if node in paths:
            continue
        paths[node] = path
        queue.extend((child, [*path, child]) for child in outgoing.get(node, ()))
    return {node.removeprefix("check:"): path for node, path in paths.items() if node.startswith("check:")}


def impact(data, change, policy_data, target=None, root=None):
    if target and data["mode"] not in TARGET_MODES[target]:
        raise ValueError("工程 mode 与冻结基线的正式交付目标不匹配")
    if not isinstance(change, dict) or change.get("schema") != CHANGE_VERSION:
        raise ValueError("变更记录 schema 无效")
    baseline = inspect_baseline(data["baseline"])
    if identity(baseline) != identity(inspect_baseline(change.get("baseline"))):
        raise ValueError("变更记录和冻结基线不同")
    items = change.get("changes")
    if not isinstance(items, list) or not items:
        raise ValueError("未提供结构化变更")
    contract, _, contract_issues = contract_context(data, policy_data, root or Path.cwd())
    if contract_issues:
        raise next((error for error in contract_issues.values() if isinstance(error, system_contract.ContractConflict)),
                   next(iter(contract_issues.values())))
    planned = select(policy_data, data["mode"], data.get("prototypes", []), data.get("intent", ""),
                     target, data.get("facts"), carried_checks=data.get("checks", {}))
    impacted = {}
    for item in items:
        if (not isinstance(item, dict) or not text(item.get("object")) or not text(item.get("variant"))
                or "before" not in item or "after" not in item or item.get("kind") not in policy_data["changes"]):
            raise ValueError("变更需要已知 kind、object、variant 与 before/after")
        if item["before"] == item["after"]:
            continue
        requested_variant = item["variant"]
        variants = [requested_variant]
        if contract is not None:
            known_variants = contract["baseline"]["variants"]
            subject = next((contract[group][item["object"]] for group in (
                "blocks", "ports", "conditions", "criteria", "decisions", "anchors")
                if item["object"] in contract[group]), None)
            scope = subject["variants"] if subject is not None else known_variants
            if requested_variant == "*":
                variants = scope
            elif requested_variant not in scope:
                raise system_contract.ContractConflict("ECO 变体不属于绑定对象或契约")
        obj = item["object"]
        kind = item["kind"]
        affected_branches = {}
        for check in planned["required_checks"]:
            keys = [branch["id"] for branch in check.get("branches", ())
                    if kind == "unknown" or kind in policy_data["branches"][branch["id"]]["invalidated_by"]]
            if keys:
                affected_branches[check["id"]] = keys
        if kind == "assembly-process":
            affected_branches.setdefault("production-evidence", ["B3"])
        seeds = [*policy_data["changes"][kind], *(
            check["id"] for check in planned["required_checks"]
            if kind in policy_data["checks"][check["id"]].get("invalidated_by", ())
        ), *affected_branches]
        if kind == "unknown":
            seeds = list(dict.fromkeys(seeds + [row["id"] for row in planned["required_checks"]]))
        for variant in variants:
            dynamic = contract_paths(contract, obj, variant) if contract is not None else {}
            queue = deque([(name, [kind, *path]) for name, path in dynamic.items()] +
                          [(name, [kind, name]) for name in seeds])
            visited = set()
            while queue:
                name, path = queue.popleft()
                if name in visited:
                    continue
                visited.add(name)
                entry = impacted.setdefault((variant, obj, name), {"path": path, "branches": []})
                if name in dynamic:
                    entry["contract_path"] = dynamic[name]
                entry["branches"].extend(affected_branches.get(name, ()))
                for dependent in policy_data["checks"][name]["affects"]:
                    # Assembly-only changes do not recheck circuit probe access unless a bound dependency calls for it.
                    if kind == "assembly-process" and name == "factory-capability" and dependent == "test-coverage":
                        continue
                    queue.append((dependent, [*path, dependent]))
    rows = [
        {"variant": variant, "object": obj, "check": check, "path": entry["path"], "status": "recheck",
         **({"contract_path": entry["contract_path"]} if "contract_path" in entry else {}),
         **({"branches": list(dict.fromkeys(entry["branches"]))} if entry["branches"] else {})}
        for (variant, obj, check), entry in impacted.items()
    ]
    affected = {row["check"] for row in rows if row["variant"] in (baseline["variant"], "*")}
    return {
        "schema": "hardware-engineering-impact-v1", "baseline": baseline,
        "recheck": rows,
        "invalidated_baseline_checks": sorted(affected & data.get("checks", {}).keys()),
        "reuse_candidates": sorted(data.get("checks", {}).keys() - affected),
        "reuse_requires_scope_check": True,
    }
