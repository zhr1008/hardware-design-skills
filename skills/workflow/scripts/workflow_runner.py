"""Preview a firmware workflow from declared inputs. This tool only reads paths."""

import argparse
import json
from pathlib import Path


WORKFLOWS = {
    "build": ("build",),
    "build-flash-monitor": ("build", "flash", "monitor"),
    "build-flash-debug": ("build", "flash", "debug"),
}
PROJECT_FILES = {
    "cmake": ("CMakeLists.txt",),
    "idf": ("CMakeLists.txt",),
    "makefile": ("GNUmakefile", "makefile", "Makefile"),
    "platformio": ("platformio.ini",),
}
PROJECT_SUFFIXES = {"keil": {".uvprojx", ".uvproj"}, "iar": {".ewp"}}


def project_matches(path, system):
    if system in PROJECT_SUFFIXES:
        return path.is_file() and path.suffix.casefold() in PROJECT_SUFFIXES[system]
    filenames = PROJECT_FILES[system]
    if path.is_dir():
        return any((path / name).is_file() for name in filenames)
    return path.is_file() and path.name in filenames


def positive_integer(value):
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("波特率必须为正整数")
    return parsed


def plan(args):
    build_inputs = []
    if not project_matches(args.project, args.build_system):
        build_inputs.append("确认存在适合所选构建系统的项目文件")
    if args.build_system in {"keil", "iar", "platformio"} and not args.target:
        build_inputs.append("指定项目目标、配置或环境名称")

    physical_target = []
    if not args.flash_target:
        physical_target.append("指定可识别的目标板和芯片")
    if not args.flash_interface:
        physical_target.append("指定探针或烧录接口")
    flash_inputs = list(physical_target)
    if args.artifact and not args.artifact.is_file():
        flash_inputs.append("确认指定镜像文件存在")

    monitor_inputs = []
    if not args.port:
        monitor_inputs.append("指定板卡串口")
    if not args.baud:
        monitor_inputs.append("指定波特率")
    requirements = {
        "build": (build_inputs, "核对目标、构建日志和实际生成工件"),
        "flash": (flash_inputs, "绑定实际镜像和地址，确认擦写、校验和复位许可"),
        "monitor": (monitor_inputs, "核对实际串口及 DTR/RTS 影响，约定采集结束条件"),
        "debug": (physical_target, "核对匹配符号、目标暂停影响和会话结束状态"),
    }
    steps = [
        {"step": step, "missing_inputs": requirements[step][0], "checkpoint": requirements[step][1]}
        for step in WORKFLOWS[args.run]
    ]
    incomplete = any(step["missing_inputs"] for step in steps)
    return {
        "status": "incomplete" if incomplete else "planned",
        "executed": False,
        "project": str(args.project),
        "build_system": args.build_system,
        "target": args.target,
        "artifact": str(args.artifact) if args.artifact else None,
        "flash_interface": args.flash_interface,
        "flash_target": args.flash_target,
        "port": args.port,
        "baud": args.baud,
        "steps": steps,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--build-system", required=True, choices=sorted(PROJECT_FILES.keys() | PROJECT_SUFFIXES.keys()))
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--target", help="构建目标、配置或环境")
    parser.add_argument("--run", choices=WORKFLOWS, default="build", help="要预览的流程")
    parser.add_argument("--artifact", type=Path, help="指定的现有镜像。省略时在构建后核对产物")
    parser.add_argument("--flash-interface", help="已指定的烧录或调试接口")
    parser.add_argument("--flash-target", help="目标板与芯片标识")
    parser.add_argument("--port", help="已指定的串口")
    parser.add_argument("--baud", type=positive_integer)
    parser.add_argument("--dry-run", action="store_true", help="显式预览。所有调用均为离线预览")
    args = parser.parse_args()
    result = plan(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["status"] == "incomplete" else 0


if __name__ == "__main__":
    raise SystemExit(main())
