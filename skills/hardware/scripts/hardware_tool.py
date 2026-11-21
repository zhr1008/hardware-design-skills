"""运行已经登记的硬件批处理。各专项负责解析、生成和读回。"""

import argparse
from importlib.util import find_spec
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


SKILLS = Path(__file__).absolute().parents[2]
TOOLS = {
    "ad-saved": (
        "L0", "盘点保存的 Altium 工程、原理图或 PCB",
        "altium-schematic-review/scripts/inspect_saved_project.py",
    ),
    "bom-archive": (
        "L0/L2", "物料档案批量预检或生成 CSV",
        "bom-material-archive/scripts/bom_archive.py",
    ),
    "selection-export": (
        "L2", "把选型 JSON 转成底稿、HTML 或按需 Excel",
        "component-sourcing/scripts/render_ad_selection.py",
    ),
    "sourcing-lock-check": (
        "L0", "检查采购资格表字段、数量和证据时间",
        "qualify-pcba-sourcing/scripts/validate_sourcing_lock.py",
    ),
    "release-check": (
        "L0", "检查冻结制造包清单、版次、文件尺寸和哈希",
        "release-pcba-fabrication/scripts/validate_release_manifest.py",
    ),
    "assembly-check": (
        "L0", "核对 BOM 与 CPL 的位号、装配面、坐标和角度字段",
        "release-pcba-fabrication/scripts/check_assembly.py",
    ),
    "kicad-report-check": (
        "L0", "读取已有 KiCad ERC/DRC JSON 的问题、排除和覆盖范围",
        "pcb-layout-review/scripts/check_kicad_report.py",
    ),
    "kicad-native-check": (
        "L2", "在隔离副本运行 KiCad ERC 或 DRC 并保存报告",
        "pcb-layout-review/scripts/run_kicad_checks.py",
    ),
    "spice-run": (
        "L2", "用 ngspice 后台运行已核对的网表并验证约定量测",
        "design-and-review-circuit/scripts/run_spice.py",
    ),
    "bench-check": (
        "L0", "按明确的验收限值核对已有测量 CSV",
        "hardware-design-review/scripts/check_bench_results.py",
    ),
}
SINGLE_AD = "component-sourcing/scripts/inspect_saved.py"


def local_file(value, *, input_file=True):
    path = Path(os.path.abspath(value))
    if os.name == "nt":
        from ctypes import windll

        if path.drive.startswith("\\\\") or windll.kernel32.GetDriveTypeW(path.anchor) == 4:
            raise ValueError(f"固定离线入口需要本机文件，请使用本地副本，当前为网络盘或 UNC：{path}")
        if any(":" in name or name.rstrip(" .") != name or Path(name).is_reserved()
               for name in path.parts[1:]):
            raise ValueError(f"请使用普通 Windows 文件路径：{path}")

    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            if not input_file:
                break
            raise ValueError(f"找不到输入文件：{path}") from None
        if stat.S_ISLNK(info.st_mode) or (
            getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        ):
            raise ValueError(f"路径含符号链接或 Windows 重解析点：{current}")
        if current == path and not stat.S_ISREG(info.st_mode):
            raise ValueError(f"目标不是普通文件：{path}")
        if current != path and not stat.S_ISDIR(info.st_mode):
            raise ValueError(f"路径中间项不是目录：{current}")
    if path == path.parent:
        raise ValueError(f"目标不是普通文件：{path}")
    return path


def output_path(value, extension):
    target = Path(value)
    if target.suffix.lower() != extension:
        raise ValueError(f"输出路径请使用 {extension}：{target}")
    return local_file(target, input_file=False)


