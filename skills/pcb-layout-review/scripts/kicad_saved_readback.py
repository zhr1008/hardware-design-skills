"""Read saved KiCad connectivity against a declared, full expected graph."""

from dataclasses import asdict
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).absolute().parents[2] / "schematic-humanizer/scripts"))
from compare_connectivity import parse_canonical_json, parse_kicad_xml
from evidence_adapter import strict_json


SCHEMA = "kicad-saved-readback-v1"
TOKEN = re.compile(r'\s+|#[^\r\n]*|"(?:[^"\\]|\\.)*"|[()]|[^()\s"]+')


def text(value):
    return isinstance(value, str) and bool(value.strip())


def schematic_graph(connectivity, paths, no_connect):
    return {
        "components": {(ref,): {**asdict(part), "sheet_path": paths[ref]}
                       for ref, part in connectivity.components.items()},
        "nets": {(net,): {} for net in connectivity.nets},
        "pins": {(pin.ref, pin.pin): {"net": net, "no_connect": no_connect[(pin.ref, pin.pin)]}
                 for net, pins in connectivity.nets.items() for pin in pins},
    }


def expected_contract(raw):
    data = strict_json(raw)
    if (not isinstance(data, dict)
            or set(data) != {"schema", "revision", "variant", "sources", "schematic", "pcb"}
            or data["schema"] != SCHEMA or not all(text(data[field]) for field in ("revision", "variant"))):
        raise ValueError(f"需要 {SCHEMA}、revision、variant、sources、schematic 和 pcb")
    sources = data["sources"]
    if not isinstance(sources, dict) or not sources:
        raise ValueError("sources 需要非空的相对路径与 SHA-256 映射")
    for name, digest in sources.items():
        path = PurePosixPath(name)
        if (not text(name) or not path.parts or path.is_absolute() or path.as_posix() != name or ".." in path.parts
                or PureWindowsPath(name).drive or "\\" in name or ":" in name or not text(digest)
                or not re.fullmatch(r"[a-f0-9]{64}", digest)):
            raise ValueError(f"无效的保存态工件路径或 SHA-256：{name!r}")

    schematic = data["schematic"]
    connectivity = parse_canonical_json(schematic, "expected-readback.schematic")
    if set(schematic) != {"schema", "components", "nets"}:
        raise ValueError("schematic 只接受 schema、components 和 nets")
    paths = {}
    for part in schematic["components"]:
        if (set(part) != {"ref", "value", "footprint", "device", "sheet_path"}
                or any(not isinstance(part[field], str) for field in ("value", "footprint", "device", "sheet_path"))
                or not part["sheet_path"].startswith("/")):
            raise ValueError("schematic.components 项需要 ref、value、footprint、device 和绝对 sheet_path")
        paths[part["ref"].strip()] = part["sheet_path"]
    no_connect = {}
    for net in schematic["nets"]:
        if set(net) != {"name", "pins"}:
            raise ValueError("schematic.nets 项需要 name 和 pins")
        for pin in net["pins"]:
            if set(pin) != {"ref", "pin", "no_connect"} or not isinstance(pin["no_connect"], bool):
                raise ValueError("schematic.nets[].pins 项需要 ref、pin 和布尔 no_connect")
            no_connect[pin["ref"].strip(), pin["pin"].strip()] = pin["no_connect"]

    pcb = data["pcb"]
    if (not isinstance(pcb, dict) or set(pcb) != {"footprints"}
            or not isinstance(pcb["footprints"], list) or not pcb["footprints"]):
        raise ValueError("pcb.footprints 需要非空的封装数组")
    footprints = {}
    for row in pcb["footprints"]:
        if (not isinstance(row, dict) or set(row) != {"ref", "footprint", "pads"}
                or not text(row["ref"]) or not text(row["footprint"]) or row["ref"] in footprints
                or not isinstance(row["pads"], dict) or any(
                    not text(pin) or (net is not None and not text(net)) for pin, net in row["pads"].items()
                )):
            raise ValueError("pcb.footprints 项需要唯一 ref、footprint 和编号焊盘到网名或 null 的映射")
        footprints[row["ref"]] = row
    return data, schematic_graph(connectivity, paths, no_connect), board_graph(footprints)


def read_schematic(path, source_copy, version):
    try:
        xml = ET.fromstring(path.read_bytes())
    except ET.ParseError as error:
        raise ValueError(f"KiCad XML 网表无效：{error}") from error
    source = xml.findtext("./design/source", "")
    tool = xml.findtext("./design/tool", "")
    if xml.tag != "export" or Path(source) != source_copy or tool != f"Eeschema {version}":
        raise ValueError("XML 网表的输入路径或 KiCad 版本与本次调用不同")
    connectivity = parse_kicad_xml(xml, str(path))
    paths = {}
    for row in xml.findall("./components/comp"):
        sheet_path = row.find("./sheetpath")
        label = None if sheet_path is None else sheet_path.get("names")
        if not label or not label.startswith("/"):
            raise ValueError(f"没有可读的图纸层级：{row.get('ref')}")
        paths[row.get("ref").strip()] = label
    no_connect = {}
    for node in xml.findall("./nets/net/node"):
        pin_type = node.get("pintype")
        if not pin_type:
            raise ValueError(f"网表未报告引脚类型：{node.get('ref')}.{node.get('pin')}")
        no_connect[node.get("ref").strip(), node.get("pin").strip()] = "no_connect" in pin_type.split("+")
    return schematic_graph(connectivity, paths, no_connect)


