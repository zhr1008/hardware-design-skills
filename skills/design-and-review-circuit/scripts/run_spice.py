"""Run a local ngspice batch deck and verify named measurements against explicit limits."""

import argparse
from decimal import Decimal
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).absolute().parents[2] / "hardware/scripts"))
from evidence_adapter import artifact, envelope, skipped, strict_json
from hardware_tool import local_file


SCHEMA = "hardware-spice-input-v1"
NAME = re.compile(r"[a-z][a-z0-9_]*")
LOCAL_NAME = re.compile(r"[\w.+-]+", re.ASCII)
ALLOWED_DIRECTIVES = set("""
    .ac .dc .end .ends .func .global .ic .include .meas .measure .model .nodeset
    .op .options .option .param .save .subckt .temp .title .tran
""".split())
ANALYSIS_DIRECTIVES = {".ac", ".dc", ".op", ".tran"}
MEASUREMENT = re.compile(
    r"^\s*([a-z][a-z0-9_]*)\s*=\s*([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)"
    r"(?:[eE][+-]?[0-9]+)?)(?:\s|$)", re.IGNORECASE,
)
SOLVER_FAILURE = re.compile(
    r"(?im)^\s*(?:fatal\s+error|error(?=\s*[:\s])|(?:doAnalyses:\s*)?timestep too small"
    r"|(?:dc|transient|ac) solution failed|(?:tran|dc|ac) simulation\(s\) aborted)"
)
MEASUREMENT_ERROR = re.compile(r"(?i)^\s*error:\s*(?:measure|meas)\b")


def path_name(value):
    if not isinstance(value, str) or not LOCAL_NAME.fullmatch(value) or value in {".", ".."}:
        raise ValueError("网表和模型只支持与输入 JSON 同级的本地普通文件名")
    return value


def input_data(spec):
    if (not isinstance(spec, dict) or set(spec) != {"schema", "netlist", "model_files", "measurements"}
            or spec["schema"] != SCHEMA):
        raise ValueError("仿真输入合同不符")
    deck = path_name(spec["netlist"])
    if not isinstance(spec["model_files"], list):
        raise ValueError("model_files 需要模型文件名列表")
    names = list(map(path_name, spec["model_files"]))
    if len({name.casefold() for name in [deck, *names]}) != len(names) + 1:
        raise ValueError("网表和模型文件名不得重复")
    measures = spec["measurements"]
    if not isinstance(measures, dict) or not measures:
        raise ValueError("measurements 需要至少一项限值")
    for name, limit in measures.items():
        if (not NAME.fullmatch(name) or not isinstance(limit, dict) or set(limit) - {"unit", "min", "max"}
                or not isinstance(limit.get("unit"), str) or not limit["unit"].strip()
                or not ({"min", "max"} & limit.keys())):
            raise ValueError(f"{name} 需要小写量测名、单位和至少一个 min 或 max")
        bounds = [limit[key] for key in ("min", "max") if key in limit]
        if (any(type(number) not in (int, float) or not math.isfinite(number) for number in bounds)
                or bounds != sorted(bounds)):
            raise ValueError(f"{name} 的限值不是有序有限数值")
    return deck, names, measures


def parse_deck(contents, deck, models, measures):
    parsed = {}
    definitions = {}
    conditions = []
    analyses = set()

    def visit(name, ancestors):
        if name in ancestors:
            raise ValueError(f"检测到循环模型引用：{name}")
        if name in parsed:
            return
        lines = contents[name].decode("utf-8-sig").splitlines()
        if name == deck:
            lines = lines[1:]
        commands = []
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("*"):
                continue
            if line.startswith("+"):
                if not commands:
                    raise ValueError(f"{name} 的续行缺少上一行")
                commands[-1] += " " + line[1:].strip()
            else:
                commands.append(line)
        parsed[name] = commands

        for command in commands:
            keyword, *tail = command.split(maxsplit=1)
            keyword = keyword.casefold()
            if re.search(r"(?i)\bfile\s*=|`|\$\{", command):
                raise ValueError(f"{name} 包含未纳入快照的外部引用")
            if keyword.startswith(".") and keyword not in ALLOWED_DIRECTIVES:
                raise ValueError(f"{name} 含不支持的指令：{keyword}")
            if keyword == ".include":
                model = path_name(tail[0].strip("\"'")) if tail else None
                if model not in models:
                    raise ValueError(f"{name} 引用了未声明的模型：{model}")
                visit(model, (*ancestors, name))
            if keyword in ANALYSIS_DIRECTIVES:
                analyses.add(keyword)
            if keyword in ANALYSIS_DIRECTIVES | {".temp", ".option", ".options"}:
                conditions.append({"file": name, "directive": command})
            if keyword in {".meas", ".measure"}:
                args = tail[0].split(maxsplit=2) if tail else []
                if len(args) != 3 or not NAME.fullmatch(args[1].casefold()) or args[1].casefold() in definitions:
                    raise ValueError(f"{name} 含无效或重复的 .measure 定义")
                definitions[args[1].casefold()] = command

    visit(deck, ())
    if (not analyses or set(parsed) != set(contents) or set(measures) != set(definitions)
            or not parsed[deck] or parsed[deck][-1].casefold() != ".end"):
        raise ValueError("主网表需要分析指令和末尾 .end，全部模型及量测定义须与输入清单一致")
    return definitions, conditions