def make_parser():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--plan", action="store_true", help="只显示本次范围和级别，跳过执行")
    commands = parser.add_subparsers(dest="tool", required=True)
    listing = commands.add_parser("list", help="列出固定入口", allow_abbrev=False)
    listing.add_argument("--json", action="store_true", help="输出工具目录 JSON")
    parsers = {}
    for name, (level, purpose, _) in TOOLS.items():
        parsers[name] = commands.add_parser(name, help=f"{level} {purpose}", allow_abbrev=False)
        parsers[name].add_argument("input", help="本轮要处理的本地文件")

    ad = parsers["ad-saved"]
    ad.add_argument("--kind", choices=("schematic", "pcb"))
    ad.add_argument("--document", action="append", default=[], help="工程内的相对文档路径，可以重复")
    ad.add_argument("--designator", help="准确位号")
    ad.add_argument("--limit", type=int, default=5, help="每份文档的最多器件明细数")
    ad.add_argument("--json", action="store_true", help="工程批查输出 JSON。单文件始终输出 JSON")

    bom = parsers["bom-archive"]
    bom.add_argument("--template", help="CSV 模板，缺省使用专项内置 V1 模板")
    bom.add_argument("--column-map", help="显式列映射 JSON")
    bom.add_argument("--evidence", help="已核对的器件身份和商品页证据 JSON")
    bom.add_argument("--sheet", help="XLSX 输入的工作表")
    bom.add_argument("--header-row", type=int, help="字段名在源文件中的行号")
    bom.add_argument("--details", action="store_true", help="返回完整问题和补充记录")
    bom.add_argument("--output", help="新建物料档案 CSV。省略时只预检")

    export = parsers["selection-export"]
    export.add_argument("--output", help="输出文件主名，省略 .html 或 .xlsx")
    modes = export.add_mutually_exclusive_group()
    modes.add_argument("--xlsx", action="store_true")
    modes.add_argument("--xlsx-only", action="store_true")
    export.add_argument("--draft", action="store_true")
    export.add_argument("--write-rows", help="将候选写成待核对的 JSON 底稿")
    export.add_argument("--replace-output", action="store_true", help="覆盖用户已指定可更新的输出文件")

    lock = parsers["sourcing-lock-check"]
    lock.add_argument("--max-age-days", type=int, default=14)
    lock.add_argument("--as-of", help="ISO 时间戳")
    lock.add_argument("--formal", action="store_true", help="按正式资格、采购和报价证据校验")

    assembly = parsers["assembly-check"]
    assembly.add_argument("--cpl", required=True, help="同一版次和装配变体的坐标 CSV")
    assembly.add_argument("--exclude", action="append", default=[], help="不贴装位号，以逗号分隔，可重复")
    assembly.add_argument("--format", choices=("json", "text"))

    for name in ("kicad-report-check", "release-check", "bench-check"):
        parsers[name].add_argument("--formal", action="store_true", help="输出正式审查的版本化证据")

    kicad = parsers["kicad-report-check"]
    kicad.add_argument("--kind", choices=("erc", "drc"), help="要求报告为指定检查类型")

    for name, executable in (("kicad-native-check", "kicad-cli"), ("spice-run", "ngspice-cli")):
        runner = parsers[name]
        runner.add_argument("--output-dir", required=True, help="本次执行的新建本地目录")
        runner.add_argument(f"--{executable}", help="显式指定本机可执行文件")
        runner.add_argument("--timeout", type=int, help="本次执行的秒数上限")
    parsers["kicad-native-check"].add_argument("--companion", action="append", default=[],
                                               help="源目录内的伴随文件，可重复")
    parsers["kicad-native-check"].add_argument("--schematic", help="同版 KiCad 原理图")
    parsers["kicad-native-check"].add_argument("--expected-readback", help="已核实的保存态目标 JSON")

    bench = parsers["bench-check"]
    bench.add_argument("--measurements", required=True, help="已有的测量 CSV")
    return parser


def list_tools(as_json):
    items = [
        {
            "tool": name, "level": level, "purpose": purpose,
            "script_installed": (SKILLS / script).is_file() and (
                name != "ad-saved" or (SKILLS / SINGLE_AD).is_file()
            ),
        }
        for name, (level, purpose, script) in TOOLS.items()
    ]
    if as_json:
        print(json.dumps(items, ensure_ascii=False))
    else:
        for item in items:
            status = "" if item["script_installed"] else "（脚本缺失）"
            print(f'{item["tool"]:<22} {item["level"]:<6} {item["purpose"]}{status}')


