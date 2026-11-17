"""Map an electronic BOM to the material archive template and verify the CSV."""

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit
from zipfile import BadZipFile


DEFAULT_TEMPLATE = Path(__file__).resolve().parents[1] / "assets" / "物料档案_模板V1.csv"
ALIASES = {
    "名称": ("物料名称", "器件名称", "Component Name", "Name"),
    "规格": ("规格值", "Value", "Specification"),
    "型号": ("完整型号", "原厂型号", "Manufacturer Part Number", "MPN"),
    "品牌": ("制造商", "Manufacturer", "Brand"),
    "封装": ("Footprint", "Package", "PCB Footprint"),
    "位号": ("Designator", "Designators", "RefDes", "Reference Designator"),
    "MPN料号": ("立创料号", "立创编号", "LCSC Part #", "LCSC Part Number", "LCSC Part", "C号"),
    "数量": ("Qty", "Quantity"),
    "层级": ("Level",),
    "描述": ("Description",),
    "备注": ("Remarks", "Notes"),
    "DNP": ("不贴装", "不装", "DNF", "Do Not Populate"),
    "变体": ("Variant", "Assembly Variant"),
}
STRUCTURAL_FIELDS = ("位号", "数量", "层级", "DNP", "变体")
IDENTIFIER_FIELDS = {"编码", "型号", "封装", "位号", "MPN料号", "图号", "版本号", "国标号"}
PLACEHOLDERS = {"待核实", "待核查", "待核对", "待确认", "未录入", "未标注"}
LCSC_CODE = re.compile(r"C[0-9]+\Z")
DNP_FALSE = {"", "0", "0.0", "false", "no", "n", "否"}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path, header_row):
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file, strict=True)
        for _ in range(header_row - 1):
            next(reader, None)
        return next(reader, []), list(reader)


def validate_header(header, label):
    values = [value.strip() if isinstance(value, str) else "" for value in header]
    while values and values[-1] == "":
        values.pop()
    if not values or "" in values or len({value.casefold() for value in values}) != len(values):
        raise ValueError(f"{label}表头为空、存在中间空列或重复列。请核对表头行。")
    return values


def resolve_columns(source, output, overrides):
    indexes = {value.casefold(): index for index, value in enumerate(source)}
    expected = set(output) | set(STRUCTURAL_FIELDS)
    if not isinstance(overrides, dict) or set(overrides) - expected:
        raise ValueError("字段映射须使用目标模板字段、DNP 或变体作键。")
    mapping = {}
    for field in output + [value for value in STRUCTURAL_FIELDS if value not in output]:
        if field in overrides:
            name = overrides[field]
            if name is None:
                continue
            if not isinstance(name, str) or name.casefold() not in indexes:
                raise ValueError(f"字段 {field} 的源列不存在。")
            mapping[field] = indexes[name.casefold()]
        elif field.casefold() in indexes:
            mapping[field] = indexes[field.casefold()]
        else:
            matches = {indexes[name.casefold()] for name in ALIASES.get(field, ()) if name.casefold() in indexes}
            if len(matches) > 1:
                raise ValueError(f"字段 {field} 对应多个源列。请用 --column-map 选定。")
            if matches:
                mapping[field] = matches.pop()
    return mapping


def read_source(path, sheet_name, header_row):
    if path.suffix.casefold() == ".csv":
        if sheet_name:
            raise ValueError("--sheet 只适用于 XLSX。")
        return read_csv(path, header_row)
    if path.suffix.casefold() != ".xlsx":
        raise ValueError("输入须为 UTF-8 CSV 或 XLSX。")
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise ValueError("读取 XLSX 需要已安装的 openpyxl。也可使用 UTF-8 CSV。") from exc

    with path.open("rb") as file:
        book = load_workbook(file, read_only=True, data_only=False, keep_links=False)
        try:
            if not sheet_name and len(book.sheetnames) != 1:
                raise ValueError(f"工作簿有多张表，请指定 --sheet。表名为 {book.sheetnames}。")
            name = sheet_name or book.sheetnames[0]
            if name not in book.sheetnames:
                raise ValueError(f"找不到工作表 {name}。")
            rows = book[name].iter_rows(min_row=header_row)
            header = [cell.value for cell in next(rows, ())]
            cells = [[(cell.value, cell.data_type, cell.number_format) for cell in row] for row in rows]
            return header, cells
        finally:
            book.close()


