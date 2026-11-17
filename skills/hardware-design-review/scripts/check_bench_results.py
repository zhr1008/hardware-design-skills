"""Compare recorded measurements with explicit limits for one board and firmware build."""

from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import io
import json
from pathlib import Path
import re


IDENTITY = ("board_id", "hardware_revision", "firmware_sha256")
FIELDS = ("test_id", "value", "unit", *IDENTITY)
DECIMAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
EXIT_CODES = {"pass": 0, "fail": 1, "invalid": 2, "missing": 3}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("限值 JSON 包含重复键")
        result[key] = value
    return result


def invalid_constant(_):
    raise ValueError("限值 JSON 包含非有限数")


def required_text(value, field):
    if not isinstance(value, str) or not value.strip() or not value.isprintable():
        raise ValueError(f"{field} 需要非空单行文本")
    return value.strip()


def identity(record):
    result = {field: required_text(record.get(field), field) for field in IDENTITY}
    digest = result["firmware_sha256"]
    if re.fullmatch(r"[A-Fa-f0-9]{64}", digest) is None:
        raise ValueError("firmware_sha256 需要 64 位十六进制 SHA-256")
    result["firmware_sha256"] = digest.lower()
    return result


def decimal_value(value, field):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError(f"{field} 需要有限十进制数")
    text = str(value).strip()
    if DECIMAL.fullmatch(text) is None:
        raise ValueError(f"{field} 需要有限十进制数")
    try:
        return Decimal(text)
    except InvalidOperation:
        raise ValueError(f"{field} 需要有限十进制数") from None


def parse_limits(raw):
    spec = json.loads(raw.decode("utf-8-sig"), parse_float=Decimal,
                      parse_constant=invalid_constant, object_pairs_hook=unique_object)
    if (not isinstance(spec, dict) or set(spec) != {"schema_version", "limit_set_id", "tests", *IDENTITY}
            or type(spec["schema_version"]) is not int or spec["schema_version"] != 1):
        raise ValueError("限值 JSON 需要版本 1、限值 ID、完整板卡身份与 tests")
    limit_set_id = required_text(spec["limit_set_id"], "limit_set_id")
    board = identity(spec)
    if not isinstance(spec["tests"], dict) or not spec["tests"]:
        raise ValueError("tests 需要至少一项测试")

    limits = {}
    for test_id, limit in spec["tests"].items():
        if required_text(test_id, "test_id") != test_id:
            raise ValueError("限值的 test_id 不允许首尾空白")
        if (not isinstance(limit, dict) or set(limit) - {"unit", "min", "max"}
                or not {"min", "max"} & limit.keys()):
            raise ValueError(f"{test_id} 需要单位和至少一个上下限，且只允许 unit、min、max")
        unit = required_text(limit.get("unit"), f"{test_id} 的 unit")
        minimum = decimal_value(limit["min"], f"{test_id} 的 min") if "min" in limit else None
        maximum = decimal_value(limit["max"], f"{test_id} 的 max") if "max" in limit else None
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError(f"{test_id} 的 min 大于 max")
        limits[test_id] = (unit, minimum, maximum)
    return limit_set_id, board, limits


def parse_measurements(raw, limits):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    fields = reader.fieldnames or []
    if len(fields) != len(FIELDS) or set(fields) != set(FIELDS):
        raise ValueError("测量 CSV 表头必须恰含 " + ", ".join(FIELDS))
    samples = {test_id: [] for test_id in limits}
    issues = []
    for row in reader:
        line = reader.line_num
        if None in row or None in row.values():
            issues.append({"line": line, "reason": "CSV 列数与表头不一致"})
            continue
        test_id = row["test_id"].strip()
        if test_id not in samples:
            issues.append({"line": line, "test_id": test_id, "reason": "测试 ID 未在限值中定义"})
            continue
        samples[test_id].append((line, row))
    return samples, issues


def assess_test(test_id, limit, samples, board):
    unit, minimum, maximum = limit
    result = {
        "test_id": test_id, "unit": unit, "lines": [line for line, _ in samples],
        "min": str(minimum) if minimum is not None else None,
        "max": str(maximum) if maximum is not None else None,
    }
    if not samples:
        return dict(result, status="missing", reason="没有实测行")
    if len(samples) > 1:
        return dict(result, status="invalid", reason="需要单次测量，出现重复测试 ID")

    _, row = samples[0]
    try:
        if identity(row) != board:
            raise ValueError("测量行的板号、硬件版次或固件摘要与限值不一致")
        if required_text(row["unit"], "unit") != unit:
            raise ValueError("测量单位与限值不一致")
        value = decimal_value(row["value"], "value")
    except ValueError as error:
        return dict(result, status="invalid", reason=str(error))
    within = (minimum is None or minimum <= value) and (maximum is None or value <= maximum)
    return dict(result, status="pass" if within else "fail", value=str(value))


def check(limits_raw, measurements_raw):
    report = {
        "sha256": {"limits": sha256(limits_raw).hexdigest(), "measurements": sha256(measurements_raw).hexdigest()},
        "results": [],
        "issues": [],
    }
    try:
        limit_set_id, board, limits = parse_limits(limits_raw)
        report.update(limit_set_id=limit_set_id, board=board)
        samples, issues = parse_measurements(measurements_raw, limits)
        report["issues"] = issues
        report["results"] = [
            assess_test(test_id, limit, samples[test_id], board)
            for test_id, limit in sorted(limits.items())
        ]
    except (ValueError, csv.Error, InvalidOperation) as error:
        report["issues"].append({"reason": str(error)})

    counts = dict.fromkeys(EXIT_CODES, 0)
    for result in report["results"]:
        counts[result["status"]] += 1
    report["counts"] = counts
    report["status"] = next(
        (status for status in ("invalid", "fail", "missing") if counts[status]
         or status == "invalid" and report["issues"]), "pass",
    )
    return report


def read_input(path):
    if str(path).startswith(("\\", "//")) or not path.is_file():
        raise ValueError("输入需要可读取的本地普通文件")
    return path.read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--limits", required=True, type=Path)
    parser.add_argument("--measurements", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = check(read_input(args.limits), read_input(args.measurements))
    except (OSError, ValueError) as error:
        report = {"status": "invalid", "issues": [{"reason": str(error)}]}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return EXIT_CODES[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
