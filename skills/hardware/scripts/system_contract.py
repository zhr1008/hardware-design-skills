"""Validate a read-only, versioned hardware system contract and check bindings."""

from collections import defaultdict, deque
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import hashlib
import json
import math
import operator
from pathlib import Path, PureWindowsPath
import re

from evidence_adapter import strict_json
from hardware_tool import local_file


SCHEMA = "hardware-system-contract-v1"
NODE_GROUPS = ("blocks", "ports", "conditions", "criteria", "decisions", "anchors")
OPS = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge}
ANCHOR_SUFFIXES = {
    "schematic": {".schdoc", ".kicad_sch", ".sch", ".net", ".json"},
    "pcb": {".pcbdoc", ".kicad_pcb", ".brd", ".json"},
    "firmware": {".c", ".h", ".cpp", ".hpp", ".s", ".asm", ".py", ".rs",
                 ".elf", ".hex", ".bin", ".json", ".csv"},
    "mechanical": {".step", ".stp", ".stl", ".iges", ".igs", ".fcstd", ".sldprt",
                   ".sldasm", ".dxf", ".json", ".csv", ".pdf"},
    "simulation": {".cir", ".sp", ".spice", ".net", ".asc", ".raw", ".csv", ".json"},
    "evidence": {".json", ".csv", ".txt", ".log", ".pdf"},
    "module-pack": {".json"},
    "bom": {".csv", ".tsv", ".xlsx"},
    "cpl": {".csv", ".tsv", ".xlsx"},
    "manifest": {".json"},
    "sourcing-lock": {".csv"},
    "test-fixture": {".csv", ".json", ".txt", ".py", ".c", ".h", ".yaml", ".yml"},
}
DOWNSTREAM_SCHEMAS = (SCHEMA, "hardware-engineering-case-v1", "pcba-program-state-v1")
DOWNSTREAM_NAMES = {"case.json", "system-contract.json", "program-state.json"}
ID = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
LINE = re.compile(r"#L([1-9][0-9]{0,8})\Z")
INVALID_PATH_CHAR = re.compile(r'[<>:"|?*\x5c\x00-\x1f]')


class ContractConflict(ValueError):
    """Declared engineering facts, identity or integrity disagree."""


class ContractMissing(ValueError):
    """A required reference or the material for checking it is missing."""


def _object(value, label, required=(), optional=None):
    if value is None:
        raise ContractMissing(f"缺少 {label}")
    if not isinstance(value, dict):
        raise ContractConflict(f"{label} 必须是对象")
    missing = set(required) - value.keys()
    if missing:
        raise ContractMissing(f"{label} 缺字段：{', '.join(sorted(missing))}")
    if optional is not None:
        extra = value.keys() - set(required) - set(optional)
        if extra:
            raise ContractConflict(f"{label} 含未定义字段：{', '.join(sorted(extra))}")
    return value


def _text(value, label):
    if value is None or isinstance(value, str) and not value.strip():
        raise ContractMissing(f"缺少 {label}")
    if not isinstance(value, str) or any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ContractConflict(f"{label} 必须是有效文字")
    return value


def _id(value, label):
    value = _text(value, label)
    if not ID.fullmatch(value):
        raise ContractConflict(f"{label} 不是有效的稳定 ID：{value}")
    return value


def _variants(value, label, allowed=None):
    if value is None or value == []:
        raise ContractMissing(f"{label} 缺少显式变体列表")
    if not isinstance(value, list):
        raise ContractConflict(f"{label} 的 variants 必须是列表")
    variants = {_text(item, f"{label} 的变体") for item in value}
    if len(variants) != len(value):
        raise ContractConflict(f"{label} 的 variants 重复")
    if allowed is not None and variants - allowed:
        raise ContractConflict(f"{label} 引用未声明的变体：{', '.join(sorted(variants - allowed))}")
    return variants


def _relative_path(value, label, suffixes):
    value = _text(value, f"{label}.path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} or part.casefold() == ".git" or part.rstrip(" .") != part
           or INVALID_PATH_CHAR.search(part) or PureWindowsPath(part).is_reserved() for part in parts):
        raise ContractConflict(f"{label} 必须使用工程内普通相对路径：{value}")
    path = Path(*parts)
    if path.suffix.lower() not in suffixes:
        raise ContractConflict(f"{label} 路径未获该工件角色允许：{value}")
    return path


