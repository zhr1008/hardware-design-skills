"""运行已经登记的硬件批处理。各专项负责解析、生成和读回。"""

import argparse
from importlib.util import find_spec
import json
from pathlib import Path
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
}
SINGLE_AD = "component-sourcing/scripts/inspect_saved.py"


def existing_file(value):
    path = Path(value).absolute()
    if path.is_symlink():
        raise ValueError(f"请指定实际输入文件：{path}")
    if not path.is_file():
        raise ValueError(f"文件不存在或不是普通文件：{path}")
    return path


def output_path(value, extension):
    target = Path(value).absolute()
    if target.suffix.lower() != extension:
        raise ValueError(f"输出路径请使用 {extension}：{target}")
    return target


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
    return parser


def list_tools(as_json):
    items = [
        {"tool": name, "level": level, "purpose": purpose, "script_installed": (SKILLS / script).is_file()}
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
    source = existing_file(args.input)
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
        if find_spec("altium_monkey") is None:
            raise ValueError("当前 Python 缺少 altium-monkey。使用已配置该依赖的 Python 环境重试")
        command += [f"--limit={args.limit}"]
        if args.designator:
            command += [f"--designator={args.designator}"]
    elif name == "bom-archive":
        for option in ("template", "column_map", "evidence"):
            value = getattr(args, option)
            if value:
                path = existing_file(value)
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
            stem = Path(args.output).absolute()
            if stem.suffix.lower() in {".html", ".xlsx"}:
                raise ValueError("--output 请填写不含 .html 或 .xlsx 的文件主名")
            command += [f"--output={stem}"]
            if not args.xlsx_only:
                outputs.append(Path(f"{stem}.html"))
            if args.xlsx or args.xlsx_only:
                outputs.append(Path(f"{stem}.xlsx"))
        elif args.xlsx or args.xlsx_only:
            raise ValueError("Excel 导出需要 --output")
        if not outputs:
            raise ValueError("需要 --output 或 --draft --write-rows")
        if args.draft:
            command += ["--draft"]
        if args.xlsx or args.xlsx_only:
            command += ["--xlsx" if args.xlsx else "--xlsx-only"]
        replace = args.replace_output
    elif name == "sourcing-lock-check":
        if args.max_age_days < 0:
            raise ValueError("--max-age-days 不能小于 0")
        command += [f"--max-age-days={args.max_age_days}"]
        if args.as_of:
            command += [f"--as-of={args.as_of}"]
    elif name == "release-check":
        command += ["--confine-to-manifest-dir"]

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
                "outputs": [str(path) for path in outputs],
            }, ensure_ascii=False))
            return 0
        return subprocess.run(
            [sys.executable, "-X", "utf8", "-B", str(script), *command], check=False,
        ).returncode
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(2, f"{args.tool} 预检失败：{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