def source_text(value, field, row, issues):
    normalized = value
    if value.strip() in PLACEHOLDERS:
        normalized = ""
    elif field == "描述" and "://" not in value:
        normalized = "/".join(part for part in value.split("/") if part.strip() not in PLACEHOLDERS)
    if normalized != value:
        issues.append({"row": row, "field": field, "code": "omitted_placeholder"})
    return normalized


def field_value(value, field, row, issues):
    if isinstance(value, str):
        return source_text(value, field, row, issues)
    raw, data_type, number_format = value
    if raw is None:
        return ""
    if data_type in {"f", "e"}:
        raise ValueError(f"第 {row} 行字段 {field} 含公式或 Excel 错误值，请先确认实际值。")
    if isinstance(raw, str):
        return source_text(raw, field, row, issues)
    if isinstance(raw, bool):
        return "TRUE" if raw else "FALSE"
    if isinstance(raw, (int, float)):
        if isinstance(raw, int) and re.fullmatch(r"0{2,}", number_format or ""):
            return str(raw).zfill(len(number_format))
        if field in IDENTIFIER_FIELDS:
            issues.append({"row": row, "field": field, "code": "numeric_identifier"})
        return str(raw)
    raise ValueError(f"第 {row} 行字段 {field} 含未支持的日期或对象，请提供所需文本。")


def evidence_index(payload):
    if not isinstance(payload, dict) or payload.get("reviewed") is not True or not isinstance(payload.get("parts"), list):
        raise ValueError("器件证据需提供 reviewed: true 和 parts 数组。")
    result = defaultdict(set)
    for part in payload["parts"]:
        if not isinstance(part, dict):
            raise ValueError("每条器件证据须为 JSON 对象。")
        values = [part.get(key) for key in ("mpn", "brand", "package", "lcsc_code", "product_url")]
        if not all(isinstance(value, str) and value.strip() == value and value for value in values):
            raise ValueError("每条证据需有完整 mpn、brand、package、lcsc_code、product_url 文本。")
        mpn, brand, package, code, url = values
        link = urlsplit(url)
        if (not LCSC_CODE.fullmatch(code) or link.scheme != "https" or link.netloc != "item.szlcsc.com"
                or link.path in {"", "/"}):
            raise ValueError("器件证据须使用精确 C 号和国内立创 HTTPS 商品页。")
        result[mpn, brand, package].add((code, url))
    return result


def fill_existing_part(record, index, issues, row):
    supplier = record.get("供应商", "")
    if supplier not in {"", "立创商城"}:
        return False
    references = index.get(tuple(record.get(key, "") for key in ("型号", "品牌", "封装")), set())
    codes = {code for code, _ in references}
    existing = record.get("MPN料号", "")
    if existing and codes and existing not in codes:
        issues.append({"row": row, "code": "existing_part_conflict"})
    if existing:
        return False
    if len(codes) == 1:
        record["MPN料号"] = next(iter(codes))
        return True
    if record.get("型号") or record.get("位号"):
        issues.append({"row": row, "code": "ambiguous_part" if codes else "missing_exact_part_evidence"})
    return False