def _local(path, label):
    try:
        # Use the shared reparse-point and local-volume checks. The missing-file
        # case is handled separately so it does not become a conflict.
        return local_file(path, input_file=False).resolve(strict=True)
    except (ValueError, RuntimeError) as exc:
        raise ContractConflict(f"{label} 路径无效：{exc}") from exc
    except OSError as exc:
        raise ContractMissing(f"无法读取 {label}：{path}") from exc


def _verified_file(spec, root, label, suffixes, *, read=None, own_path=None, expected_path=None):
    _object(spec, label, ("path", "sha256"))
    digest = _text(spec["sha256"], f"{label}.sha256")
    if not DIGEST.fullmatch(digest):
        raise ContractConflict(f"{label} 的 SHA-256 格式无效")
    relative = _relative_path(spec["path"], label, suffixes)
    path = _local(root / relative, label)
    if not path.is_relative_to(root.resolve()):
        raise ContractConflict(f"{label} 真实路径位于工程外：{path}")
    if expected_path is not None and path != _local(expected_path, "--contract"):
        raise ContractConflict("--contract 路径与 case 绑定的系统契约不符")
    try:
        if own_path is not None and path.samefile(own_path):
            raise ContractConflict(f"{label} 引用了系统契约自身")
        with path.open("rb") as stream:
            if read is True or read == path.suffix.lower():
                payload = stream.read()
                actual = hashlib.sha256(payload).hexdigest()
            else:
                payload = None
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
    except OSError as exc:
        raise ContractMissing(f"无法读取 {label}：{path}") from exc
    if actual != digest:
        raise ContractConflict(f"{label} 文件内容与绑定 SHA-256 不符：{relative.as_posix()}")
    return path, payload


def _decode(raw, label, *, exact=False):
    def object_pairs(pairs):
        value = dict(pairs)
        if len(value) != len(pairs):
            raise ValueError("重复 JSON 字段或 ID")
        return value

    def bad_constant(value):
        raise ValueError(f"不是有限 JSON 数值：{value}")

    try:
        if exact:
            return json.loads(raw, object_pairs_hook=object_pairs, parse_float=Decimal,
                              parse_constant=bad_constant)
        return strict_json(raw)
    except (ValueError, InvalidOperation, RecursionError) as exc:
        raise ContractConflict(f"{label} JSON 无效：{exc}") from exc


def _at_pointer(data, pointer):
    for escaped in pointer[1:].split("/"):
        token = escaped.replace("~1", "/").replace("~0", "~")
        if isinstance(data, dict):
            data = data[token]
        elif isinstance(data, list) and re.fullmatch(r"(?:0|[1-9][0-9]{0,8})", token):
            data = data[int(token)]
        else:
            raise KeyError(token)
    return data


def _brief(spec, root, own_path):
    _object(spec, "brief_ref", ("path", "sha256", "requirements"), ())
    requirements = _object(spec["requirements"], "brief_ref.requirements")
    path, raw = _verified_file(spec, root, "brief_ref", {".yaml", ".yml", ".json"},
                               read=True, own_path=own_path)
    try:
        document = raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ContractMissing("brief 需要可读取的 UTF-8 文本") from exc
    data = _decode(raw, "brief_ref") if path.suffix.lower() == ".json" or document.lstrip().startswith("{") else None
    lines = document.splitlines()
    if isinstance(data, dict) and data.get("schema") in DOWNSTREAM_SCHEMAS:
        raise ContractConflict("brief_ref 指向下游工件")
    for name, locator in requirements.items():
        label = f"brief_ref.requirements.{_id(name, '需求 ID')}"
        locator = _text(locator, label)
        line = LINE.fullmatch(locator)
        try:
            if line:
                item = lines[int(line[1]) - 1].strip()
                found = bool(item) and not item.startswith("#")
            elif locator.startswith("/") and not re.search(r"~(?![01])", locator):
                if data is None:
                    raise ContractMissing(f"{label} 在普通 YAML 中使用 #L 行定位，JSON Pointer 需要 JSON 格式")
                found = _at_pointer(data, locator) not in (None, "", [], {})
            else:
                raise ContractConflict(f"{label} 需要 JSON Pointer 或 #L 行定位")
        except (KeyError, IndexError):
            found = False
        if not found:
            raise ContractMissing(f"{label} 未在 brief 中定位到需求：{locator}")
    return requirements


