"""Independently read local Gerber and Excellon files with explicit role and geometry expectations."""

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path, PureWindowsPath
import re
import sys
import warnings

sys.path.insert(0, str(Path(__file__).absolute().parents[2] / "hardware/scripts"))
from evidence_adapter import artifact, envelope, skipped, strict_json
from hardware_tool import local_file


SCHEMA = "hardware-cam-input-v1"
ROLE = re.compile(r"[a-z][a-z0-9_-]*")
DIGEST = re.compile(r"[0-9a-fA-F]{64}")


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def input_contract(value):
    if (not isinstance(value, dict) or set(value) != {"schema", "required_roles", "tolerance_mm", "layers"}
            or value["schema"] != SCHEMA):
        raise ValueError("CAM 清单字段或版本错误")
    required = value["required_roles"]
    if (not isinstance(required, list) or not all(isinstance(role, str) and ROLE.fullmatch(role) for role in required)
            or "outline" not in required or len(set(required)) != len(required)):
        raise ValueError("required_roles 需要无重复且含 outline 的层角色")
    tolerance = value["tolerance_mm"]
    if not finite(tolerance) or tolerance < 0:
        raise ValueError("tolerance_mm 需要非负的有限数")
    layers = value["layers"]
    if not isinstance(layers, dict):
        raise ValueError("layers 需要按角色给出映射")
    paths = set()
    for role, layer in layers.items():
        base = {"path", "kind", "unit", "bounds_mm", "sha256"}
        if (not ROLE.fullmatch(role) or not isinstance(layer, dict) or not base <= layer.keys()
                or layer["kind"] not in ("gerber", "excellon")
                or (role == "outline" and layer["kind"] != "gerber")
                or layer["unit"] not in ("mm", "inch")
                or not isinstance(layer["sha256"], str) or not DIGEST.fullmatch(layer["sha256"])):
            raise ValueError(f"{role} 需要相对路径、格式、原生单位、边界和冻结摘要")
        expected_keys = base | ({"drills", "slots"} if layer["kind"] == "excellon" else set())
        if set(layer) != expected_keys:
            raise ValueError(f"{role} 的字段与格式不符")
        if layer["kind"] == "excellon" and any(type(layer[key]) is not int or layer[key] < 0 for key in ("drills", "slots")):
            raise ValueError(f"{role} 的孔与槽数需要非负整数")
        bounds = layer["bounds_mm"]
        if (not isinstance(bounds, list) or len(bounds) != 4 or not all(map(finite, bounds))
                or bounds[0] > bounds[2] or bounds[1] > bounds[3]):
            raise ValueError(f"{role} 需要 [min_x, min_y, max_x, max_y] 型毫米边界")
        filename = layer["path"]
        if not isinstance(filename, str) or not filename.strip() or filename != filename.strip():
            raise ValueError(f"{role} 的文件路径无效")
        path = PureWindowsPath(filename)
        if not path.parts or path.drive or path.root or ".." in path.parts or path in paths:
            raise ValueError(f"{role} 的路径必须是独立的清单目录内相对路径")
        paths.add(path)
    return required, layers, tolerance


