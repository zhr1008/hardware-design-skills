"""Prepare a hardware engineering workflow and read its local rule evidence."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

import engineering_decision as engineering
import reading_map

KNOWLEDGE = Path(__file__).with_name("knowledge.py")
TOPICS = {
    "analog": ("opamp-common-mode", "opamp-linear-output", "analog-capacitive-load",
               "opamp-offset-error", "opamp-bias-error", "opamp-slew-rate"),
    "sampling": ("adc-antialias-budget", "adc-acquisition-settling", "adc-kickback-filter",
                 "reference-error-budget", "reference-transient-load"),
    "filtering": ("filter-source-loading", "filter-q-gain", "filter-high-frequency-stopband",
                  "mlcc-effective-capacitance"),
    "power": ("absolute-max-is-not-operating", "thermal-junction-budget", "pcb-pdn-impedance",
              "mlcc-effective-capacitance", "ripple-measurement-loop"),
    "current-sense": ("current-sense-kelvin", "power-high-current-connections",
                      "resistor-self-heating-ratio", "thermal-board-conditions"),
    "interfaces": ("pcb-edge-rate", "pcb-return-path", "mixed-signal-grounding"),
    "layout": ("pcb-return-path", "pcb-functional-partition", "decoupling-via-pair",
               "drc-rule-coverage"),
    "thermal": ("thermal-junction-budget", "thermal-board-conditions", "absolute-max-is-not-operating"),
    "insulation": ("ipc-conductor-spacing",),
    "fabrication": ("ipc-land-density", "ipc-assembly-courtyard", "ipc-pth-hole-copper-tradeoff",
                    "ipc-datum-fiducial", "msl-floor-life", "pcb-bow-twist-method"),
}
PHASES = {
    "plan": ("requirements", "knowledge", "decision", "handoff"),
    "design": ("requirements", "knowledge", "decision", "implementation", "verification", "handoff"),
    "review": ("requirements", "knowledge", "assessment", "verification", "handoff"),
    "eco": ("baseline", "knowledge", "impact", "decision", "implementation", "reverification", "handoff"),
    "verify": ("requirements", "knowledge", "model_coverage", "verification", "handoff"),
    "bringup": ("baseline", "knowledge", "hypotheses", "observation", "discrimination", "reverification", "handoff"),
    "release": ("baseline", "knowledge", "risk_closure", "release_evidence", "signoff", "handoff"),
}


def query(library, *args):
    command = [sys.executable, "-X", "utf8", "-B", str(KNOWLEDGE)]
    if library is not None:
        command.extend(("--library", str(library)))
    result = subprocess.run(
        command + list(args), encoding="utf-8", capture_output=True, timeout=30, check=False
    )
    if result.returncode:
        raise ValueError(result.stderr.strip() or result.stdout.strip() or "知识库命令执行失败")
    return json.loads(result.stdout)


def rule_arguments(rule_ids):
    return [arg for rule_id in dict.fromkeys(rule_ids) for arg in ("--id", rule_id)]


def start(library, mode, topics, additional_rules, prototype_names=(), intent="", data=None, model_limits=(),
          target=None):
    case = data or {}
    if target and mode not in engineering.TARGET_MODES[target]:
        raise ValueError("工程 mode 与正式交付目标不匹配")
    task_intent = " ".join(filter(None, (case.get("intent", ""), intent)))
    decision = engineering.select(engineering.policy(), mode, [*case.get("prototypes", []), *prototype_names],
                                  task_intent, target,
                                  facts=case.get("facts"), model_limits=[
                                      *model_limits, *(flag for flags in case.get("model_limits", {}).values() for flag in flags)
                                  ], carried_checks=case.get("checks", {}))
    mapped = {name: TOPICS[name] for name in dict.fromkeys(topics)}
    rule_ids = [rule for rules in mapped.values() for rule in rules] + additional_rules
    expanded = data is not None or bool(prototype_names or intent or model_limits or target) or mode not in ("plan", "design", "review")
    all_ids = [*rule_ids, *decision["required_rules"]]
    available = query(library, "rules", "--summary", *rule_arguments(all_ids))["rules"] if all_ids else []
    candidates = available if expanded else [row for row in available if row["id"] in rule_ids]
    return {
        "schema": "hardware-design-flow-v2" if expanded else "hardware-design-flow-v1",
        "mode": mode,
        "phases": PHASES[mode],
        "topic_seeds": mapped,
        "candidate_rules": candidates,
        "has_seed_rules": bool(rule_ids),
        "knowledge_route": reading_map.select(
            mode, mapped, decision["prototypes"], library, task_intent,
            required_themes=[check["knowledge_theme"] for check in decision["required_checks"]
                             if "knowledge_theme" in check]),
        **decision,
    }


def basis(library, rule_ids, theme_ids=(), roles=(), branch_ids=()):
    branches = [{"id": key, **engineering.policy()["branches"][key]} for key in dict.fromkeys(branch_ids)]
    rule_ids = list(dict.fromkeys([*rule_ids, *(rule for branch in branches for rule in branch["rules"])]))
    rules = query(library, "rules", *rule_arguments(rule_ids))["rules"] if rule_ids else []
    if {rule["id"] for rule in rules} != set(rule_ids):
        raise ValueError("规则结果未覆盖请求的编号")
    locations = [item for branch in branches for item in branch["sources"]]
    locations.extend(item for rule in rules for item in rule["evidence"])
    reading = []
    if theme_ids:
        chart = reading_map.load_map()
        docs = reading_map.documents(library or reading_map.SKILL)
        for theme in reading_map.expand(chart, dict.fromkeys(theme_ids), docs, include_further=True, root=library):
            for step in theme["reading_steps"]:
                if roles and step["role_id"] not in roles:
                    continue
                row = {"theme": theme["id"], **step}
                reading.append(row)
                doc = step["document_id"]
                if doc not in docs:
                    continue
                if "pdf_page" in step:
                    locations.append({**step, "source_sha256": docs[doc].get("source_sha256")})
                else:
                    try:
                        hits = query(library, "search", "--doc", doc, "--limit", "3", *step["search_terms"])
                        row["candidates"] = [
                            {key: hit[key] for key in ("locator", "reference") if key in hit}
                            for hit in hits["results"]
                        ]
                    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
                        row["error"] = str(exc)
    pages = {}
    for evidence in locations:
        key = (evidence["document_id"], evidence["pdf_page"])
        if key in pages:
            continue
        doc, number = key
        try:
            page = query(library, "read", doc, str(number))
            source = page.get("document", {})
            text = page.get("text", "")
            if (source.get("id") != doc or page.get("pdf_page") != number
                    or not text.strip() or "该位置尚无可检索文字" in text):
                raise ValueError("返回资料编号、页码或可检索正文不符合请求")
            expected_hash = evidence.get("source", evidence).get("source_sha256")
            if expected_hash and source.get("source_sha256") != expected_hash:
                raise ValueError("本机正文的来源版本与指定页码依据不一致")
            status = "partial" if page.get("next_offset") is not None else "retrieved"
            pages[key] = {"status": status, **page}
        except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
            pages[key] = {"status": "unavailable", "error": str(exc)}
        if "locator" in evidence:
            pages[key]["approved_locator"] = evidence["locator"]
    return {
        "schema": "hardware-design-basis-v1",
        "rules": rules,
        **({"branch_sources": {branch["id"]: branch["sources"] for branch in branches}} if branches else {}),
        **({"related_sources": {branch["id"]: branch["related_sources"] for branch in branches
                                if "related_sources" in branch}} if branches else {}),
        **({"reading_steps": reading} if theme_ids else {}),
        "source_pages": [
            {"document_id": doc, "requested_pdf_page": number, **page}
            for (doc, number), page in pages.items()
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--library", type=Path, help="公开版 knowledge.py 的本地正文库目录")
    sub = parser.add_subparsers(dest="command", required=True)
    initial = sub.add_parser("start", help="给出阶段、实际规则候选和适用条件", allow_abbrev=False)
    initial.add_argument("mode", choices=PHASES)
    initial.add_argument("--topic", action="append", choices=TOPICS, default=[])
    initial.add_argument("--rule", action="append", default=[])
    initial.add_argument("--prototype", action="append", default=[], help="重复指定电路或系统原型")
    initial.add_argument("--intent", default="", help="简短目标描述，匹配明确的原型别名")
    initial.add_argument("--case", type=Path, help="正式或已记录的工程对象，可选")
    initial.add_argument("--target", choices=engineering.TARGET_MODES)
    initial.add_argument("--model-limit", choices=engineering.MODEL_LIMITS, action="append", default=[])
    evidence = sub.add_parser("basis", help="读取选中规则或知识主题的来源页", allow_abbrev=False)
    evidence.add_argument("--rule", action="append", default=[])
    evidence.add_argument("--branch", action="append", default=[], help="读取已选适用分支的原页")
    evidence.add_argument("--theme", action="append", default=[], choices=reading_map.load_map()["themes"])
    evidence.add_argument("--role", action="append", default=[], choices=("theory", "design", "practice", "authority"))
    sub.add_parser("prototypes", help="列出可用原型及别名")
    target = sub.add_parser("assess", help="按正式目标核对当前工况和证据覆盖", allow_abbrev=False)
    target.add_argument("--case", type=Path, required=True)
    target.add_argument("--target", choices=engineering.TARGET_MODES, required=True)
    target.add_argument("--root", type=Path, help="允许读取的证据根目录，默认工程记录所在目录")
    propagation = sub.add_parser("impact", help="计算同版变更的影响范围", allow_abbrev=False)
    propagation.add_argument("--case", type=Path, required=True)
    propagation.add_argument("--change", type=Path, required=True)
    propagation.add_argument("--target", choices=engineering.TARGET_MODES, help="冻结基线的正式交付目标")
    binding = sub.add_parser("bind", help="根据执行回执附加本次工程条件，不授予审批", allow_abbrev=False)
    binding.add_argument("--case", type=Path, required=True)
    binding.add_argument("--evidence", type=Path, required=True)
    for name in ("check", "execution", "condition", "criterion"):
        binding.add_argument("--" + name, required=True)
    binding.add_argument("--branch", action="append", default=[], help="该执行项及工况实际覆盖的分支")
    binding.add_argument("--disposition", choices=("pass", "fail", "not_applicable"), default="pass")
    args = parser.parse_args()
    code = 0
    try:
        if args.command == "basis":
            if not (args.rule or args.theme or args.branch) or (args.role and not args.theme):
                evidence.error("指定 --rule、--branch 或 --theme（--role 筛选主题内的阅读角色）")
            result = basis(args.library, args.rule, args.theme, args.role, args.branch)
        else:
            rules = engineering.policy()
            case_path = getattr(args, "case", None)
            data = engineering.load_case(case_path, rules) if case_path else None
            if args.command == "prototypes":
                result = {"prototypes": rules["prototypes"]}
            elif args.command == "start":
                if data is not None and data["mode"] != args.mode:
                    raise ValueError("工程记录的 mode 与启动 mode 不同")
                result = start(args.library, args.mode, args.topic, args.rule, args.prototype, args.intent,
                               data, args.model_limit, args.target)
            elif args.command == "assess":
                result = engineering.assess(data, rules, args.target, args.root or case_path.resolve().parent)
                code = {"covered": 0, "blocked": 1, "needs_evidence": 2}[result["engineering_evidence"]]
            elif args.command == "impact":
                result = engineering.impact(data, engineering.read_json(args.change), rules, args.target)
            else:
                if any(rules.get("branches", {}).get(key, {}).get("check") != args.check for key in args.branch):
                    raise ValueError("分支不存在或不属于指定检查")
                if args.branch and args.disposition == "not_applicable":
                    raise ValueError("适用分支不能绑定为不适用")
                result = engineering.bind(
                    engineering.read_json(args.evidence), engineering.inspect_baseline(data["baseline"]),
                    args.check, args.condition, args.criterion, args.execution, args.disposition,
                    rules["checks"][args.check]["stages"], args.branch)
    except (ValueError, TypeError, KeyError, OSError, subprocess.TimeoutExpired) as exc:
        parser.exit(2, f"{exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