def _anchor(name, row, root, own_path, own_digest, baseline):
    role = _text(row["role"], f"anchors.{name}.role")
    if role not in ANCHOR_SUFFIXES:
        raise ContractConflict(f"anchors.{name} 使用未允许的工件角色：{role}")
    path, raw = _verified_file(row, root, f"anchors.{name}", ANCHOR_SUFFIXES[role], read=".json", own_path=own_path)
    if path.name.casefold() in DOWNSTREAM_NAMES:
        raise ContractConflict(f"anchors.{name} 引用了下游工件：{path.name}")
    if raw is None:
        return
    data = _decode(raw, f"anchors.{name}")
    if isinstance(data, dict) and data.get("schema") in DOWNSTREAM_SCHEMAS:
        raise ContractConflict(f"anchors.{name} 引用了下游工件：{path.name}")
    if isinstance(data, dict) and data.get("schema") == "hardware-evidence-envelope-v1":
        coverage = data.get("coverage")
        engineering = coverage.get("engineering") if isinstance(coverage, dict) else None
        if (isinstance(engineering, dict) and engineering.get("project") == baseline["project"]
                and engineering.get("revision") == baseline["revision"]
                and engineering.get("variant") in row["variants"]):
            checks = engineering.get("checks")
            if isinstance(checks, dict) and any(isinstance(claim, dict) and "contract_sha256" in claim
                                                for claim in checks.values()):
                raise ContractConflict(f"anchors.{name} 引用了依赖当前契约的工程回执：{path.name}")
    pending = [data]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            ref = value.get("path")
            if value.get("sha256") == own_digest:
                raise ContractConflict(f"anchors.{name} 的内容引用当前或下游工件：{path.name}")
            if isinstance(ref, str):
                target = Path(ref.replace("\\", "/"))
                if target.name.casefold() in DOWNSTREAM_NAMES or own_path in (root / target, path.parent / target):
                    raise ContractConflict(f"anchors.{name} 的内容引用当前或下游工件：{path.name}")
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)


def _scalar(value, label):
    if value is None:
        raise ContractMissing(f"缺少 {label}")
    if type(value) not in (int, Decimal):
        raise ContractConflict(f"{label} 必须是有限数值")
    try:
        measured = float(value)
    except (OverflowError, ValueError) as exc:
        raise ContractConflict(f"{label} 超出有限度量范围") from exc
    if not math.isfinite(measured) or measured == 0 and value != 0:
        raise ContractConflict(f"{label} 超出有限度量范围")
    return Fraction(value)


def _criterion(row, label, requirements):
    requirement = _id(row["requirement"], f"{label}.requirement")
    if requirement not in requirements:
        raise ContractMissing(f"{label} 引用了未知需求 {requirement}")
    unit = _text(row["unit"], f"{label}.unit")
    if any(char.isspace() or not char.isprintable() for char in unit):
        raise ContractConflict(f"{label}.unit 必须是明确的单位符号")
    op = _text(row["op"], f"{label}.op")
    if op not in OPS:
        raise ContractConflict(f"{label} 比较方向无效：{op}")
    limit = _scalar(row["limit"], f"{label}.limit")
    if "allocations" not in row:
        return
    values = row["allocations"]
    if not isinstance(values, list) or not values:
        raise ContractConflict(f"{label}.allocations 需要同单位的非空标量列表")
    total = sum(_scalar(value, f"{label}.allocations[{index}]") for index, value in enumerate(values))
    if not OPS[op](total, limit):
        raise ContractConflict(f"{label} 的同单位线性分配合计未满足 {op} {row['limit']} {unit}")


def _reference(value, label, records, scope):
    name = _id(value, label)
    if name not in records:
        raise ContractMissing(f"{label} 引用了未知 ID {name}")
    absent = scope - set(records[name]["variants"])
    if absent:
        raise ContractConflict(f"{label} 引用 {name} 的变体范围缺少 {', '.join(sorted(absent))}")
    return name


def _reference_list(value, label, records, scope):
    if not isinstance(value, list) or not value:
        raise ContractConflict(f"{label} 需要非空 ID 列表")
    names = {_reference(item, label, records, scope) for item in value}
    if len(names) != len(value):
        raise ContractConflict(f"{label} 包含重复 ID")