def prepare(args):
    name = args.tool
    formal = getattr(args, "formal", False)
    paired_readback = name == "kicad-native-check" and bool(args.schematic and args.expected_readback)
    source = local_file(args.input, input_file=not (formal or paired_readback))
    entry = TOOLS[name][2]
    command = [str(source)]
    input_paths = [source]
    outputs = []
    replace = False

    if name == "ad-saved":
        if args.limit < 1:
            raise ValueError("--limit 必须大于 0")
        if source.suffix.lower() == ".prjpcb":
            command += [f"--document={document}" for document in args.document]
            if args.kind:
                command += [f"--kind={args.kind}"]
            if args.json:
                command += ["--json"]
        elif source.suffix.lower() in {".schdoc", ".pcbdoc"}:
            if args.kind or args.document:
                raise ValueError("--kind 和 --document 仅用于 .PrjPcb")
            entry = SINGLE_AD
        else:
            raise ValueError("指定 .PrjPcb、.SchDoc 或 .PcbDoc")
        if not args.plan and find_spec("altium_monkey") is None:
            raise ValueError("当前 Python 缺少 altium-monkey。使用已配置该依赖的 Python 环境重试")
        command += [f"--limit={args.limit}"]
        if args.designator:
            command += [f"--designator={args.designator}"]
    elif name == "bom-archive":
        for option in ("template", "column_map", "evidence"):
            value = getattr(args, option)
            if value:
                path = local_file(value)
                input_paths.append(path)
                command += [f"--{option.replace('_', '-')}={path}"]
        if args.sheet:
            command += [f"--sheet={args.sheet}"]
        if args.header_row is not None:
            if args.header_row < 1:
                raise ValueError("--header-row 必须大于 0")
            command += [f"--header-row={args.header_row}"]
        if args.details:
            command += ["--details"]
        if args.output:
            outputs.append(output_path(args.output, ".csv"))
            command += [f"--output={outputs[0]}"]
    elif name == "selection-export":
        if args.write_rows:
            outputs.append(output_path(args.write_rows, ".json"))
            command += [f"--write-rows={outputs[-1]}"]
            if not args.draft:
                raise ValueError("--write-rows 需配合 --draft")
        if args.output:
            stem = Path(os.path.abspath(args.output))
            if stem.suffix.lower() in {".html", ".xlsx"}:
                raise ValueError("--output 请填写不含 .html 或 .xlsx 的文件主名")
            command += [f"--output={stem}"]
            if not args.xlsx_only:
                outputs.append(output_path(f"{stem}.html", ".html"))
            if args.xlsx or args.xlsx_only:
                outputs.append(output_path(f"{stem}.xlsx", ".xlsx"))
        elif args.xlsx or args.xlsx_only:
            raise ValueError("Excel 导出需要 --output")
        if not outputs:
            raise ValueError("需要 --output 或 --draft --write-rows")
        if args.draft:
            command += ["--draft"]
        if args.xlsx or args.xlsx_only:
            command += ["--xlsx" if args.xlsx else "--xlsx-only"]
        replace = args.replace_output
        if not replace:
            command += ["--no-clobber"]
    elif name == "sourcing-lock-check":
        if args.max_age_days < 0:
            raise ValueError("--max-age-days 不能小于 0")
        command += [f"--max-age-days={args.max_age_days}"]
        if args.as_of:
            command += [f"--as-of={args.as_of}"]
    elif name == "release-check":
        command += ["--confine-to-manifest-dir"]
    elif name == "assembly-check":
        cpl = local_file(args.cpl)
        if source.suffix.casefold() != ".csv" or cpl.suffix.casefold() != ".csv":
            raise ValueError("BOM 和 CPL 路径都需要使用 .csv")
        if source.samefile(cpl):
            raise ValueError("BOM 和 CPL 需要分别指定两份 CSV")
        input_paths.append(cpl)
        command += [f"--cpl={cpl}", *(f"--exclude={value}" for value in args.exclude)]
        if args.format:
            command += [f"--format={args.format}"]
    elif name == "kicad-report-check" and args.kind:
        command += [f"--kind={args.kind}"]
    elif name in {"kicad-native-check", "spice-run"}:
        suffixes = {".kicad_pcb", ".kicad_sch"} if name == "kicad-native-check" else {".json"}
        if source.suffix.casefold() not in suffixes:
            raise ValueError(f"输入格式应为 {', '.join(sorted(suffixes))}")
        outputs.append(local_file(args.output_dir, input_file=False))
        command += [f"--output-dir={outputs[0]}"]
        executable_key = "kicad-cli" if name == "kicad-native-check" else "ngspice-cli"
        executable = getattr(args, executable_key.replace("-", "_"))
        if executable:
            executable_path = local_file(executable)
            input_paths.append(executable_path)
            command += [f"--{executable_key}={executable_path}"]
        if args.timeout is not None:
            if args.timeout < 1:
                raise ValueError("--timeout 必须为正整数")
            command += [f"--timeout={args.timeout}"]
        for value in getattr(args, "companion", []):
            companion = local_file(source.parent / value)
            if not companion.is_relative_to(source.parent):
                raise ValueError(f"伴随文件必须位于输入文件所在目录：{companion}")
            input_paths.append(companion)
            command += [f"--companion={companion}"]
        if name == "kicad-native-check":
            if bool(args.schematic) != bool(args.expected_readback):
                raise ValueError("--schematic 与 --expected-readback 必须同时指定")
            for flag, value in (("schematic", args.schematic), ("expected-readback", args.expected_readback)):
                if value:
                    path = local_file(value, input_file=False)
                    input_paths.append(path)
                    command.append(f"--{flag}={path}")
    elif name == "bench-check":
        measurements = local_file(args.measurements, input_file=not formal)
        if source.suffix.casefold() != ".json" or measurements.suffix.casefold() != ".csv":
            raise ValueError("限值文件需要使用 .json，测量文件需要使用 .csv")
        input_paths.append(measurements)
        command = [f"--limits={source}", f"--measurements={measurements}"]

    if formal:
        command.append("--formal")

    # 比较解析后的路径以识别符号链接。直接拒绝输出链接，保留已有文件。
    resolved_inputs = {path.resolve() for path in input_paths} if outputs else set()
    seen_outputs = set()
    for target in outputs:
        resolved = target.resolve()
        if target.is_symlink() or resolved in resolved_inputs or resolved in seen_outputs:
            raise ValueError(f"输出与输入或其他产物冲突：{target}")
        if target.exists() and (not replace or not target.is_file()):
            raise ValueError(f"输出已存在：{target}")
        seen_outputs.add(resolved)

    script = SKILLS / entry
    if not script.is_file():
        raise ValueError(f"专项脚本缺失：{script}")
    return script, command, input_paths, outputs


def main():
    parser = make_parser()
    args = parser.parse_args()
    if args.tool == "list":
        list_tools(args.json)
        return 0
    try:
        script, command, inputs, outputs = prepare(args)
        if args.plan:
            print(json.dumps({
                "status": "planned", "tool": args.tool, "level": "L2" if outputs else "L0",
                "script": str(script), "inputs": [str(path) for path in inputs],
                "outputs": [str(path) for path in outputs], "parameters": command,
            }, ensure_ascii=False))
            return 0
        invocation = [sys.executable, "-X", "utf8", "-B", str(script), *command]
        if args.tool == "sourcing-lock-check" and args.formal:
            from evidence_adapter import saved_sourcing, strict_json

            outcome = subprocess.run(invocation, check=False, capture_output=True, encoding="utf-8")
            if not outcome.stdout.strip():
                raise ValueError(outcome.stderr.strip() or "未取得正式资格校核结果")
            report = strict_json(outcome.stdout)
            evidence = saved_sourcing(report, inputs[0])
            print(json.dumps(evidence, ensure_ascii=False))
            return outcome.returncode
        return subprocess.run(invocation, check=False).returncode
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(2, f"{args.tool} 预检失败：{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
