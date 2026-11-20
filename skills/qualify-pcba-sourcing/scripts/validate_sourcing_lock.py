#!/usr/bin/env python3
"""Validate sourcing lock evidence, quantities, approvals, and cost."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


FIELDS = [
    "reference", "function", "quantity_per_board", "assembly_quantity",
    "required_quantity", "order_quantity", "manufacturer", "requested_mpn",
    "mpn", "supplier_part_number", "package", "package_verified", "footprint",
    "pinout_verified", "cad_status", "model_3d_status", "lifecycle",
    "stock_checked_at", "stock_quantity", "moq", "unit_price", "currency",
    "assembly_class", "line_parts_cost", "setup_fee", "extended_fee",
    "line_total_cost", "datasheet_url", "approved_alternates",
    "substitution_approved", "substitution_approval_evidence",
    "design_critical", "approval_required", "status", "evidence_url",
]
QUALIFICATION_IDENTITY = {
    "qualification_manufacturer": "manufacturer",
    "qualification_mpn": "mpn",
    "qualification_package": "package",
}
EVIDENCE_FIELDS = {
    "qualification_scope", "production_configurations", "qualified_configurations",
    *QUALIFICATION_IDENTITY, "qualification_evidence", "supplier", "stock_pool",
    "quote_id", "quote_issued_at", "quote_valid_until", "quote_min_quantity",
    "quote_max_quantity", "quote_evidence",
}
UNRESOLVED = {"", "-", "?", "*", "any", "all", "tbd", "unknown", "unspecified", "n/a", "待证", "待核实"}
ROW_STATUSES = {"PASS", "BLOCKED", "USER_REVIEW"}
LIFECYCLES = {"active", "nrnd", "eol", "obsolete", "last-time-buy", "unknown"}
EVIDENCE_STATES = {"verified", "unverified", "missing", "not-required"}


@dataclass(frozen=True)
class QuoteTerms:
    issued: dt.datetime
    expires: dt.datetime
    minimum: int
    maximum: int | None
    price: float


def parse_time(value: str, *, require_offset: bool = False) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        if require_offset:
            raise ValueError("timestamp requires a UTC offset")
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def references(value: str) -> list[str]:
    return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]


def integer(row: dict[str, str], field: str, number: int, errors: list[str], *, positive: bool = True) -> int | None:
    try:
        value = int(row.get(field, ""))
        if value < (1 if positive else 0):
            raise ValueError
        return value
    except (ValueError, TypeError):
        qualifier = "positive" if positive else "non-negative"
        errors.append(f"row {number}: {field} must be a {qualifier} integer")
        return None


def decimal(row: dict[str, str], field: str, number: int, errors: list[str]) -> float | None:
    try:
        value = float(row.get(field, ""))
        if not math.isfinite(value) or value < 0:
            raise ValueError
        return value
    except (ValueError, TypeError):
        errors.append(f"row {number}: {field} must be a non-negative finite number")
        return None


def evidence_value(row: dict[str, str], field: str, number: int, pending: list[str]) -> str:
    value = row.get(field, "").strip()
    if value.casefold() in UNRESOLVED:
        pending.append(f"row {number}: {field} evidence is missing")
        return ""
    return value


def configuration_set(row: dict[str, str], field: str, number: int, pending: list[str]) -> set[str]:
    value = evidence_value(row, field, number, pending)
    configurations = set(references(value))
    if value and (not configurations or any(
        item.casefold() in UNRESOLVED or "*" in item or "?" in item for item in configurations
    )):
        pending.append(f"row {number}: {field} needs exact configuration IDs")
        return set()
    return configurations


def check_qualification(row: dict[str, str], number: int, errors: list[str], pending: list[str]) -> None:
    scope = evidence_value(row, "qualification_scope", number, pending)
    evidence_value(row, "qualification_evidence", number, pending)
    if scope == "required":
        production = configuration_set(row, "production_configurations", number, pending)
        covered = configuration_set(row, "qualified_configurations", number, pending)
        if production and covered and (uncovered := production - covered):
            errors.append(f"row {number}: production configurations outside qualification: {sorted(uncovered)}")
        for field, identity_field in QUALIFICATION_IDENTITY.items():
            value = evidence_value(row, field, number, pending)
            if value and value != row.get(identity_field, "").strip():
                errors.append(f"row {number}: {field} does not match selected {identity_field}")
    elif scope == "not-required":
        if row.get("production_configurations", "").strip():
            configuration_set(row, "production_configurations", number, pending)
        if any(row.get(field, "").strip() for field in ("qualified_configurations", *QUALIFICATION_IDENTITY)):
            errors.append(f"row {number}: qualification coverage conflicts with not-required scope")
    elif scope:
        errors.append(f"row {number}: qualification_scope must be required or not-required")


def quote_terms(
    row: dict[str, str], number: int, as_of: dt.datetime, price: float | None,
    errors: list[str], pending: list[str],
) -> QuoteTerms | None:
    dates = {}
    for field in ("quote_issued_at", "quote_valid_until"):
        if value := evidence_value(row, field, number, pending):
            try:
                dates[field] = parse_time(value, require_offset=True)
            except (ValueError, OverflowError):
                errors.append(f"row {number}: {field} must be an ISO timestamp with UTC offset")
    issued = dates.get("quote_issued_at")
    expires = dates.get("quote_valid_until")
    if issued is not None and expires is not None and expires < issued:
        errors.append(f"row {number}: quote_valid_until precedes quote_issued_at")
    if issued is not None and as_of < issued:
        errors.append(f"row {number}: quote is not yet valid")
    if expires is not None and as_of > expires:
        errors.append(f"row {number}: quote has expired")

    minimum_text = evidence_value(row, "quote_min_quantity", number, pending)
    maximum_text = evidence_value(row, "quote_max_quantity", number, pending)
    minimum = integer(row, "quote_min_quantity", number, errors) if minimum_text else None
    maximum = integer(row, "quote_max_quantity", number, errors) if maximum_text not in {"", "unbounded"} else None
    if minimum is not None and maximum is not None and maximum < minimum:
        errors.append(f"row {number}: quote_max_quantity is below quote_min_quantity")
    evidence = evidence_value(row, "quote_evidence", number, pending)
    if None in (issued, expires, minimum, price) or not evidence or (maximum is None and maximum_text != "unbounded"):
        return None
    return QuoteTerms(issued, expires, minimum, maximum, price)


def check_purchase_groups(
    stock_groups: dict[tuple[str, str, str], list[tuple[int, int, int, dt.datetime]]],
    quote_groups: dict[tuple[str, str, str], list[tuple[int, int, QuoteTerms | None]]],
    errors: list[str],
) -> None:
    for key, orders in stock_groups.items():
        order_total = sum(quantity for _, quantity, _, _ in orders)
        snapshots = {(stock, checked) for _, _, stock, checked in orders}
        row_numbers = [number for number, _, _, _ in orders]
        if len(snapshots) > 1:
            errors.append(f"rows {row_numbers}: inventory pool {key!r} has conflicting stock snapshots")
            continue
        stock, _ = next(iter(snapshots))
        if order_total > stock:
            errors.append(f"rows {row_numbers}: inventory pool {key!r} stock {stock} is below "
                          f"aggregate order quantity {order_total}")

    for key, orders in quote_groups.items():
        order_total = sum(quantity for _, quantity, _ in orders)
        terms = {terms for _, _, terms in orders}
        confirmed = terms - {None}
        row_numbers = [number for number, _, _ in orders]
        if len(confirmed) > 1:
            errors.append(f"rows {row_numbers}: conflicting quote terms for {key!r}")
        elif None not in terms:
            quoted = next(iter(confirmed))
            if order_total < quoted.minimum or (quoted.maximum is not None and order_total > quoted.maximum):
                errors.append(f"rows {row_numbers}: aggregate order quantity {order_total} is outside quoted tier "
                              f"for {key!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--max-age-days", type=int, default=14)
    parser.add_argument("--as-of", help="ISO timestamp used for deterministic validation")
    parser.add_argument("--formal", action="store_true", help="require configuration and supplier evidence")
    args = parser.parse_args()
    as_of = parse_time(args.as_of) if args.as_of else dt.datetime.now(dt.timezone.utc)

    errors: list[str] = []
    warnings: list[str] = []
    pending: list[str] = []
    scoped = args.formal
    raw = None
    rows = []
    try:
        raw = args.csv_file.read_bytes()
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), restval="")
        headers = reader.fieldnames or []
        scoped = scoped or EVIDENCE_FIELDS.issubset(headers)
        missing = [field for field in FIELDS if field not in headers]
        extra = [field for field in headers if field not in FIELDS and (not scoped or field not in EVIDENCE_FIELDS)]
        if missing:
            errors.append(f"missing headers: {missing}")
        if extra:
            warnings.append(f"extra headers: {extra}")
        if scoped and len(headers) != len(set(headers)):
            errors.append("enhanced sourcing lock has duplicate headers")
        rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as error:
        errors.append(f"cannot read sourcing lock: {error}")

    if not rows:
        errors.append("sourcing lock has no component rows")

    seen: set[str] = set()
    row_statuses: list[str] = []
    assembly_quantities: set[int] = set()
    currencies: set[str] = set()
    stock_groups = defaultdict(list)
    quote_groups = defaultdict(list)
    total_cost = 0.0
    for number, row in enumerate(rows, start=2):
        if scoped and None in row:
            errors.append(f"row {number}: contains values without CSV headers")
        refs = references(row.get("reference", ""))
        if not refs:
            errors.append(f"row {number}: reference is required")
        for ref in refs:
            if ref in seen:
                errors.append(f"row {number}: duplicate reference {ref}")
            seen.add(ref)
        for field in (
            "function", "manufacturer", "requested_mpn", "mpn",
            "supplier_part_number", "package", "footprint", "currency",
            "assembly_class", "datasheet_url", "evidence_url",
        ):
            if not row.get(field, "").strip():
                errors.append(f"row {number}: {field} is required")
        for field in (
            "package_verified", "pinout_verified", "substitution_approved",
            "design_critical", "approval_required",
        ):
            if row.get(field, "").strip().lower() not in {"yes", "no"}:
                errors.append(f"row {number}: {field} must be yes or no")

        status = row.get("status", "").strip()
        row_statuses.append(status)
        if status not in ROW_STATUSES:
            errors.append(f"row {number}: invalid status")
        elif status == "BLOCKED":
            errors.append(f"row {number}: status is BLOCKED")

        package = row.get("package", "").strip()
        if re.search(r"\b(?:or|either|tbd|unknown)\b", package, re.IGNORECASE) or "|" in package:
            errors.append(f"row {number}: package is ambiguous")
        lifecycle = row.get("lifecycle", "").strip().lower()
        if lifecycle not in LIFECYCLES:
            errors.append(f"row {number}: invalid lifecycle")
        cad = row.get("cad_status", "").strip().lower()
        model = row.get("model_3d_status", "").strip().lower()
        if cad not in EVIDENCE_STATES:
            errors.append(f"row {number}: invalid cad_status")
        if model not in EVIDENCE_STATES:
            errors.append(f"row {number}: invalid model_3d_status")

        quantity = integer(row, "quantity_per_board", number, errors)
        assembly_quantity = integer(row, "assembly_quantity", number, errors)
        required = integer(row, "required_quantity", number, errors)
        order_quantity = integer(row, "order_quantity", number, errors)
        stock = integer(row, "stock_quantity", number, errors, positive=False)
        moq = integer(row, "moq", number, errors)
        if quantity is not None and refs and quantity != len(refs):
            errors.append(f"row {number}: quantity_per_board must equal grouped reference count")
        if assembly_quantity is not None:
            assembly_quantities.add(assembly_quantity)
        if quantity is not None and assembly_quantity is not None and required != quantity * assembly_quantity:
            errors.append(f"row {number}: required_quantity does not equal quantity_per_board * assembly_quantity")
        if order_quantity is not None and required is not None and order_quantity < required:
            errors.append(f"row {number}: order_quantity is below required_quantity")
        if order_quantity is not None and moq is not None and order_quantity < moq:
            errors.append(f"row {number}: order_quantity is below MOQ")
        if order_quantity is not None and stock is not None and stock < order_quantity:
            errors.append(f"row {number}: stock is below order_quantity")

        unit_price = decimal(row, "unit_price", number, errors)
        line_parts = decimal(row, "line_parts_cost", number, errors)
        setup_fee = decimal(row, "setup_fee", number, errors)
        extended_fee = decimal(row, "extended_fee", number, errors)
        line_total = decimal(row, "line_total_cost", number, errors)
        if order_quantity is not None and unit_price is not None and line_parts is not None:
            if not math.isclose(line_parts, order_quantity * unit_price, abs_tol=0.005):
                errors.append(f"row {number}: line_parts_cost does not equal order_quantity * unit_price")
        if None not in (line_parts, setup_fee, extended_fee, line_total):
            expected_total = float(line_parts) + float(setup_fee) + float(extended_fee)
            if not math.isclose(float(line_total), expected_total, abs_tol=0.005):
                errors.append(f"row {number}: line_total_cost does not reconcile")
            total_cost += float(line_total)
        currency = row.get("currency", "").strip().upper()
        if currency:
            currencies.add(currency)

        requested_mpn = row.get("requested_mpn", "").strip()
        selected_mpn = row.get("mpn", "").strip()
        if requested_mpn and selected_mpn and requested_mpn != selected_mpn:
            approved_alternates = references(row.get("approved_alternates", ""))
            if selected_mpn not in approved_alternates:
                errors.append(f"row {number}: selected alternate is not listed in approved_alternates")
            if row.get("substitution_approved", "").strip().lower() != "yes":
                errors.append(f"row {number}: selected alternate is not approved")
            if not row.get("substitution_approval_evidence", "").strip():
                errors.append(f"row {number}: approved alternate requires substitution_approval_evidence")

        if row.get("design_critical", "").lower() == "yes":
            if row.get("pinout_verified", "").lower() != "yes":
                errors.append(f"row {number}: design-critical pinout is unverified")
            if row.get("approval_required", "").lower() != "yes":
                errors.append(f"row {number}: design-critical part must require approval")
        if row.get("package_verified", "").lower() != "yes":
            errors.append(f"row {number}: package is unverified")
        if row.get("pinout_verified", "").lower() != "yes":
            errors.append(f"row {number}: pinout is unverified")
        if lifecycle in {"eol", "obsolete", "unknown"}:
            errors.append(f"row {number}: lifecycle is not orderable ({lifecycle})")
        if cad != "verified":
            errors.append(f"row {number}: CAD is not verified")
        if model not in {"verified", "not-required"}:
            errors.append(f"row {number}: 3D model is not verified or not-required")
        if status == "PASS":
            if lifecycle != "active":
                errors.append(f"row {number}: PASS requires active lifecycle")

        checked = None
        try:
            checked = parse_time(row.get("stock_checked_at", ""))
            age = as_of - checked
            if age.total_seconds() < 0:
                errors.append(f"row {number}: stock timestamp is in the future")
            elif age > dt.timedelta(days=args.max_age_days):
                errors.append(f"row {number}: stock evidence is stale ({age.days} days)")
        except (ValueError, TypeError, OverflowError):
            errors.append(f"row {number}: invalid stock_checked_at")
        if not row.get("datasheet_url", "").startswith(("https://", "http://")):
            errors.append(f"row {number}: datasheet_url must be an URL")

        if scoped:
            check_qualification(row, number, errors, pending)
            supplier = evidence_value(row, "supplier", number, pending)
            stock_pool = evidence_value(row, "stock_pool", number, pending)
            sku = evidence_value(row, "supplier_part_number", number, pending)
            evidence_value(row, "evidence_url", number, pending)
            quote_id = evidence_value(row, "quote_id", number, pending)
            terms = quote_terms(row, number, as_of, unit_price, errors, pending)
            if supplier and sku and order_quantity is not None:
                if stock_pool and stock is not None and checked is not None:
                    stock_groups[supplier, sku, stock_pool].append((number, order_quantity, stock, checked))
                if quote_id:
                    quote_groups[supplier, sku, quote_id].append((number, order_quantity, terms))

    check_purchase_groups(stock_groups, quote_groups, errors)
    if len(assembly_quantities) > 1:
        errors.append("assembly_quantity must be identical across sourcing rows")
    if len(currencies) > 1:
        errors.append("one sourcing lock must use one currency for total assembled cost")

    if errors or "BLOCKED" in row_statuses:
        overall = "BLOCKED"
    elif pending or "USER_REVIEW" in row_statuses:
        overall = "USER_REVIEW"
    else:
        overall = "PASS"
    result = {
        "schema": "sourcing-lock-v2" if scoped else "sourcing-lock-v1", "file": str(args.csv_file),
        "status": overall, "rows": len(rows), "references": len(seen),
        "assembly_quantity": next(iter(assembly_quantities)) if len(assembly_quantities) == 1 else None,
        "currency": next(iter(currencies)) if len(currencies) == 1 else None,
        "total_assembled_cost": round(total_cost, 6),
        "errors": errors, "warnings": warnings,
    }
    if scoped:
        result["pending"] = pending
        result["sha256"] = hashlib.sha256(raw).hexdigest() if raw is not None else None
        result["as_of"] = as_of.isoformat()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