def _edges(contract, nodes, variants, check_ids):
    graphs = defaultdict(lambda: defaultdict(list))
    for group in ("links", "dependencies"):
        edges = contract[group]
        if edges is None:
            raise ContractMissing(f"缺少 {group}")
        if not isinstance(edges, list):
            raise ContractConflict(f"{group} 必须是列表")
        present = set()
        records = contract["ports"] if group == "links" else nodes
        for index, row in enumerate(edges):
            label = f"{group}[{index}]"
            _object(row, label, ("source", "target", "variants"), ("condition",) if group == "links" else ())
            scope = _variants(row["variants"], label, variants)
            source = _reference(row["source"], f"{label}.source", records, scope)
            target = _text(row["target"], f"{label}.target")
            if group == "dependencies" and target.startswith("check:"):
                check = _id(target.removeprefix("check:"), f"{label}.target")
                if check not in check_ids:
                    raise ContractMissing(f"{label} 引用了未知检查 {check}")
            else:
                _reference(target, f"{label}.target", records, scope)
            condition = None
            if "condition" in row:
                condition = _reference(row["condition"], f"{label}.condition", contract["conditions"], scope)
            for variant in sorted(scope):
                edge = (source, target, condition, variant)
                if edge in present:
                    raise ContractConflict(f"{label} 在变体 {variant} 重复声明边 {source} → {target}")
                present.add(edge)
                if group == "dependencies" and target in nodes:
                    graphs[variant][source].append(target)
    for variant, graph in graphs.items():
        incoming = dict.fromkeys(graph, 0)
        for targets in graph.values():
            for target in targets:
                incoming[target] = incoming.get(target, 0) + 1
        ready = deque(name for name, count in incoming.items() if count == 0)
        visited = 0
        while ready:
            visited += 1
            for target in graph.get(ready.popleft(), ()):
                incoming[target] -= 1
                if incoming[target] == 0:
                    ready.append(target)
        if visited != len(incoming):
            raise ContractConflict(f"变体 {variant} 的 dependencies 存在循环")


def _baseline(contract, baseline):
    project = _object(contract, "baseline", ("project", "revision", "variants"), ())
    _object(baseline, "case.baseline", ("project", "revision", "variant"))
    for key in ("project", "revision"):
        if _text(project[key], f"baseline.{key}") != _text(baseline[key], f"case.baseline.{key}"):
            raise ContractConflict(f"系统契约与 case 的 {key} 不一致")
    declared = _variants(project["variants"], "baseline")
    variant = _text(baseline["variant"], "case.baseline.variant")
    if variant not in declared:
        raise ContractConflict(f"case 的变体不属于系统契约：{variant}")
    return declared


def load(spec, root, baseline, check_ids, *, expected_path=None):
    """Verify the bound snapshot, its project-local material and graph."""
    root = Path(root).absolute()
    own_path, raw = _verified_file(spec, root, "artifacts.system_contract", {".json"}, read=True,
                                   expected_path=expected_path)
    contract = _decode(raw, "系统契约", exact=True)
    _object(contract, "系统契约", ("schema", "baseline", "brief_ref", "links", "dependencies", *NODE_GROUPS), ())
    if contract["schema"] != SCHEMA:
        raise ContractConflict("系统契约 schema 无效")
    variants = _baseline(contract["baseline"], baseline)
    requirements = _brief(contract["brief_ref"], root, own_path)
    fields = {
        "blocks": (("role",), ()),
        "ports": (("block", "kind", "role", "domain"), ("locator", "gap", "anchor")),
        "conditions": (("state", "window"), ("environment",)),
        "criteria": (("requirement", "condition", "point", "op", "limit", "unit"), ("allocations",)),
        "decisions": (("statement",), ("condition", "method", "anchors", "affected")),
        "anchors": (("path", "sha256", "role"), ("locator",)),
    }
    nodes = {}
    for group, (required, optional) in fields.items():
        for name, row in _object(contract[group], group).items():
            label = f"{group}.{_id(name, f'{group} ID')}"
            if name in nodes:
                raise ContractConflict(f"系统契约的对象 ID 重复：{name}")
            nodes[name] = _object(row, label, (*required, "variants"), optional)
            _variants(row["variants"], label, variants)
            for key in sorted(row.keys() - {"variants", "limit", "allocations", "anchors", "affected"}):
                _text(row[key], f"{label}.{key}")
    for name, row in contract["ports"].items():
        scope = set(row["variants"])
        _reference(row["block"], f"ports.{name}.block", contract["blocks"], scope)
        if "anchor" in row:
            _reference(row["anchor"], f"ports.{name}.anchor", contract["anchors"], scope)
    points = contract["blocks"] | contract["ports"] | contract["anchors"]
    for name, row in contract["criteria"].items():
        label = f"criteria.{name}"
        _criterion(row, label, requirements)
        scope = set(row["variants"])
        _reference(row["condition"], f"{label}.condition", contract["conditions"], scope)
        _reference(row["point"], f"{label}.point", points, scope)
    for name, row in contract["decisions"].items():
        scope = set(row["variants"])
        if "condition" in row:
            _reference(row["condition"], f"decisions.{name}.condition", contract["conditions"], scope)
        if "anchors" in row:
            _reference_list(row["anchors"], f"decisions.{name}.anchors", contract["anchors"], scope)
        if "affected" in row:
            _reference_list(row["affected"], f"decisions.{name}.affected", nodes, scope)
    _edges(contract, nodes, variants, check_ids)
    for name, row in contract["anchors"].items():
        _anchor(name, row, root, own_path, spec["sha256"], baseline)
    return contract


