"""Filter a user-supplied standard resistor/capacitor JSON index offline."""

import argparse
import json
import operator
import re
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


UNAVAILABLE = {"", "-", "—", "待核实", "未知", "n/a"}
LCSC_CODE = re.compile(r"C[0-9]+", re.IGNORECASE)
PARAMETER = re.compile(r"([^=<>]+?)(<=|>=|=)([^=<>]+)")
QUANTITY = re.compile(r"(±)?\s*([+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+))\s*(\S+)")
COMPARE = {"=": operator.eq, ">=": operator.ge, "<=": operator.le}
PREFIX_POWER = {"": 0, "p": -12, "n": -9, "u": -6, "m": -3, "k": 3, "K": 3, "M": 6, "G": 9}
BASE_UNITS = ("Ω", "F", "V", "W", "A")
INDEX_FIELDS = (
    "lcsc_id", "code", "mpn", "brand", "package", "category", "group", "parameters",
    "parameter_sources", "engineering_parameters", "verified_at", "evidence", "url", "datasheet",
    "comment", "generic_description", "description", "symbol", "footprint",
)


def known_text(value):
    if isinstance(value, str):
        value = value.strip()
        if value.casefold() not in UNAVAILABLE:
            return value
    return None


def quantity(text):
    match = QUANTITY.fullmatch(text)
    if match is None:
        return None
    symmetric, value, unit = match.groups()
    unit = unit.replace("µ", "u").replace("μ", "u").replace("Ω", "Ω").replace("℃", "°C")
    number = Decimal(value)
    if symmetric and (number < 0 or (unit not in {"%", "ppm/°C"} and not unit.endswith("F"))):
        return None
    if unit in {"%", "ppm/°C", "mm", "h"}:
        return (unit, symmetric), number
    if unit[-1] in BASE_UNITS and unit[:-1] in PREFIX_POWER:
        return (unit[-1], symmetric), number.scaleb(PREFIX_POWER[unit[:-1]])
    return None


@dataclass(frozen=True)
class ParameterCondition:
    name: str
    operation: str
    expected: str
    numeric: tuple | None

    @classmethod
    def parse(cls, expression):
        match = PARAMETER.fullmatch(expression)
        if match is None:
            raise argparse.ArgumentTypeError("参数条件格式为 名称=值、名称>=值 或 名称<=值")
        name, operation, expected = match.groups()
        name, expected = known_text(name), known_text(expected)
        if name is None or expected is None:
            raise argparse.ArgumentTypeError("参数名称和值需明确")
        numeric = quantity(expected)
        if operation != "=" and numeric is None:
            raise argparse.ArgumentTypeError("数值上下限需带支持的单位")
        return cls(name, operation, expected, numeric)

    def matches(self, value):
        actual = known_text(value)
        if actual is None:
            return None
        if self.numeric is None:
            return actual == self.expected
        measured = quantity(actual)
        if measured is None or measured[0] != self.numeric[0]:
            return None
        return COMPARE[self.operation](measured[1], self.numeric[1])


def query(records, *, code, mpn, fields, conditions, limit):
    matches, pending = [], []
    for part in records:
        codes = {value.upper() for key in ("lcsc_id", "code")
                 if (value := known_text(part.get(key))) and LCSC_CODE.fullmatch(value)}
        model = known_text(part.get("mpn"))
        if code and code.upper() not in codes:
            continue
        if mpn and (model is None or model.casefold() != mpn.casefold()):
            continue

        checks = []
        for key, expected in fields.items():
            if expected is not None:
                actual = known_text(part.get(key))
                checks.append((key, actual.casefold() == expected.casefold() if actual else None))
        parameters = part.get("parameters")
        if not isinstance(parameters, dict):
            parameters = {}
        checks.extend((condition.name, condition.matches(parameters.get(condition.name)))
                      for condition in conditions)
        if any(matched is False for _, matched in checks):
            continue

        unknown = list(dict.fromkeys(key for key, matched in checks if matched is None))
        if len(codes) > 1:
            unknown.append("lcsc_id 与 code 冲突")
        if not codes and model is None:
            unknown.append("lcsc_id/mpn")
        row = {key: part[key] for key in INDEX_FIELDS if key in part}
        if unknown:
            pending.append({**row, "unknown_conditions": unknown})
        else:
            matches.append(row)
    return {
        "source": "local_passive_index", "record_count": len(records),
        "matched_count": len(matches), "pending_count": len(pending),
        "matched": matches[:limit], "pending": pending[:limit],
        "truncated": len(matches) > limit or len(pending) > limit,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path, help="用户明确提供的 UTF-8 JSON 索引路径")
    parser.add_argument("--code", help="准确立创 C 号")
    parser.add_argument("--mpn", help="完整订购料号，忽略大小写")
    parser.add_argument("--group", help="准确分组名")
    parser.add_argument("--package", help="准确封装名")
    parser.add_argument("--brand", help="准确品牌名")
    parser.add_argument("--param", action="append", type=ParameterCondition.parse, default=[], metavar="条件")
    parser.add_argument("--limit", type=int, default=10, help="匹配项和待核实项各显示的最大条数")
    args = parser.parse_args()
    fields = {key: getattr(args, key) for key in ("group", "package", "brand")}
    if any(value is not None and known_text(value) is None for value in (args.mpn, *fields.values())):
        parser.error("筛选值需明确")
    if args.code is not None and not LCSC_CODE.fullmatch(args.code.strip()):
        parser.error("--code 需要准确的立创 C 号")
    if not (args.code or args.mpn or any(fields.values()) or args.param):
        parser.error("至少提供一个料号或规格条件")
    if args.limit < 1:
        parser.error("--limit 必须大于 0")
    try:
        with args.index.open(encoding="utf-8-sig") as stream:
            records = json.load(stream)
        if not isinstance(records, list) or any(not isinstance(part, dict) for part in records):
            raise ValueError("索引需要是由器件对象组成的 JSON 数组")
    except (OSError, ValueError) as exc:
        print(f"无法读取索引：{exc}", file=sys.stderr)
        return 1
    result = query(records, code=known_text(args.code), mpn=known_text(args.mpn),
                   fields={key: known_text(value) for key, value in fields.items()},
                   conditions=args.param, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
