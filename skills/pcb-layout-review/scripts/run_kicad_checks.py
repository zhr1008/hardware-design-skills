"""Run native KiCad checks on an isolated copy and retain the saved-state evidence."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import sys

from check_kicad_report import check

sys.path.insert(0, str(Path(__file__).absolute().parents[2] / "hardware/scripts"))
from evidence_adapter import artifact, envelope, skipped
from hardware_tool import local_file


KINDS = {".kicad_sch": ("sch", "erc"), ".kicad_pcb": ("pcb", "drc")}
SHEET_FILE = re.compile(r'\(property\s+"Sheet ?[Ff]ile"\s+("(?:[^"\\]|\\.)*")')
VERSION = re.compile(r"(?:9|10)\.[0-9]+\.[0-9]+")


def input_bundle(source, companions):
    root = source.parent
    known = {source}
    candidates = (source.with_suffix(".kicad_pro"), source.with_suffix(".kicad_dru"),
                  root / "sym-lib-table", root / "fp-lib-table")
    pending = [source, *(path for path in candidates if os.path.lexists(path)), *companions]
    inspected = set()
    while pending:
        candidate = local_file(pending.pop())
        if not candidate.is_relative_to(root):
            raise ValueError(f"伴随文件必须位于输入文件所在目录：{candidate}")
        if candidate in inspected:
            continue
        inspected.add(candidate)
        known.add(candidate)
        if candidate.suffix.casefold() != ".kicad_sch":
            continue
        for match in SHEET_FILE.finditer(candidate.read_text(encoding="utf-8-sig")):
            reference = json.loads(match[1])
            child = PureWindowsPath(reference)
            if child.drive or child.root or "${" in reference:
                raise ValueError(f"层次原理图路径需要可复制的相对本机路径：{reference}")
            pending.append(candidate.parent.joinpath(*child.parts))
    return sorted(known)


def process(arguments, directory, environment, timeout, *, log=None):
    options = {
        "cwd": directory, "env": environment, "timeout": timeout, "check": False,
        "stdin": subprocess.DEVNULL, "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
    }
    try:
        if log:
            with log.open("xb") as stream:
                return subprocess.run(
                    arguments, stdout=stream, stderr=subprocess.STDOUT, **options,
                ), None
        return subprocess.run(
            arguments, capture_output=True, encoding="utf-8", errors="replace", **options,
        ), None
    except subprocess.TimeoutExpired:
        return None, "timed_out"
    except OSError:
        return None, "failed"


def stage_stock_tables(executable, version, config):
    major, minor, _ = version.split(".")
    binary_dir = Path(executable).resolve().parent
    configured = os.environ.get(f"KICAD{major}_TEMPLATE_DIR")
    candidates = [
        *([Path(configured)] if configured else []),
        binary_dir.parent / "share/kicad/template",
        binary_dir.parent / "SharedSupport/template",
        Path("/usr/share/kicad/template"), Path("/usr/local/share/kicad/template"),
    ]
    table_names = ("sym-lib-table", "fp-lib-table")
    templates = next((directory for directory in candidates
                      if all((directory / name).is_file() for name in table_names)), None)
    if templates is None:
        return {}
    profile = config / f"{major}.{minor}"
    profile.mkdir(exist_ok=True)
    records = {}
    for name in table_names:
        source = templates / name
        dest = profile / name
        shutil.copyfile(source, dest)
        records[f"stock:{name}"] = artifact(source, artifact(dest)["sha256"])
    return records


def rule_command(executable, platform, kind, report, source_copy, *, parity=False):
    return [
        executable, platform, kind, "--format", "json", "--units", "mm", "--severity-all",
        "--exit-code-violations", *(["--all-track-errors"] if kind == "drc" else []),
        *(["--schematic-parity"] if parity else []), "--output", str(report), str(source_copy),
    ]


def bound_rule_report(report, kind, source, version):
    checked = check(report, kind)
    if checked["kicad_version"] != version or Path(checked["source"]).name != source.name:
        raise ValueError("原生报告绑定的源名称或 KiCad 版本与本次调用不同")
    return checked


def changed_artifacts(records):
    changed = []
    for name, item in records.items():
        try:
            current = artifact(local_file(item["path"]))["sha256"]
        except (OSError, ValueError):
            current = None
        if current != item["sha256"]:
            changed.append(name)
    return changed


def run(source, directory, *, executable, companions=(), timeout=120):
    platform, kind = KINDS[source.suffix.casefold()]
    work = directory / "source-copy"
    config_home = directory / "config"
    documents_home = directory / "documents"
    paths = input_bundle(source, companions)
    inputs = {path.relative_to(source.parent).as_posix(): artifact(path) for path in paths}
    for child in (work, config_home, documents_home):
        child.mkdir()
    for path in paths:
        dest = work / path.relative_to(source.parent)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
        if artifact(dest)["sha256"] != inputs[path.relative_to(source.parent).as_posix()]["sha256"]:
            raise ValueError(f"源文件在快照期间发生变化：{path}")

    environment = {
        **os.environ, "KICAD_CONFIG_HOME": str(config_home),
        "KICAD_DOCUMENTS_HOME": str(documents_home),
    }
    report = directory / f"{kind}.json"
    log = directory / "native.log"
    source_copy = work / source.name
    command = rule_command(executable, platform, kind, report, source_copy)
    ver, probe_error = process([executable, "version"], work, environment, min(timeout, 15))
    version = ver.stdout.strip() if ver and ver.returncode == 0 else None
    native = {"command": command, "engine_version": version, "returncode": None, "report": None}
    omitted = [skipped("individual_rule_execution", "KiCad JSON 没有逐规则执行清单")]
    if kind == "drc":
        omitted.append(skipped("schematic_parity", "本次 DRC 未启用与原理图的一致性检查"))
    omitted.append(skipped("board_acceptance", "原生规则报告只覆盖指定输入和当前检查配置"))
    executed = []
    execution = "not_executed"
    verification = "not_evaluated"
    stock = stage_stock_tables(executable, version, config_home) if (
        kind == "erc" and version is not None and VERSION.fullmatch(version)
    ) else {}
    inputs.update(stock)
    if probe_error or version is None or VERSION.fullmatch(version) is None:
        execution = probe_error or ("failed" if version is None else "unsupported")
        native["error"] = "KiCad 版本探测失败或不是受支持的稳定 9.x/10.x 版本"
        omitted.append(skipped(f"native_{kind}", native["error"]))
    elif kind == "erc" and not stock:
        native["error"] = "缺少可复制到隔离配置的 KiCad 标准 sym-lib-table/fp-lib-table"
        omitted.append(skipped("native_erc", native["error"]))
    else:
        result, error = process(command, work, environment, timeout, log=log)
        native["returncode"] = result.returncode if result else None
        if error or result.returncode not in (0, 5):
            execution = error or "failed"
            native["error"] = "原生检查超时或返回工具错误"
            omitted.append(skipped(f"native_{kind}", native["error"]))
        else:
            execution = "completed"
            executed.append(f"native_{kind}")
            try:
                checked = bound_rule_report(report, kind, source, version)
                if result.returncode == 5 and checked["status"] == "no_reported_findings":
                    raise ValueError("原生违规退出码与零发现报告不一致")
                native["report"] = checked
                verification = checked["status"]
                executed.append("report_readback")
            except (OSError, ValueError) as exc:
                verification = "missing" if isinstance(exc, FileNotFoundError) else "invalid"
                native["error"] = str(exc)
    if "report_readback" not in executed:
        omitted.append(skipped("report_readback", native.get("error") or "没有可用原生报告"))
    changed = changed_artifacts(inputs)
    if changed:
        verification = "invalid"
        native["source_changed_or_unreadable"] = changed
    return envelope(
        backend="kicad-cli", stage="native_eda", execution=execution,
        mutation="outcome_unknown" if changed else "unchanged", verification=verification, native=native,
        inputs=inputs, outputs={path.stem: artifact(path) for path in (report, log) if path.is_file()},
        executed=executed, skipped_checks=omitted,
        coverage={
            "requested_severities": ["error", "warning", "exclusion"],
            "included_severities": (native["report"] or {}).get("included_severities"),
            "missing_severities": (native["report"] or {}).get("missing_severities"),
            "ignored_checks": (native["report"] or {}).get("ignored_checks"),
            "saved_project_settings_included": source.with_suffix(".kicad_pro") in paths,
        },
    )


def run_paired(board, schematic, intent, directory, *, executable, companions=(), timeout=120):
    from kicad_saved_readback import compare_graphs, expected_contract, read_board, read_schematic

    inputs = {}
    outputs = {}
    executed = []
    omissions = {
        "saved_identity": "还未核对联合保存态工件",
        "native_erc": "还未执行原理图规则检查",
        "erc_report_readback": "还没有可读的原理图规则报告",
        "native_drc": "还未执行 PCB 规则检查",
        "drc_report_readback": "还没有可读的 PCB 规则报告",
        "native_schematic_parity": "还未取得原生一致性检查已执行的日志与报告",
        "native_schematic_export": "还未执行原生 XML 网表导出",
        "schematic_connectivity": "还没有可用的保存态原理图图谱",
        "pcb_connectivity": "还没有可用的保存态 PCB 焊盘图谱",
        "individual_rule_execution": "KiCad JSON 没有逐规则执行清单",
        "board_acceptance": "连通性和原生规则报告只覆盖声明的保存态工件与规则配置",
    }
    native = {"identity": {}, "connectivity": {}, "engine_version": None, "commands": {}}
    coverage = {"requested_severities": ["error", "warning", "exclusion"],
                "variant_scope": "materialized_saved_files",
                "schematic_scope": "native_xml_components_sheet_paths_and_pin_memberships",
                "pcb_scope": "footprint_reference_and_numbered_pad_net"}

    def done(name):
        executed.append(name)
        del omissions[name]

    def finish(execution, verification, mutation="unchanged"):
        return envelope(
            backend="kicad-cli", stage="native_eda", execution=execution,
            mutation=mutation, verification=verification, native=native, inputs=inputs, outputs=outputs,
            executed=executed, skipped_checks=[skipped(name, reason) for name, reason in omissions.items()],
            coverage=coverage,
        )

    source_paths = {}
    errors = {}
    error_status = "missing"
    for role, supplied in (("board", board), ("schematic", schematic), ("intent", intent)):
        try:
            path = local_file(supplied, input_file=False)
            if not path.exists():
                raise FileNotFoundError(f"找不到 {role} 输入：{path}")
            path = local_file(path)
            source_paths[role] = path
            inputs[role] = artifact(path)
        except (OSError, ValueError) as error:
            if not isinstance(error, FileNotFoundError):
                error_status = "invalid"
            errors[role] = str(error)
    if errors:
        native["identity"] = {"status": error_status, "errors": errors}
        omissions["saved_identity"] = "缺少或无法读取联合读回输入"
        return finish("not_executed", error_status)
    board, schematic, intent = (source_paths[role] for role in ("board", "schematic", "intent"))
    try:
        raw = intent.read_bytes()
        if hashlib.sha256(raw).hexdigest() != inputs["intent"]["sha256"]:
            native["identity"] = {"status": "invalid", "error": "读回合同在取证期间发生变化"}
            omissions["saved_identity"] = native["identity"]["error"]
            return finish("failed", "invalid", "outcome_unknown")
        contract, expected_schematic, expected_pcb = expected_contract(raw)
    except (OSError, ValueError) as error:
        native["identity"] = {"status": "invalid", "error": str(error)}
        omissions["saved_identity"] = "无法读取有效的读回合同"
        return finish("not_executed", "invalid")
    identity = {"revision": contract["revision"], "variant": contract["variant"]}
    native["identity"] = identity
    if (board.suffix.casefold() != ".kicad_pcb" or schematic.suffix.casefold() != ".kicad_sch"
            or board.parent != schematic.parent or board.stem != schematic.stem):
        identity.update(status="fail", error="PCB 与根原理图须为同目录、同文件基名的一对保存态文件")
        done("saved_identity")
        return finish("completed", "fail")
    try:
        paths = input_bundle(board, [schematic, *companions])
        saved = {path.relative_to(board.parent).as_posix(): artifact(path) for path in paths}
    except (OSError, ValueError) as error:
        identity.update(status="coverage_incomplete", error=str(error))
        omissions["saved_identity"] = "无法构成完整的联合保存态副本"
        return finish("not_executed", "coverage_incomplete")
    if any(saved[path.name]["sha256"] != inputs[role]["sha256"]
           for role, path in (("board", board), ("schematic", schematic))):
        identity.update(status="invalid", error="根原理图或 PCB 在建立保存态清单期间发生变化")
        return finish("failed", "invalid", "outcome_unknown")
    inputs = {"intent": inputs["intent"], **{f"saved:{name}": item for name, item in saved.items()}}
    declared = contract["sources"]
    missing = sorted(declared.keys() - saved.keys())
    extra = sorted(saved.keys() - declared.keys())
    mismatches = {name: {"expected": declared[name], "actual": saved[name]["sha256"]}
                  for name in sorted(declared.keys() & saved.keys()) if declared[name] != saved[name]["sha256"]}
    identity.update(
        status="fail" if missing or mismatches else "coverage_incomplete" if extra else "pass",
        missing_from_snapshot=missing, not_declared=extra, sha256_mismatches=mismatches,
    )
    done("saved_identity")
    coverage["saved_project_settings_included"] = board.with_suffix(".kicad_pro").name in saved

    work = directory / "source-copy"
    config = directory / "config"
    documents = directory / "documents"
    try:
        for child in (work, config, documents):
            child.mkdir()
        for name, item in saved.items():
            copy = work / name
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item["path"], copy)
            outputs[f"snapshot:{name}"] = artifact(copy)
            if outputs[f"snapshot:{name}"]["sha256"] != item["sha256"]:
                raise ValueError(f"源文件在快照期间发生变化：{name}")
    except (OSError, ValueError) as error:
        native["snapshot_error"] = str(error)
        changed = changed_artifacts(inputs)
        native["source_changed_or_unreadable"] = changed
        return finish("failed", "invalid", "outcome_unknown" if changed or isinstance(error, ValueError) else "unchanged")

    environment = {
        **os.environ, "KICAD_CONFIG_HOME": str(config), "KICAD_DOCUMENTS_HOME": str(documents),
    }
    ver, probe_error = process([executable, "version"], work, environment, min(timeout, 15))
    version = ver.stdout.strip() if ver and ver.returncode == 0 else None
    native["engine_version"] = version
    execution_errors = []
    verification_statuses = [identity["status"]]

    def invoke(name, command, product, valid_codes):
        log = directory / f"{name}.log"
        result, error = process(command, work, environment, timeout, log=log)
        code = result.returncode if result else None
        entry = {"command": command, "returncode": code, "execution_status": "completed"}
        native["commands"][name] = entry
        for path in (log, product):
            if path.is_file():
                outputs[path.name] = artifact(path)
        if error or code not in valid_codes:
            execution_errors.append(error or "failed")
            entry["execution_status"] = error or "failed"
            entry["error"] = f"原生命令超时（{timeout} s）" if error == "timed_out" else "原生命令启动或执行失败"
        return entry

    if probe_error or version is None or VERSION.fullmatch(version) is None:
        execution_errors.append(probe_error or ("failed" if version is None else "unsupported"))
        native["version_error"] = "KiCad 版本探测失败或不是受支持的稳定 9.x/10.x 版本"
        for name in ("native_erc", "native_drc", "native_schematic_export"):
            omissions[name] = native["version_error"]
    else:
        inputs.update(stock := stage_stock_tables(executable, version, config))
        profile = config / ".".join(version.split(".")[:2])
        profile.mkdir(exist_ok=True)
        # Use a fixed locale only in the isolated profile so parity execution can be read from the log.
        (profile / "kicad_common.json").write_text('{"system":{"language":"English"}}\n', encoding="utf-8")
        for platform, kind, source in (("sch", "erc", schematic), ("pcb", "drc", board)):
            check_name = f"native_{kind}"
            if kind == "erc" and not stock:
                omissions[check_name] = "缺少 KiCad 标准库表，无法在隔离配置执行 ERC"
                verification_statuses.append("coverage_incomplete")
                continue
            report = directory / f"{kind}.json"
            command = rule_command(executable, platform, kind, report, work / source.name, parity=kind == "drc")
            entry = invoke(kind, command, report, (0, 5))
            if "error" in entry:
                omissions[check_name] = entry["error"]
                continue
            done(check_name)
            try:
                checked = bound_rule_report(report, kind, source, version)
                findings = sum(checked["counts"].values())
                if entry["returncode"] == 5 and not findings:
                    raise ValueError("原生违规退出码与零发现报告不一致")
                entry["report"] = checked
                done(f"{kind}_report_readback")
                coverage[kind] = {key: checked[key] for key in
                                  ("included_severities", "missing_severities", "ignored_checks")}
                if checked["status"] == "coverage_incomplete" or checked["ignored_checks"] is None:
                    verification_statuses.append("coverage_incomplete")
                if checked["ignored_checks"]:
                    verification_statuses.append("coverage_incomplete")
                if findings:
                    verification_statuses.append("review_required")
                if kind == "drc":
                    log = (directory / "drc.log").read_text(encoding="utf-8", errors="replace")
                    parity_count = re.search(r"(?m)^Found (\d+) schematic parity issues\s*$", log)
                    reported = checked["groups"]["schematic_parity"]
                    if parity_count and int(parity_count[1]) == sum(reported.values()):
                        done("native_schematic_parity")
                        coverage["native_schematic_parity"] = "executed"
                        if reported["error"] or reported["warning"]:
                            verification_statuses.append("fail")
                    else:
                        coverage["native_schematic_parity"] = "unconfirmed"
                        verification_statuses.append("coverage_incomplete")
            except (OSError, ValueError) as error:
                omissions[f"{kind}_report_readback"] = str(error)
                verification_statuses.append("missing" if isinstance(error, FileNotFoundError) else "invalid")

        netlist = directory / "schematic.xml"
        command = [executable, "sch", "export", "netlist", "--format", "kicadxml",
                   "--output", str(netlist), str(work / schematic.name)]
        entry = invoke("netlist", command, netlist, (0,))
        if "error" in entry:
            omissions["native_schematic_export"] = entry["error"]
        else:
            done("native_schematic_export")
            try:
                result = compare_graphs(expected_schematic, read_schematic(netlist, work / schematic.name, version))
                native["connectivity"]["schematic"] = result
                verification_statuses.append(result["status"])
                done("schematic_connectivity")
            except (OSError, ValueError) as error:
                omissions["schematic_connectivity"] = str(error)
                verification_statuses.append("missing" if isinstance(error, FileNotFoundError) else "invalid")

    try:
        result = compare_graphs(expected_pcb, read_board(work / board.name))
        native["connectivity"]["pcb"] = result
        verification_statuses.append(result["status"])
        done("pcb_connectivity")
    except (OSError, ValueError) as error:
        omissions["pcb_connectivity"] = str(error)
        verification_statuses.append("missing" if isinstance(error, FileNotFoundError) else "invalid")

    changed = changed_artifacts(inputs)
    if changed:
        native["source_changed_or_unreadable"] = changed
    changed_copies = changed_artifacts({key: item for key, item in outputs.items() if key.startswith("snapshot:")})
    if changed_copies:
        native["snapshot_changed_or_unreadable"] = changed_copies
    execution = next((status for status in ("timed_out", "failed", "unsupported")
                      if status in execution_errors), "completed")
    if changed or changed_copies:
        return finish(execution, "invalid", "outcome_unknown" if changed else "unchanged")
    if execution != "completed":
        verification_statuses = [status for status in verification_statuses if status != "fail"]
        verification_statuses.append("coverage_incomplete")
    status = next((value for value in ("invalid", "fail", "missing", "coverage_incomplete", "review_required")
                   if value in verification_statuses), "pass")
    return finish(execution, status)


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("input")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--kicad-cli")
    parser.add_argument("--companion", action="append", default=[], type=Path)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--schematic", help="同目录同基名的保存态根原理图")
    parser.add_argument("--expected-readback", help="预先声明的 kicad-saved-readback-v1 JSON")
    args = parser.parse_args()
    try:
        paired = args.schematic is not None or args.expected_readback is not None
        if paired and (args.schematic is None or args.expected_readback is None):
            raise ValueError("--schematic 和 --expected-readback 须同时提供")
        source = Path(os.path.abspath(args.input)) if paired else local_file(args.input)
        if (not paired and source.suffix.casefold() not in KINDS) or args.timeout < 1:
            raise ValueError("输入须为 .kicad_sch 或 .kicad_pcb，timeout 须为正整数")
        executable = str(local_file(args.kicad_cli)) if args.kicad_cli else shutil.which("kicad-cli")
        if not executable:
            raise ValueError("未找到 kicad-cli，使用 --kicad-cli 指定本机可执行文件")
        output = local_file(args.output_dir, input_file=False)
        output.mkdir()
        options = dict(executable=executable, companions=[source.parent / path for path in args.companion],
                       timeout=args.timeout)
        if paired:
            value = run_paired(source, args.schematic, args.expected_readback, output, **options)
        else:
            value = run(source, output, **options)
        with (output / "evidence.json").open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "invalid_input", "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return {"no_reported_findings": 0, "pass": 0, "fail": 1, "review_required": 1}.get(
        value["verification_status"], 2,
    )


if __name__ == "__main__":
    raise SystemExit(main())