def _check_id(value, group):
    if not isinstance(value, str) or not value.startswith("contract:"):
        return None
    prefix = f"contract:{group}:"
    if not value.startswith(prefix) or not ID.fullmatch(value[len(prefix):]):
        raise ContractConflict(f"无效契约引用：{value}")
    return value[len(prefix):]


def _canonical_scalar(value):
    sign, digits, exponent = Decimal(value).as_tuple()
    coefficient = "".join(map(str, digits)).rstrip("0")
    if not coefficient:
        return "0"
    return f"{'-' if sign else ''}{coefficient}e{exponent + len(digits) - len(coefficient)}"


def _point_snapshot(contract, name, variant):
    scope = {variant}
    result = {}
    for group in ("blocks", "ports", "anchors"):
        records = contract[group]
        if name not in records:
            continue
        _reference(name, "criterion.point", records, scope)
        point = records[name]
        result[group] = {name: {**point, "variants": [variant]}}
        if group == "ports":
            for related_group, field in (("blocks", "block"), ("anchors", "anchor")):
                if field in point:
                    related_id = _reference(point[field], f"criterion.point.{field}", contract[related_group], scope)
                    result[related_group] = {related_id: {**contract[related_group][related_id], "variants": [variant]}}
        return result
    raise ContractMissing(f"criterion.point 引用了未知测点 {name}")


def binding(contract, baseline, condition, criterion):
    """Bind referenced criterion and condition semantics within the case variant."""
    condition_id = _check_id(condition, "condition")
    criterion_id = _check_id(criterion, "criterion")
    if condition_id is None and criterion_id is None:
        return None
    if contract is None:
        raise ContractMissing("契约检查缺有效的系统契约")
    _baseline(contract["baseline"], baseline)
    variant = baseline["variant"]
    scope = {variant}
    fingerprint = {"schema": SCHEMA, "baseline": {key: baseline[key] for key in ("project", "revision", "variant")}}
    if condition_id is not None:
        _reference(condition_id, "case.condition", contract["conditions"], scope)
    if criterion_id is not None:
        _reference(criterion_id, "case.criterion", contract["criteria"], scope)
        record = contract["criteria"][criterion_id]
        if condition_id is not None and condition_id != record["condition"]:
            raise ContractConflict("case 的工况与规范化判据声明的工况不匹配")
        condition_id = record["condition"]
        scoped = {**record, "variants": [variant], "limit": _canonical_scalar(record["limit"])}
        if "allocations" in record:
            scoped["allocations"] = [_canonical_scalar(value) for value in record["allocations"]]
        fingerprint["criterion"] = {criterion_id: scoped}
        fingerprint["point"] = _point_snapshot(contract, record["point"], variant)
    fingerprint["condition"] = {condition_id: {**contract["conditions"][condition_id], "variants": [variant]}}
    encoded = json.dumps(fingerprint, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
