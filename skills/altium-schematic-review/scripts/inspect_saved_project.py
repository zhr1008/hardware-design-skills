"""Read the saved SchDoc and PcbDoc members listed by an Altium project."""

import argparse
from collections import Counter
from contextlib import redirect_stdout
from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import sys


KINDS = {".schdoc": "schematic", ".pcbdoc": "pcb"}
SCOPE = "磁盘保存版本。每个成员单独读取，未验证活动文档、未保存状态、原生编译或 ERC/DRC。"


class OutsideScope(ValueError):
    """An input is not a local regular file within the project directory."""


def load_saved_reader():
    skills = Path(__file__).absolute().parents[2]
    script = skills / "component-sourcing" / "scripts" / "inspect_saved.py"
    if not script.is_file():
        raise ImportError("缺少同级 component-sourcing/scripts/inspect_saved.py")
    sys.dont_write_bytecode = True
    spec = spec_from_file_location("_component_sourcing_inspect_saved", script)
    reader = module_from_spec(spec)
    spec.loader.exec_module(reader)
    return reader.inspect


def relative_parts(value):
    path = PureWindowsPath(value)
    if path.anchor or not path.parts or any(
        part.rstrip(" .") != part or PureWindowsPath(part).is_reserved()
        or any(ord(char) < 32 or char in '<>:"|?*' for char in part)
        for part in path.parts
    ):
        raise OutsideScope("工程成员需要使用工程目录以内的常规相对路径")
    return path.parts


def regular_file(root, parts):
    current = root
    for index, part in enumerate(parts):
        current = current / part
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or (
            getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        ):
            raise OutsideScope("路径含符号链接或 Windows 重解析点")
        if index < len(parts) - 1 and not stat.S_ISDIR(info.st_mode):
            raise OutsideScope("路径中间项不是目录")
    if not stat.S_ISREG(info.st_mode):
        raise OutsideScope("目标不是常规文件")
    return current


def local_project(path):
    path = Path(os.path.abspath(path))
    if path.suffix.casefold() != ".prjpcb":
        raise OutsideScope("需要指定一个已保存的 .PrjPcb 文件")
    if os.name == "nt":
        from ctypes import windll

        if path.drive.startswith("\\\\") or windll.kernel32.GetDriveTypeW(path.anchor) == 4:
            raise OutsideScope("请先将工程副本置于本机磁盘，当前路径是网络盘或 UNC 地址")
    return regular_file(Path(path.anchor), relative_parts(str(Path(*path.parts[1:]))))


def read_member(parts, root, inspect, designator, limit):
    try:
        target = regular_file(root, parts)
        return {"status": "read", "data": inspect(target, designator=designator, limit=limit)}
    except FileNotFoundError:
        return {"status": "missing", "detail": "工程目录内找不到已保存文件"}
    except OutsideScope as exc:
        return {"status": "blocked", "detail": str(exc)}
    except Exception as exc:
        return {"status": "parse_error", "detail": f"{type(exc).__name__}: {str(exc)[:250]}"}


def document_key(parts):
    return tuple(part.casefold() for part in parts)


def read_manifest(project):
    from altium_monkey.altium_prjpcb import AltiumPrjPcb

    config = AltiumPrjPcb(project).config
    # The current .documents accessor stops ordinary DocumentN entries at the
    # first numbering gap. The parsed sections retain all declared members.
    return [
        config.get(section, "DocumentPath", fallback="")
        for section in config.sections()
        if re.fullmatch(r"(?:Document|DeviceSheet)\d+", section, re.IGNORECASE)
    ]


def inspect_project(project, inspect, *, documents, kind, designator, limit):
    manifest = read_manifest(project)
    requested = {document_key(relative_parts(path)): path for path in documents}
    seen = set()
    records = []
    ignored = duplicates = 0
    for path in manifest:
        if not path and not requested:
            records.append({"document": "", "kind": None, "status": "invalid_reference",
                            "detail": "工程成员未填写 DocumentPath"})
            continue
        document_kind = KINDS.get(PureWindowsPath(path).suffix.casefold())
        if document_kind is None or (kind and kind != document_kind):
            ignored += 1
            continue
        try:
            parts = relative_parts(path)
            key = document_key(parts)
        except OutsideScope as exc:
            if not requested:
                records.append({"document": path, "kind": document_kind, "status": "blocked",
                                "detail": str(exc)})
            continue
        if requested and key not in requested:
            ignored += 1
            continue
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        record = read_member(parts, project.parent, inspect, designator, limit)
        records.append({"document": path, "kind": document_kind, **record})

    for key, path in requested.items():
        if key not in seen:
            records.append({"document": path, "kind": None, "status": "not_listed",
                            "detail": "未在工程成员清单中找到指定路径"})

    counts = Counter(record["status"] for record in records)
    complete = bool(records) and counts["read"] == len(records)
    return {
        "schema_version": 1,
        "source": "saved_project",
        "project": str(project),
        "status": "complete" if complete else "incomplete",
        "scope": SCOPE,
        "declared_count": len(manifest),
        "ignored_count": ignored,
        "duplicate_count": duplicates,
        "counts": dict(counts),
        "designator": designator,
        "documents": records,
    }


def show_summary(result):
    counts = result["counts"]
    print(f'{result["project"]} · {result["status"]} · 读取 {counts.get("read", 0)} / '
          f'{len(result["documents"])} · 清单共 {result["declared_count"]} 项')
    for record in result["documents"]:
        name = json.dumps(record["document"], ensure_ascii=False)
        if record["status"] != "read":
            print(f'- {name} {record["status"]} · {json.dumps(record["detail"], ensure_ascii=False)[1:-1]}')
            continue
        data = record["data"]
        detail = (
            f'{data["wire_count"]} 段线 / {data["port_count"]} 端口'
            if record["kind"] == "schematic"
            else f'{data["net_count"]} 网 / {data["track_count"]} 走线 / {data["pad_count"]} 焊盘'
        )
        match = f' · 位号命中 {data["matched_count"]}' if result["designator"] else ""
        print(f'- {name} · {data["component_count"]} 器件 / {detail}{match}')
    print(result["scope"])


def main():
    parser = argparse.ArgumentParser(description="按 .PrjPcb 清单批量读取磁盘中的 .SchDoc、.PcbDoc")
    parser.add_argument("project", type=Path)
    parser.add_argument("--kind", choices=tuple(KINDS.values()))
    parser.add_argument("--document", action="append", default=[], help="清单中的相对路径，可重复")
    parser.add_argument("--designator", help="只在组件明细中返回与位号精确匹配的项目")
    parser.add_argument("--limit", type=int, default=5, help="每个成员最多返回的组件明细数，默认 5")
    parser.add_argument("--json", action="store_true", help="输出紧凑 JSON")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit 必须大于 0")
    try:
        for path in args.document:
            relative_parts(path)
            selected_kind = KINDS.get(PureWindowsPath(path).suffix.casefold())
            if selected_kind is None or (args.kind and selected_kind != args.kind):
                raise ValueError("--document 需匹配 .SchDoc/.PcbDoc 与 --kind")
        project = local_project(args.project)
        with redirect_stdout(sys.stderr):
            result = inspect_project(
                project, load_saved_reader(), documents=args.document, kind=args.kind,
                designator=args.designator, limit=args.limit,
            )
    except ImportError as exc:
        parser.error(f"离线依赖不可用，请用装有 altium-monkey 的 Python 环境。{exc}")
    except Exception as exc:
        parser.error(f"项目无法读取 ({type(exc).__name__})。{exc}")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    else:
        show_summary(result)
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
