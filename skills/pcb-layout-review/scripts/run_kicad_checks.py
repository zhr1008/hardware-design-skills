"""Run native KiCad ERC/DRC on an isolated copy and retain the JSON evidence."""

import argparse
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
    command = [
        executable, platform, kind, "--format", "json", "--units", "mm", "--severity-all",
        "--exit-code-violations", *(["--all-track-errors"] if kind == "drc" else []),
        "--output", str(report), str(source_copy),
    ]
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
                checked = check(report, kind)
                if checked["kicad_version"] != version or Path(checked["source"]).name != source.name:
                    raise ValueError("原生报告绑定的源名称或 KiCad 版本与本次调用不同")
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
    changed = []
    for name, item in inputs.items():
        try:
            current = artifact(local_file(item["path"]))["sha256"]
        except (OSError, ValueError):
            current = None
        if current != item["sha256"]:
            changed.append(name)
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


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("input")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--kicad-cli")
    parser.add_argument("--companion", action="append", default=[], type=Path)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    try:
        source = local_file(args.input)
        if source.suffix.casefold() not in KINDS or args.timeout < 1:
            raise ValueError("输入须为 .kicad_sch 或 .kicad_pcb，timeout 须为正整数")
        executable = str(local_file(args.kicad_cli)) if args.kicad_cli else shutil.which("kicad-cli")
        if not executable:
            raise ValueError("未找到 kicad-cli，使用 --kicad-cli 指定本机可执行文件")
        output = local_file(args.output_dir, input_file=False)
        output.mkdir()
        value = run(source, output, executable=executable,
                    companions=[source.parent / path for path in args.companion], timeout=args.timeout)
        with (output / "evidence.json").open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "invalid_input", "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return {"no_reported_findings": 0, "review_required": 1}.get(value["verification_status"], 2)


if __name__ == "__main__":
    raise SystemExit(main())