def read_measures(log, limits):
    found = {name: [] for name in limits}
    for line in log.splitlines():
        match = MEASUREMENT.match(line)
        if match and (name := match[1].casefold()) in found:
            found[name].append(Decimal(match[2]))
    results = {}
    for name, values in found.items():
        limit = limits[name]
        result = {"unit": limit["unit"]}
        if len(values) != 1:
            result["status"] = "missing" if not values else "invalid"
        else:
            value = values[0]
            passed = (("min" not in limit or Decimal(str(limit["min"])) <= value)
                      and ("max" not in limit or value <= Decimal(str(limit["max"]))))
            result.update(status="pass" if passed else "fail", value=str(value))
        results[name] = result
    return results


def run(spec_path, output, executable, timeout):
    spec_raw = spec_path.read_bytes()
    deck, models, limits = input_data(strict_json(spec_raw))
    paths = {name: local_file(spec_path.parent / name) for name in (deck, *models)}
    contents = {name: path.read_bytes() for name, path in paths.items()}
    definitions, conditions = parse_deck(contents, deck, set(models), limits)
    inputs = {"experiment": artifact(spec_path, sha256(spec_raw).hexdigest())}
    inputs.update({("netlist" if name == deck else f"model:{name}"): artifact(path, sha256(contents[name]).hexdigest())
                   for name, path in paths.items()})
    output.mkdir()
    work = output / "source-copy"
    work.mkdir()
    for name, data in contents.items():
        (work / name).write_bytes(data)
    log = output / "native.log"
    command = [executable, "-n", "-b", "-o", str(log), str(work / deck)]
    native = {
        "command": command, "engine_version": None, "returncode": None, "solver_status": "not_evaluated",
        "measurements": {}, "definitions": definitions, "conditions": conditions, "limits": limits,
    }
    executed = []
    verification = "not_evaluated"
    execution = "failed"
    options = {
        "cwd": work, "capture_output": True, "check": False,
        "encoding": "utf-8", "errors": "replace", "stdin": subprocess.DEVNULL,
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
    }
    try:
        probe = subprocess.run([executable, "--version"], timeout=min(timeout, 10), **options)
        version = re.search(r"(?i)ngspice-([0-9]+(?:\.[0-9]+)*)", probe.stdout + probe.stderr)
        if not version or probe.returncode != 0:
            native["error"] = "无法确认 ngspice 引擎版本"
        else:
            native["engine_version"] = version[1]
            process = subprocess.run(command, timeout=timeout, **options)
            native["returncode"] = process.returncode
            (output / "process.log").write_text(process.stdout + process.stderr, encoding="utf-8")
            if not log.is_file():
                native["error"] = "求解器没有写回原生日志"
                verification = "missing"
            else:
                raw = log.read_text(encoding="utf-8", errors="replace")
                diagnostics = "\n".join(line for line in raw.splitlines() if not MEASUREMENT_ERROR.match(line))
                if process.returncode != 0 or SOLVER_FAILURE.search(diagnostics):
                    native["solver_status"] = "failed"
                    native["error"] = "原生批处理报错或求解结束状态异常"
                else:
                    native["solver_status"] = "completed"
                    execution = "completed"
                    executed.append("ngspice_batch")
                    native["measurements"] = read_measures(raw, limits)
                    statuses = {item["status"] for item in native["measurements"].values()}
                    verification = next((status for status in ("invalid", "missing", "fail") if status in statuses), "pass")
    except subprocess.TimeoutExpired:
        execution = "timed_out"
        native["error"] = "ngspice 批处理或版本探测超时"
    except OSError as error:
        native["error"] = str(error)
    omitted = [skipped("hardware_qualification", "覆盖本次网表、模型和量测工况")]
    if execution != "completed":
        omitted.append(skipped("ngspice_batch", native["error"]))
    for name in limits:
        measure_status = native["measurements"].get(name, {}).get("status")
        if measure_status in {"pass", "fail"}:
            executed.append(f"measure:{name}")
        else:
            omitted.append(skipped(f"measure:{name}", "量测缺失、重复或求解未完成"))
    drift = []
    for role, item in inputs.items():
        try:
            current = artifact(local_file(item["path"]))["sha256"]
        except (OSError, ValueError):
            current = None
        if current != item["sha256"]:
            drift.append(role)
    if drift:
        native["source_changed_or_unreadable"] = drift
        verification = "invalid"
    return envelope(
        backend="ngspice", stage="simulation", execution=execution, verification=verification,
        native=native, inputs=inputs, mutation="outcome_unknown" if drift else "unchanged",
        outputs={path.stem: artifact(path) for path in (log, output / "process.log") if path.is_file()},
        executed=executed, skipped_checks=omitted,
        coverage={"measurements_requested": sorted(limits), "waveform_exported": False},
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("experiment")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ngspice-cli")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    try:
        if args.timeout < 1:
            raise ValueError("timeout 须为正整数")
        executable = (str(local_file(args.ngspice_cli)) if args.ngspice_cli else
                      shutil.which("ngspice_con") or shutil.which("ngspice"))
        if not executable:
            raise ValueError("未找到 ngspice，本机可执行文件可通过 --ngspice-cli 指定")
        value = run(local_file(args.experiment), local_file(args.output_dir, input_file=False), executable, args.timeout)
        with (Path(args.output_dir) / "evidence.json").open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except (OSError, UnicodeError, ValueError, OverflowError) as error:
        print(json.dumps({"status": "invalid_input", "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return {"pass": 0, "fail": 1}.get(value["verification_status"], 2)


if __name__ == "__main__":
    raise SystemExit(main())
