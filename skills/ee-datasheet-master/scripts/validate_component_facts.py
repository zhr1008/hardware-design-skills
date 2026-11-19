"""Validate component-fact records against an exact identity and optional local PDF."""

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


IDENTITY = ("manufacturer", "mpn", "package")
CATEGORIES = ("pin", "absolute_maximum", "recommended_operating", "electrical_characteristic")


def read_json(path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"重复 JSON 字段：{key}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"无效 JSON 常量：{value}")

    return json.loads(path.read_bytes(), object_pairs_hook=unique_object,
                      parse_float=Decimal, parse_constant=invalid_constant)


def text(value):
    return isinstance(value, str) and bool(value.strip()) and value.isprintable() and value == value.strip()


def exact_fields(value, fields, name):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError(f"{name} 的字段不符合合同")


def identity(value, name):
    exact_fields(value, IDENTITY, name)
    if not all(map(text, value.values())):
        raise ValueError(f"{name} 需要原厂、完整订购 MPN 和封装")
    return tuple(value[key] for key in IDENTITY)


def source_location(source, name):
    exact_fields(source, {"page", "location"}, f"{name}.source")
    if type(source["page"]) is not int or source["page"] < 1 or not text(source["location"]):
        raise ValueError(f"{name} 需要从 1 开始的 PDF 页码与表格、行或图定位")


def facts_contract(data, expected):
    exact_fields(data, {"schema", "identity", "datasheet", "facts"}, "器件事实")
    if data["schema"] != "hardware-component-facts-v1":
        raise ValueError("不支持的器件事实合同版本")
    target = identity(data["identity"], "器件")
    if any(value is not None and actual != value for value, actual in zip(expected, target)):
        raise ValueError("原厂、完整订购 MPN 或封装与指定身份不一致")
    datasheet = data["datasheet"]
    if datasheet is not None:
        exact_fields(datasheet, {"kind", "url", "revision", "sha256", "applies_to"}, "datasheet")
        url = urlsplit(datasheet["url"]) if text(datasheet["url"]) else None
        if (datasheet["kind"] != "manufacturer_datasheet" or not url or url.scheme not in {"https", "http"}
                or not url.hostname or url.username is not None or any(char.isspace() for char in datasheet["url"])
                or not text(datasheet["revision"])
                or not (text(datasheet["sha256"]) and re.fullmatch(r"[0-9a-fA-F]{64}", datasheet["sha256"]))):
            raise ValueError("datasheet 需要原厂资料类型、URL、版次和 PDF SHA-256")
        scope = datasheet["applies_to"]
        if not isinstance(scope, list) or not scope:
            raise ValueError("datasheet 需要已核对的适用身份")
        identities = [identity(item, "datasheet.applies_to") for item in scope]
        if len(identities) != len(set(identities)) or target not in identities:
            raise ValueError("datasheet 存在重复身份或与当前完整 MPN/封装不符")
    if not isinstance(data["facts"], list) or not data["facts"]:
        raise ValueError("facts 需要至少一项事实或待核实记录")

    seen = set()
    pins = set()
    unknown = []
    for item in data["facts"]:
        if not isinstance(item, dict):
            raise ValueError("facts 项需要对象")
        status = item.get("status")
        fields = {"id", "category", "status", "value", "conditions", "source"}
        exact_fields(item, fields | ({"reason"} if status == "unknown" else set()), "fact")
        name = item["id"]
        if not text(name) or name in seen or item["category"] not in CATEGORIES:
            raise ValueError("每项 fact 需要唯一 ID 与受支持的类别")
        seen.add(name)
        conditions = item["conditions"]
        if conditions is not None and (not isinstance(conditions, list) or
                                       not all(map(text, conditions)) or len(conditions) != len(set(conditions))):
            raise ValueError(f"{name} 的工况须为 null 或无重复的文本列表")
        if item["source"] is not None:
            if datasheet is None:
                raise ValueError(f"{name} 的来源定位缺少对应的 datasheet")
            source_location(item["source"], name)
        if status == "unknown":
            if item["value"] is not None or not text(item["reason"]):
                raise ValueError(f"{name} 的 unknown 需要原因和 null 值")
            unknown.append(name)
            continue
        if status != "supported" or item["source"] is None or conditions is None:
            raise ValueError(f"{name} 的 supported 需要来源页和已核对工况")
        value = item["value"]
        if item["category"] == "pin":
            exact_fields(value, {"number", "name", "role"}, name)
            if (not text(value["number"]) or not text(value["name"])
                    or value["role"] not in ("signal", "power", "ground", "nc", "exposed_pad", "other")
                    or value["number"] in pins):
                raise ValueError(f"{name} 的脚号、名称或角色不合法，或脚号重复")
            pins.add(value["number"])
            continue
        exact_fields(value, {"unit", "min", "typ", "max"}, name)
        bounds = [value[field] for field in ("min", "typ", "max") if value[field] is not None]
        if (not text(value["unit"]) or not bounds
                or any(type(number) not in (int, Decimal) or not Decimal(number).is_finite() for number in bounds)
                or bounds != sorted(bounds)):
            raise ValueError(f"{name} 需要单位、有限数字和顺序正确的 min/typ/max")
        if item["category"] in {"absolute_maximum", "recommended_operating"} and value["typ"] is not None:
            raise ValueError(f"{name} 的额定极限或推荐范围不能用典型值替代")
    return unknown


def pdf_digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise ValueError("PDF 输入缺少 %PDF- 标识")
        stream.seek(0)
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_pdf_pages(path, digest, facts):
    try:
        import pymupdf
    except ImportError as error:
        raise ValueError("页码校验需要数据手册专项的 PyMuPDF 后端") from error
    raw = path.read_bytes()
    if not raw.startswith(b"%PDF-") or hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("本地 PDF 与已记录 SHA-256 不一致或缺少 PDF 文件标识")
    try:
        with pymupdf.open(stream=raw, filetype="pdf") as document:
            if document.needs_pass or document.page_count < 1:
                raise ValueError("PDF 受密码保护或没有可读取的页")
            page_count = document.page_count
    except RuntimeError as error:
        raise ValueError(f"PDF 页树无法读取：{error}") from error
    for fact in facts:
        source = fact["source"]
        if source is not None and source["page"] > page_count:
            raise ValueError(f"{fact['id']} 的 PDF 页码 {source['page']} 超出原件 {page_count} 页")
    return page_count


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("facts", type=Path)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--verify-pages", action="store_true", help="用原件核对每条定位是否在 PDF 页数范围内")
    for field in IDENTITY:
        parser.add_argument(f"--expected-{field}")
    args = parser.parse_args()
    try:
        data = read_json(args.facts)
        unknown = facts_contract(data, tuple(getattr(args, f"expected_{key}") for key in IDENTITY))
        page_count = None
        if args.verify_pages and not args.pdf:
            raise ValueError("--verify-pages 需要 --pdf")
        if args.pdf:
            if data["datasheet"] is None:
                raise ValueError("器件事实未记录对应 PDF 摘要")
            digest = data["datasheet"]["sha256"].lower()
            if args.verify_pages:
                page_count = verify_pdf_pages(args.pdf, digest, data["facts"])
            elif pdf_digest(args.pdf) != digest:
                raise ValueError("本地 PDF 与已记录 SHA-256 不一致")
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "invalid", "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({
        "status": "review_required" if unknown else "valid_contract",
        "identity": data["identity"],
        "pdf_digest_verified": bool(args.pdf),
        "unknown_facts": unknown,
        "supported_count": len(data["facts"]) - len(unknown),
        **({"pdf_page_count": page_count, "pdf_page_ranges_verified": True} if page_count is not None else {}),
    }, ensure_ascii=False, indent=2))
    return 1 if unknown else 0


if __name__ == "__main__":
    raise SystemExit(main())