def prepare_rows(source, source_width, output, mapping, evidence, is_v1, header_row):
    records = []
    issues = []
    filled = 0
    previous_level = None
    for line, raw in enumerate(source, header_row + 1):
        cells = [cell[0] if isinstance(cell, tuple) else cell for cell in raw]
        populated = [cell is not None and cell != "" for cell in cells]
        if not any(populated):
            continue
        if any(populated[source_width:]):
            raise ValueError(f"第 {line} 行在表头外还有数据，请检查 CSV 转义或输入列。")
        record = {field: field_value(raw[index], field, line, issues) if index < len(raw) else ""
                  for field, index in mapping.items()}
        if not any(record.values()):
            raise ValueError(f"第 {line} 行无可映射字段，请核对模板和字段映射。")
        for field in STRUCTURAL_FIELDS:
            if field not in output and record.get(field) and (field not in {"DNP", "变体"} or "备注" not in output):
                raise ValueError(f"第 {line} 行的 {field} 无对应列，需使用可保留该字段的模板。")
        metadata = [f"{field}={record[field]}" for field in ("DNP", "变体") if record.get(field) and field not in output]
        if metadata:
            record["备注"] = " | ".join(part for part in (record.get("备注", ""), *metadata) if part)
        if record.get("封装") in {"201", "402", "603", "805"}:
            issues.append({"row": line, "field": "封装", "code": "package_padding_unknown"})
        if is_v1:
            if "单位" not in mapping and record.get("数量"):
                record["单位"] = "PCS"
            if "大类" not in mapping and record.get("位号"):
                record["大类"] = "电子元器件"
            if "状态" not in mapping and record.get("DNP", "").strip().casefold() in DNP_FALSE:
                record["状态"] = "启用"
        level = record.get("层级", "")
        if level:
            if not re.fullmatch(r"[0-9]+", level):
                issues.append({"row": line, "code": "unrecognized_level"})
                previous_level = None
            else:
                current_level = int(level)
                if (previous_level is None and not records and current_level > 1
                        or previous_level is not None and current_level > previous_level + 1):
                    issues.append({"row": line, "code": "hierarchy_gap"})
                previous_level = current_level
        elif previous_level is not None:
            issues.append({"row": line, "code": "missing_level"})
            previous_level = None
        if evidence is not None:
            filled += fill_existing_part(record, evidence, issues, line)
        records.append([record.get(field, "") for field in output])
    if not records:
        raise ValueError("找不到可转换的 BOM 记录。")
    return records, filled, issues


def output_csv(path, rows):
    if path.suffix.casefold() != ".csv":
        raise ValueError("输出须以 .csv 结尾。")
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"输出文件已存在，请另选路径。{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="", dir=path.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            csv.writer(temporary, lineterminator="\r\n").writerows(rows)
        with temporary_path.open(encoding="utf-8-sig", newline="") as file:
            if list(csv.reader(file, strict=True)) != rows:
                raise ValueError("CSV 读回与目标行不一致。")
        if os.name == "nt":
            temporary_path.rename(path)
        else:
            os.link(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="电子 BOM，支持 UTF-8 CSV 或 XLSX")
    parser.add_argument("--sheet", help="XLSX 工作表名称")
    parser.add_argument("--header-row", type=int, default=1, help="源表头行号，自 1 起")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE, help="首行为字段的 CSV 模板")
    parser.add_argument("--column-map", type=Path, help="目标列到源列的 JSON 映射")
    parser.add_argument("--evidence", type=Path, help="经核对的器件证据 JSON")
    parser.add_argument("--output", type=Path, help="写入新 CSV，省略则仅预检")
    parser.add_argument("--details", action="store_true", help="输出全部警告，默认仅首 12 项")
    args = parser.parse_args()
    if args.header_row < 1:
        parser.error("--header-row 至少为 1。")
    try:
        source_header, source = read_source(args.input, args.sheet, args.header_row)
        source_fields = validate_header(source_header, "输入")
        target_fields = validate_header(read_csv(args.template, 1)[0], "模板")
        overrides = read_json(args.column_map) if args.column_map else {}
        mapping = resolve_columns(source_fields, target_fields, overrides)
        evidence = evidence_index(read_json(args.evidence)) if args.evidence else None
        if evidence is not None and "MPN料号" not in target_fields:
            raise ValueError("补 C 号需要模板的 MPN料号列。")
        use_v1 = args.template.resolve() == DEFAULT_TEMPLATE.resolve()
        rows, filled, issues = prepare_rows(source, len(source_fields), target_fields, mapping, evidence, use_v1,
                                            args.header_row)
        if args.output:
            output_csv(args.output, [target_fields, *rows])
        report = {"status": "verified" if args.output else "preview", "rows": len(rows),
                  "output": str(args.output.resolve()) if args.output else None,
                  "mapped_columns": {field: source_fields[index] for field, index in mapping.items()},
                  "unmapped_columns": [field for index, field in enumerate(source_fields) if index not in mapping.values()],
                  "filled_part_codes": filled, "issue_counts": dict(Counter(issue["code"] for issue in issues)),
                  "issues": issues if args.details else issues[:12]}
        print(json.dumps(report, ensure_ascii=False))
    except (OSError, ValueError, csv.Error, BadZipFile) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
