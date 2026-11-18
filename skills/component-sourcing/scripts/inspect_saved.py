"""Inspect saved Altium projects, schematics, PCBs and integrated libraries offline."""

import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


def inspect_intlib(path: Path, *, component: str | None, limit: int) -> dict:
    from altium_monkey import AltiumIntLib, AltiumSchLib

    with AltiumIntLib.from_file(path) as library, TemporaryDirectory(prefix="component-intlib-") as directory:
        if library.component_parse_error:
            raise ValueError("IntLib 器件交叉引用无法读取，请提供配套 SchLib/PcbLib 或清单")
        members = library.components
        if component is None:
            selected = members
        else:
            selected = [item for item in members if item.name.casefold() == component.casefold()]
        rows = []
        sources = {}
        for item in selected[:limit]:
            # Read only the distinct SchLib streams used by the selected output rows.
            if item.virtual_path not in sources:
                source = Path(directory) / f"{len(sources)}.SchLib"
                source.write_bytes(library.read_stream(item.virtual_path))
                sources[item.virtual_path] = AltiumSchLib(source)
            symbol = sources[item.virtual_path].get_symbol(item.name)
            row = {"name": item.name, "description": item.description,
                   "footprints": [model.name for model in item.models if model.model_type.upper() == "PCBLIB"]}
            if symbol is None:
                row["warning"] = "已列入交叉引用，内嵌 SchLib 中未解析到同名符号"
            else:
                row["parameters"] = [{"name": param.name, "value": param.text} for param in symbol.parameters]
                row["pin_count"] = len(symbol.pins)
            rows.append(row)
        return {"source": "saved_file", "file": path.name, "component_count": len(members),
                "matched_count": len(selected), "components": rows, "truncated": len(selected) > limit}


def inspect(path: Path, *, designator: str | None, limit: int, component: str | None = None) -> dict:
    result = {"source": "saved_file", "file": path.name}
    kind = path.suffix.lower()
    if kind == ".intlib":
        return inspect_intlib(path, component=component, limit=limit)
    if kind == ".prjpcb":
        from altium_monkey.altium_prjpcb import AltiumPrjPcb

        documents = AltiumPrjPcb(path).documents
        return {**result, "document_count": len(documents),
                "documents": [doc["path"] for doc in documents[:limit]],
                "truncated": len(documents) > limit}

    if kind == ".schdoc":
        from altium_monkey import AltiumSchDoc

        sheet = AltiumSchDoc(path)
        components = sheet.get_components()
        result.update(wire_count=len(sheet.wires), port_count=len(sheet.ports))
    else:
        from altium_monkey import AltiumPcbDoc

        board = AltiumPcbDoc.from_file(path)
        components = board.components
        result.update(net_count=len(board.nets), track_count=len(board.tracks), pad_count=len(board.pads))

    selected = components if designator is None else [
        comp for comp in components if comp.designator.casefold() == designator.casefold()
    ]
    rows = []
    for comp in selected[:limit]:
        row = {"designator": comp.designator, "footprint": comp.footprint}
        if kind == ".schdoc":
            row.update(comment=comp.comment, pin_count=len(comp.pins))
        else:
            row.update(layer=comp.layer, x=comp.x, y=comp.y, rotation=comp.rotation)
        rows.append(row)
    return {**result, "component_count": len(components), "matched_count": len(selected),
            "components": rows, "truncated": len(selected) > limit}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--designator", help="Exact component designator in a SchDoc or PcbDoc")
    parser.add_argument("--component", help="IntLib 中的准确库件名，忽略大小写")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()
    kind = args.file.suffix.lower()
    if not args.file.is_file() or kind not in {".prjpcb", ".schdoc", ".pcbdoc", ".intlib"}:
        parser.error("需要指定一个已保存的 .PrjPcb、.SchDoc、.PcbDoc 或 .IntLib 文件")
    if args.limit < 1:
        parser.error("--limit 必须大于 0")
    if args.component is not None and kind != ".intlib":
        parser.error("--component 用于指定 .IntLib 的库件名")
    if args.designator is not None and kind not in {".schdoc", ".pcbdoc"}:
        parser.error("按位号检查时请指定具体的 .SchDoc 或 .PcbDoc")
    try:
        with redirect_stdout(sys.stderr):
            result = inspect(args.file, designator=args.designator, limit=args.limit, component=args.component)
    except ImportError as exc:
        print(f"解析依赖不可用。请用装有 altium-monkey 的 Python 3.12 环境运行。{exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"{args.file.name} 解析失败 ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
