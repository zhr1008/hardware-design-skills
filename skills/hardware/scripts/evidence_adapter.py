"""Package an existing checker result without promoting it to a system-level verdict."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys


SCHEMA = "hardware-evidence-envelope-v1"
SKILLS = Path(__file__).absolute().parents[2]
EXECUTION = {"completed", "failed", "timed_out", "not_executed", "unsupported"}
MUTATION = {"unchanged", "changed", "not_applicable", "outcome_unknown"}
VERIFICATION = {
    "pass", "fail", "no_reported_findings", "review_required", "coverage_incomplete",
    "invalid", "missing", "blocked", "not_evaluated",
}
STAGES = {"saved_artifact", "native_eda", "release_package", "bench_record", "simulation", "cam_readback"}
ADAPTERS = {
    "kicad": "pcb-layout-review/scripts/check_kicad_report.py",
    "release": "release-pcba-fabrication/scripts/validate_release_manifest.py",
    "bench": "hardware-design-review/scripts/check_bench_results.py",
}


def strict_json(raw):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"重复 JSON 字段：{key}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"无效 JSON 常量：{value}")

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("JSON 数值超出有限浮点范围")
        return number

    return json.loads(raw, object_pairs_hook=unique_object,
                      parse_constant=invalid_constant, parse_float=finite_float)


def artifact(path, digest=None):
    if digest is None:
        calculated = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                calculated.update(chunk)
        digest = calculated.hexdigest()
    return {"path": str(path.absolute()), "sha256": digest.lower()}


def skipped(check, reason):
    return {"check": check, "reason": reason}


def envelope(*, backend, stage, verification, native, inputs=None, outputs=None,
             executed=(), skipped_checks=(), execution="completed",
             mutation="unchanged", coverage=None):
    value = {
        "schema": SCHEMA,
        "backend": backend,
        "evidence_stage": stage,
        "execution_status": execution,
        "mutation_outcome": mutation,
        "verification_status": verification,
        "checks_executed": list(executed),
        "checks_skipped": list(skipped_checks),
        "inputs": inputs or {},
        "outputs": outputs or {},
        "coverage": coverage or {},
        "native": native,
    }
    validate(value)
    return value


def validate(value):
    fields = {
        "schema", "backend", "evidence_stage", "execution_status", "mutation_outcome",
        "verification_status", "checks_executed", "checks_skipped", "inputs", "outputs",
        "coverage", "native",
    }
    if not isinstance(value, dict) or set(value) != fields or value["schema"] != SCHEMA:
        raise ValueError("证据需要受支持的 schema 和完整包络字段")
    text = lambda item: isinstance(item, str) and bool(item.strip())
    if not text(value["backend"]):
        raise ValueError("backend 需要非空文本")
    for field, allowed in (
        ("evidence_stage", STAGES), ("execution_status", EXECUTION),
        ("mutation_outcome", MUTATION), ("verification_status", VERIFICATION),
    ):
        if not text(value[field]) or value[field] not in allowed:
            raise ValueError(f"{field} 不在合同枚举中")
    for field in ("inputs", "outputs"):
        if not isinstance(value[field], dict):
            raise ValueError(f"{field} 需要工件映射")
        for label, item in value[field].items():
            if (not text(label) or not isinstance(item, dict) or set(item) != {"path", "sha256"}
                    or not text(item["path"]) or not text(item["sha256"])
                    or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])):
                raise ValueError(f"{field}.{label} 需要路径及小写 SHA-256")
    if any(not isinstance(value[field], dict) for field in ("coverage", "native")):
        raise ValueError("coverage 与 native 需要对象")
    done = value["checks_executed"]
    omitted = value["checks_skipped"]
    if not isinstance(done, list) or not all(text(item) for item in done):
        raise ValueError("checks_executed 需要检查名称列表")
    if not isinstance(omitted, list) or any(
        not isinstance(item, dict) or set(item) != {"check", "reason"}
        or not all(map(text, item.values())) for item in omitted
    ):
        raise ValueError("checks_skipped 需要检查名称与原因")
    check_names = done + [item["check"] for item in omitted]
    if len(check_names) != len(set(check_names)):
        raise ValueError("同一检查只能记录一次")
    if (
        value["verification_status"] in {"pass", "fail", "no_reported_findings"}
        and (value["execution_status"] != "completed" or not done)
    ):
        raise ValueError("通过、失败与无报告问题需要已完成的检查")
    if value["verification_status"] in {"pass", "fail", "no_reported_findings"} and not (
        value["inputs"] or value["outputs"]
    ):
        raise ValueError("通过、失败与无报告问题需要至少一项可定位工件")
    if (
        value["verification_status"] in {"pass", "no_reported_findings"}
        and value["mutation_outcome"] == "outcome_unknown"
    ):
        raise ValueError("修改结果未知时不能给出通过或无报告问题")


def saved_kicad(report, path, digest, *, missing=False):
    status = report["status"]
    valid = status != "invalid_input"
    coverage = {
        "included_severities": report.get("included_severities"),
        "missing_severities": report.get("missing_severities"),
        "ignored_checks": report.get("ignored_checks"),
        "native_rule_execution": "unverified",
    }
    return envelope(
        backend="kicad-report-check", stage="saved_artifact",
        verification="missing" if missing else status if valid else "invalid", native=report,
        executed=["report_readback"] if valid else [],
        skipped_checks=[
            skipped("native_erc_drc", "输入为已有报告，未执行原生规则"),
            *([] if valid else [skipped("report_readback", "报告缺失或格式无效")]),
        ],
        inputs={"report": artifact(path, digest)} if digest else {},
        coverage=coverage,
    )


def saved_release(report, path, digest, *, identity, invalid=False, missing=False, artifacts=None):
    status = report["status"]
    verified = not invalid and not missing
    return envelope(
        backend="release-manifest-validator", stage="release_package",
        verification="missing" if missing else "invalid" if invalid else status.lower(), native=report,
        executed=["manifest_package_validation"] if verified else [],
        skipped_checks=[
            skipped("repeat_eda_drc_or_approval", "发布检查读取已有验证和审批记录"),
            *([] if verified else [skipped("manifest_package_validation", "清单缺失或合同无效")]),
        ],
        inputs={**({"manifest": artifact(path, digest)} if digest else {}),
                **{f"package:{role}": item for role, item in (artifacts or {}).items()}},
        coverage={"scope": "清单合同、版次、文件尺寸与摘要、适用的 BOM/CPL 装配对账",
                  "release_identity": identity},
    )


def saved_bench(report, limits, measurements, hashes, *, missing=False):
    executed = ["compare:" + item["test_id"] for item in report.get("results", [])
                if item["status"] in {"pass", "fail"}]
    omitted = [skipped("compare:" + item["test_id"], item["reason"])
               for item in report.get("results", []) if item["status"] in {"invalid", "missing"}]
    if not report.get("results"):
        omitted.append(skipped("compare_measurements", "缺少可读的限值或有效测量输入"))
    return envelope(
        backend="bench-result-checker", stage="bench_record",
        verification="missing" if missing else report["status"], native=report, executed=executed,
        skipped_checks=[skipped("physical_measurement", "仅读回已有测量记录"), *omitted],
        inputs={role: artifact(path, hashes[role]) for role, path in
                (("limits", limits), ("measurements", measurements)) if role in hashes},
        coverage={"device_identity_readback": "unverified", "limit_set_id": report.get("limit_set_id")},
    )


def verify_artifacts(value):
    from hardware_tool import local_file

    results = []
    for direction in ("inputs", "outputs"):
        for label, item in value[direction].items():
            result = {"role": f"{direction}.{label}", "expected_sha256": item["sha256"]}
            try:
                path = Path(item["path"])
                if not path.is_absolute():
                    raise ValueError("证据工件须使用本地绝对路径")
                actual = artifact(local_file(path, input_file=False))["sha256"]
                result.update(actual_sha256=actual, status="match" if actual == item["sha256"] else "changed")
            except FileNotFoundError:
                result["status"] = "missing"
            except (OSError, ValueError) as error:
                result.update(status="unreadable", reason=str(error))
            results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(dest="adapter", required=True)
    kicad = commands.add_parser("kicad", allow_abbrev=False)
    kicad.add_argument("report")
    kicad.add_argument("--kind", choices=("erc", "drc"))
    commands.add_parser("release", allow_abbrev=False).add_argument("manifest")
    bench = commands.add_parser("bench", allow_abbrev=False)
    bench.add_argument("limits")
    bench.add_argument("--measurements", required=True)
    validator = commands.add_parser("validate", allow_abbrev=False)
    validator.add_argument("envelope", type=Path)
    validator.add_argument("--verify-artifacts", action="store_true", help="读回本机工件并核对 SHA-256")
    args = parser.parse_args()
    if args.adapter == "validate":
        try:
            value = strict_json(args.envelope.read_bytes())
            validate(value)
        except (OSError, ValueError) as error:
            parser.exit(2, f"无效证据包络：{error}\n")
        result = {"status": "valid_format", "schema": SCHEMA}
        if args.verify_artifacts:
            result["artifacts"] = verify_artifacts(value)
            result["status"] = ("artifacts_match" if result["artifacts"] and
                                all(item["status"] == "match" for item in result["artifacts"])
                                else "artifact_verification_incomplete")
        print(json.dumps(result, ensure_ascii=False))
        return 2 if result["status"] == "artifact_verification_incomplete" else 0
    options = {
        "kicad": lambda: [args.report, *([f"--kind={args.kind}"] if args.kind else [])],
        "release": lambda: [args.manifest, "--confine-to-manifest-dir"],
        "bench": lambda: [f"--limits={args.limits}", f"--measurements={args.measurements}"],
    }
    return subprocess.run(
        [sys.executable, "-X", "utf8", "-B", str(SKILLS / ADAPTERS[args.adapter]),
         "--formal", *options[args.adapter]()], check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