def read_layer(gerbonara, raw, layer, tolerance):
    text = raw.decode("utf-8-sig")
    if layer["kind"] == "gerber":
        if not re.search(r"%MO(?:MM|IN)\*%", text) or not re.search(r"M02\*\s*\Z", text):
            raise ValueError("Gerber 缺少显式单位或 M02 结束命令")
        parser = gerbonara.GerberFile
    else:
        if not re.search(r"(?m)^(?:METRIC|INCH)(?:,|\s|$)", text) or not re.search(r"(?m)^M30\s*\Z", text):
            raise ValueError("Excellon 缺少显式单位或 M30 结束命令")
        parser = gerbonara.ExcellonFile
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        parsed = parser.from_string(text)
        bounds = parsed.bounding_box(gerbonara.MM)
        unit = parsed.import_settings.unit
    if bounds is None or unit not in (gerbonara.MM, gerbonara.Inch):
        raise ValueError("图层缺少可读几何或明确单位")
    coordinates = [coordinate for point in bounds for coordinate in point]
    if not all(map(finite, coordinates)):
        raise ValueError("图层边界含非有限坐标")
    actual = {
        "unit": "mm" if unit == gerbonara.MM else "inch",
        "bounds_mm": coordinates, "primitive_count": len(parsed.objects),
        "warnings": [str(warning.message) for warning in captured],
    }
    issues = []
    if actual["unit"] != layer["unit"]:
        issues.append("unit_mismatch")
    if any(abs(number - expected) > tolerance for number, expected in zip(coordinates, layer["bounds_mm"])):
        issues.append("geometry_mismatch")
    if layer["kind"] == "excellon":
        actual.update(drills=sum(1 for _ in parsed.drills()), slots=sum(1 for _ in parsed.slots()))
        for name in ("drills", "slots"):
            if actual[name] != layer[name]:
                issues.append(f"{name}_count_mismatch")
    status = "fail" if issues else "review_required" if captured else "pass"
    return dict(actual, status=status, issues=issues)


def check(path):
    raw = path.read_bytes()
    required, layers, tolerance = input_contract(strict_json(raw))
    inputs = {"manifest": artifact(path, sha256(raw).hexdigest())}
    omitted = [
        skipped("supplier_dfm", "只检查显式映射、单位、几何边界和孔槽计数"),
        skipped("bom_cpl_and_orientation", "装配对账及方向使用对应的发布和贴装检查"),
        skipped("outline_closed_and_drill_plating", "仅比较外接边界和孔槽计数"),
        skipped("native_source_export", "输入为已有 CAM 文件，原生导出需独立留证"),
    ]
    native = {"parser_version": None, "layers": {}, "required_roles": required, "tolerance_mm": tolerance}
    try:
        import gerbonara
    except ImportError:
        return envelope(
            backend="gerbonara", stage="cam_readback", execution="unsupported",
            verification="not_evaluated", native=native, inputs=inputs,
            skipped_checks=[*omitted, *(skipped(f"layer:{role}", "Python 环境缺少 gerbonara")
                                        for role in sorted(set(required) | layers.keys()))],
        )
    native["parser_version"] = gerbonara.__version__
    executed = []
    for role in sorted(set(required) | layers.keys()):
        label = f"layer:{role}"
        layer = layers.get(role)
        if layer is None:
            native["layers"][role] = {"status": "missing", "reason": "清单缺少必需图层"}
            omitted.append(skipped(label, "清单缺少必需图层"))
            continue
        try:
            source = local_file(path.parent.joinpath(*PureWindowsPath(layer["path"]).parts), input_file=False)
            raw = source.read_bytes()
            digest = sha256(raw).hexdigest()
            inputs[label] = artifact(source, digest)
            if digest != layer["sha256"].lower():
                raise ValueError("工件摘要与冻结清单不一致")
            native["layers"][role] = read_layer(gerbonara, raw, layer, tolerance)
            executed.append(label)
        except (OSError, ValueError, RuntimeError, ArithmeticError, KeyError) as error:
            status = "missing" if isinstance(error, FileNotFoundError) else "invalid"
            native["layers"][role] = {"status": status, "reason": str(error)}
            omitted.append(skipped(label, str(error)))
    statuses = {layer["status"] for layer in native["layers"].values()}
    verification = next((status for status in ("invalid", "missing", "fail", "review_required") if status in statuses), "pass")
    return envelope(
        backend="gerbonara", stage="cam_readback", verification=verification, native=native,
        inputs=inputs, executed=executed, skipped_checks=omitted,
        coverage={"required_roles": required, "mapped_roles": sorted(layers)},
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("manifest")
    args = parser.parse_args()
    try:
        record = check(local_file(args.manifest))
    except (OSError, ValueError, OverflowError) as error:
        print(json.dumps({"status": "invalid_input", "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return {"pass": 0, "fail": 1, "review_required": 1}.get(record["verification_status"], 2)


if __name__ == "__main__":
    raise SystemExit(main())
