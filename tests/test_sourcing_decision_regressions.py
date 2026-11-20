"""Exercise production-configuration, shared inventory, and quote boundaries."""

import csv
import datetime as dt
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1] / "skills" / "qualify-pcba-sourcing"
VALIDATOR = SKILL / "scripts" / "validate_sourcing_lock.py"
AS_OF = "2026-11-19T12:00:00Z"
LEGACY = {
    "reference": "U17", "function": "isolation buffer", "quantity_per_board": 1,
    "assembly_quantity": 50, "required_quantity": 50, "order_quantity": 50,
    "manufacturer": "Fixture Co.", "requested_mpn": "FIX-01", "mpn": "FIX-01",
    "supplier_part_number": "SKU-41", "package": "QFN-16", "package_verified": "yes",
    "footprint": "FIX-QFN16", "pinout_verified": "yes", "cad_status": "verified",
    "model_3d_status": "verified", "lifecycle": "active",
    "stock_checked_at": "2026-11-19T09:00:00Z", "stock_quantity": 100,
    "moq": 1, "unit_price": ".20", "currency": "CNY", "assembly_class": "Basic",
    "line_parts_cost": "10.00", "setup_fee": "0", "extended_fee": "0",
    "line_total_cost": "10.00", "datasheet_url": "https://example.invalid/buffer.pdf",
    "approved_alternates": "", "substitution_approved": "no",
    "substitution_approval_evidence": "", "design_critical": "yes",
    "approval_required": "yes", "status": "PASS",
    "evidence_url": "https://example.invalid/stock/snapshot-01",
}
EVIDENCE = {
    "qualification_scope": "required", "production_configurations": "fab-B",
    "qualified_configurations": "fab-A;fab-B", "qualification_manufacturer": "Fixture Co.",
    "qualification_mpn": "FIX-01", "qualification_package": "QFN-16",
    "qualification_evidence": "qualification-report-B#table-2",
    "supplier": "Fixture Supplier", "stock_pool": "warehouse-01",
    "quote_id": "quote-001", "quote_issued_at": "2026-11-19T10:00:00Z",
    "quote_valid_until": "2026-11-20T10:00:00Z", "quote_min_quantity": 50,
    "quote_max_quantity": 100, "quote_evidence": "https://example.invalid/quotes/quote-001",
}
SCOPED = {**LEGACY, **EVIDENCE}