def sexpr(raw):
    stack = [[]]
    offset = 0
    for match in TOKEN.finditer(raw):
        token = match[0]
        if match.start() != offset:
            raise ValueError("PCB 文本含无法读取的 s-expression")
        offset = match.end()
        if token == "(":
            form = []
            stack[-1].append(form)
            stack.append(form)
        elif token == ")":
            if len(stack) == 1:
                raise ValueError("PCB s-expression 的圆括号未成对")
            stack.pop()
        elif not (token.isspace() or token.startswith("#")):
            stack[-1].append(json.loads(token, strict=False) if token.startswith('"') else token)
    if offset != len(raw) or len(stack) != 1 or len(stack[0]) != 1:
        raise ValueError("PCB 文件需要完整的 s-expression")
    board = stack[0][0]
    if not isinstance(board, list) or not board or board[0] != "kicad_pcb":
        raise ValueError("PCB 文件缺少 kicad_pcb 根节点")
    return board


def forms(row, label):
    return [child for child in row if isinstance(child, list) and child and child[0] == label]


def read_board(path):
    board = sexpr(path.read_text(encoding="utf-8-sig"))
    nets = {}
    for row in forms(board, "net"):
        if (len(row) != 3 or not all(isinstance(field, str) for field in row[1:])
                or row[1] in nets or (row[1] == "0") != (row[2] == "")):
            raise ValueError("PCB 网号表格式无效")
        nets[row[1]] = row[2]
    nets.setdefault("0", "")
    footprints = {}
    for footprint in forms(board, "footprint"):
        refs = [row[2] for row in forms(footprint, "property") if row[1:2] == ["Reference"] and len(row) > 2]
        if not refs:
            refs = [row[2] for row in forms(footprint, "fp_text") if row[1:2] == ["reference"] and len(row) > 2]
        if (len(footprint) < 2 or not text(footprint[1]) or len(refs) != 1
                or not text(refs[0]) or refs[0] in footprints):
            raise ValueError("PCB 封装需要唯一可识别的位号和封装名")
        ref = refs[0]
        pads = {}
        for pad in forms(footprint, "pad"):
            if len(pad) < 2 or not isinstance(pad[1], str):
                raise ValueError(f"{ref} 含无效的焊盘编号")
            number = pad[1]
            if not number:
                continue
            assignment = forms(pad, "net")
            net = None
            if assignment:
                _, *values = assignment[0]
                if len(assignment) != 1 or not all(isinstance(value, str) for value in values):
                    raise ValueError(f"{ref}.{number} 包含无效的 PCB 网分配")
                if len(values) == 2 and nets.get(values[0]) == values[1]:
                    net = values[1] or None
                elif len(values) == 1:
                    net = values[0] or None
                else:
                    raise ValueError(f"{ref}.{number} 的网分配与 PCB 网号表不一致")
            if number in pads and pads[number] != net:
                raise ValueError(f"{ref}.{number} 的同号焊盘分配到了不同的网")
            pads[number] = net
        footprints[ref] = {"ref": ref, "footprint": footprint[1], "pads": pads}
    return board_graph(footprints)


def board_graph(footprints):
    return {
        "footprints": {(ref,): {"footprint": row["footprint"]} for ref, row in footprints.items()},
        "pads": {(ref, pin): {"net": net} for ref, row in footprints.items() for pin, net in row["pads"].items()},
    }


def compare_graphs(expected, actual):
    differences = {}
    counts = {}
    status = "pass"
    for group, expected_rows in expected.items():
        actual_rows = actual[group]
        missing = sorted(expected_rows.keys() - actual_rows.keys())
        extra = sorted(actual_rows.keys() - expected_rows.keys())
        changed = sorted(key for key in expected_rows.keys() & actual_rows.keys()
                         if expected_rows[key] != actual_rows[key])
        counts[group] = {"expected": len(expected_rows), "actual": len(actual_rows)}
        if missing or extra or changed:
            differences[group] = {
                "missing_from_saved": [{"key": list(key), "expected": expected_rows[key]} for key in missing],
                "not_declared": [{"key": list(key), "actual": actual_rows[key]} for key in extra],
                "changed": [{"key": list(key), "expected": expected_rows[key], "actual": actual_rows[key]}
                            for key in changed],
            }
        if missing or changed:
            status = "fail"
        elif extra and status == "pass":
            status = "coverage_incomplete"
    return {"status": status, "counts": counts, "differences": differences}