class SourcingDecisionRegressions(unittest.TestCase):
    def invoke(self, *rows, as_of=AS_OF, flags=()):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sourcing-lock.csv"
            fields = dict.fromkeys(field for row in rows for field in row)
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fields)
                writer.writeheader()
                writer.writerows(rows)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            process = subprocess.run(
                [sys.executable, "-X", "utf8", "-B", str(VALIDATOR), str(path), "--as-of", as_of, *flags],
                capture_output=True, text=True, encoding="utf-8", check=False,
            )
        self.assertEqual(process.stderr, "", process.stdout + process.stderr)
        result = json.loads(process.stdout)
        if result["schema"] == "sourcing-lock-v2":
            self.assertEqual(result["sha256"], digest)
            self.assertEqual(dt.datetime.fromisoformat(result["as_of"]),
                             dt.datetime.fromisoformat(as_of.replace("Z", "+00:00")))
        return process.returncode, result

    def assert_status(self, expected, *rows, diagnostic=None, **kwargs):
        code, result = self.invoke(*rows, **kwargs)
        self.assertEqual(result["status"], expected, result)
        self.assertEqual(code, 0 if expected == "PASS" else 1, result)
        if diagnostic:
            reasons = result["errors"] + result.get("pending", [])
            self.assertTrue(any(diagnostic in reason for reason in reasons), reasons)
        return result

    def test_legacy_csv_keeps_original_checks_and_report(self):
        prior = self.assert_status("PASS", LEGACY)
        self.assertEqual(prior["schema"], "sourcing-lock-v1")
        self.assertEqual(prior["warnings"], [])
        self.assertNotIn("pending", prior)
        custom = self.assert_status("PASS", {**LEGACY, "supplier": "Fixture Supplier"})
        self.assertEqual(custom["schema"], "sourcing-lock-v1")
        self.assertEqual(custom["warnings"], ["extra headers: ['supplier']"])
        changed = {**LEGACY, "mpn": "FIX-02"}
        self.assert_status("BLOCKED", changed, diagnostic="selected alternate is not approved")
        approved = {**changed, "approved_alternates": "FIX-02", "substitution_approved": "yes",
                    "substitution_approval_evidence": "design-owner#FIX-02"}
        self.assert_status("PASS", approved)

    def test_same_mpn_cannot_reuse_qualification_for_previous_fab(self):
        industrial = {**SCOPED, "qualified_configurations": "fab-A"}
        self.assert_status("BLOCKED", industrial, diagnostic="fab-B")
        self.assert_status("PASS", {**industrial, "production_configurations": "fab-A"})
        self.assert_status("PASS", SCOPED)
        mixed_supply = {**industrial, "production_configurations": "fab-A;fab-B"}
        self.assert_status("BLOCKED", mixed_supply, diagnostic="fab-B")

    def test_qualification_is_bound_to_ordered_identity(self):
        for field in ("qualification_manufacturer", "qualification_mpn", "qualification_package"):
            with self.subTest(field=field):
                self.assert_status("BLOCKED", {**SCOPED, field: "different"}, diagnostic=field)
        approved = {**SCOPED, "mpn": "FIX-02", "approved_alternates": "FIX-02",
                    "substitution_approved": "yes", "substitution_approval_evidence": "design-owner#FIX-02"}
        self.assert_status("BLOCKED", approved, diagnostic="qualification_mpn")
        self.assert_status("PASS", {**approved, "qualification_mpn": "FIX-02"})

    def test_missing_new_evidence_is_pending(self):
        for field in ("qualification_scope", "production_configurations", "qualified_configurations",
                      "qualification_evidence", "supplier", "stock_pool", "quote_id", "quote_evidence"):
            with self.subTest(field=field):
                self.assert_status("USER_REVIEW", {**SCOPED, field: ""}, diagnostic=field)
        self.assert_status("USER_REVIEW", {**SCOPED, "production_configurations": "fab-B;待核实"},
                           diagnostic="production_configurations")
        wildcard = {**SCOPED, "production_configurations": "fab-*", "qualified_configurations": "fab-*"}
        self.assert_status("USER_REVIEW", wildcard, diagnostic="exact configuration IDs")
        self.assert_status("USER_REVIEW", {**LEGACY, "qualification_scope": "required"},
                           diagnostic="quote_id", flags=("--formal",))

    def test_not_required_needs_reviewed_project_basis(self):
        standard_part = {**SCOPED, "qualification_scope": "not-required", "production_configurations": "",
                         "qualified_configurations": "", "qualification_manufacturer": "", "qualification_mpn": "",
                         "qualification_package": "", "qualification_evidence": "project-spec#scope"}
        self.assert_status("PASS", standard_part)
        self.assert_status("USER_REVIEW", {**standard_part, "qualification_evidence": ""})
        self.assert_status("BLOCKED", {**standard_part, "qualification_mpn": "FIX-01"}, diagnostic="conflicts")

    def test_stock_combines_orders_even_with_different_quote_ids(self):
        u17 = {**SCOPED, "stock_quantity": 60}
        u18 = {**u17, "reference": "U18", "quote_id": "quote-002"}
        self.assert_status("BLOCKED", u17, u18, diagnostic="aggregate order quantity 100")
        self.assert_status("PASS", u17, {**u18, "stock_pool": "warehouse-02"})
        self.assert_status("PASS", u17, {**u18, "supplier": "Other Supplier"})
        self.assert_status("PASS", u17, {**u18, "supplier_part_number": "SKU-42"})

    def test_stock_pool_needs_one_coherent_snapshot(self):
        u18 = {**SCOPED, "reference": "U18"}
        self.assert_status("BLOCKED", SCOPED, {**u18, "stock_quantity": 150}, diagnostic="stock snapshot")
        self.assert_status("BLOCKED", SCOPED, {**u18, "stock_checked_at": "2026-11-19T09:01:00Z"},
                           diagnostic="stock snapshot")

    def test_quote_uses_aggregate_order_and_inclusive_tier(self):
        u17 = {**SCOPED, "quote_min_quantity": 100}
        u18 = {**u17, "reference": "U18"}
        self.assert_status("PASS", u17, u18)
        self.assert_status("PASS", u17, {**u18, "stock_pool": "warehouse-02"})
        self.assert_status("BLOCKED", u17, diagnostic="outside quoted tier")
        self.assert_status("BLOCKED", {**u17, "quote_max_quantity": 99}, diagnostic="quote_min_quantity")
        self.assert_status("PASS", {**SCOPED, "quote_max_quantity": "unbounded"})
        self.assert_status("BLOCKED", SCOPED, {**u18, "quote_min_quantity": 50, "quote_max_quantity": 90},
                           diagnostic="conflicting quote terms")

    def test_quote_freshness_is_independent_of_stock(self):
        self.assert_status("PASS", SCOPED, as_of=SCOPED["quote_issued_at"])
        self.assert_status("PASS", SCOPED, as_of=SCOPED["quote_valid_until"])
        self.assert_status("BLOCKED", SCOPED, as_of="2026-11-20T10:00:01Z", diagnostic="quote has expired")
        self.assert_status("BLOCKED", SCOPED, as_of="2026-11-19T09:59:59Z", diagnostic="quote is not yet valid")
        self.assert_status("USER_REVIEW", {**SCOPED, "quote_valid_until": ""}, diagnostic="quote_valid_until")
        self.assert_status("BLOCKED", {**SCOPED, "quote_valid_until": "2026-11-20"}, diagnostic="UTC offset")

    def test_short_formal_row_is_pending_instead_of_raising(self):
        self.assert_status("USER_REVIEW", SCOPED, {**LEGACY, "reference": "U18"}, diagnostic="quote_id")

    def test_explicit_formal_check_does_not_accept_legacy_evidence(self):
        result = self.assert_status("USER_REVIEW", LEGACY, flags=("--formal",), diagnostic="qualification_scope")
        self.assertEqual(result["schema"], "sourcing-lock-v2")

    def test_formal_template_covers_the_fixture_headers(self):
        with (SKILL / "assets" / "sourcing-lock-v2.csv").open(encoding="utf-8", newline="") as handle:
            self.assertCountEqual(next(csv.reader(handle)), SCOPED)


if __name__ == "__main__":
    unittest.main()
