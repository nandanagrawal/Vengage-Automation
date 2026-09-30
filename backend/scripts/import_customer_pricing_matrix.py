#!/usr/bin/env python3
"""
One-off import: read the "Customer Services And Billing Master Data" pricing
matrix CSV and create the corresponding CustomerProductAndService rows
(Flat, Slab or Fixed) for each existing customer.

Background
----------
The source file has TWO header rows, not one: row 1 (index 0) is the old,
verbose column description; row 2 (index 1) is a shorter alias for the same
column, in the same position. Row 2's text is what customer-product names and
this script's own target-sheet-column list below were matched against while
building COLUMN_MAP — see the two mapping blocks given in the request this
script was written for. A handful of columns (Consulting RAD/Dental preread,
Support charges B0005, Olivia AI cancellation-by-AI, Development charges
B0005, the trailing "(S) column" note) have zero data for every customer in
the current export and are intentionally left out of COLUMN_MAP; if a future
export populates one of them this script will just silently ignore it, so
re-check counts before assuming that's still safe.

"Strategic Care Pty Ltd." and its centre-customers (display names starting
with that prefix) are always skipped, per instruction.

Two customer names in the CSV don't exactly match this database and were
confirmed as the same company: NAME_OVERRIDES below.

Two more populated columns ("External E-Referral Charges", "Internal
E-Referral Transmission Charges" — 1 customer each) were confirmed to skip
for now rather than guess a target; STRAY_COLUMNS documents them so a rerun
doesn't silently drop them without saying so.

Pricing types
-------------
- A cell with one "$X.XX" (optionally with a trailing "(note)") is Flat:
  rate = X.XX, sheet_column = this column's target, the note (if any)
  becomes the row's description.
- A multi-line cell ("start-end: $rate" / "start+: $rate" per line, optional
  trailing note line) is Slab: one CustomerProductAndServiceSlab per tier,
  the row's own `rate` stays NULL, the trailing note (if any) becomes the
  row's description.
- The "E-Referral Portal Monthly Subscription Fees" column is Fixed:
  quantity = 1, rate = the cell's dollar value, no sheet column.

A (customer, product, sheet_column) combination that already has a row is
left untouched and reported as already-mapped — this script only adds rows,
it never edits or removes one.

Usage
-----
    cd backend

    # Accepts either the original .xlsx directly (reads its one sheet, or the
    # sheet named "Final sheet" if there's more than one — no manual CSV
    # conversion needed, which only invites transcription drift) or a .csv
    # export of it.

    # Dry run (default) — prints the full report, writes nothing.
    python scripts/import_customer_pricing_matrix.py path/to/pricing.xlsx

    # Apply the reported changes (creates missing Sheet Column Catalog
    # entries first, then the CustomerProductAndService/slab rows).
    python scripts/import_customer_pricing_matrix.py path/to/pricing.xlsx --apply

    # Separate pass: delete orphan rows with no data anywhere in the sheet.
    # Run this AFTER the normal --apply above, once every row that genuinely
    # has data has already been filled in.
    python scripts/import_customer_pricing_matrix.py path/to/pricing.xlsx --delete-unused
    python scripts/import_customer_pricing_matrix.py path/to/pricing.xlsx --delete-unused --apply

    # Separate pass: turn on Mail attachment for every customer in the sheet,
    # and set each of their centres' Drive file name(s) to "{centre name}.xls"
    # wherever that's currently blank (never overwrites an existing value).
    python scripts/import_customer_pricing_matrix.py path/to/pricing.xlsx --set-drive-defaults
    python scripts/import_customer_pricing_matrix.py path/to/pricing.xlsx --set-drive-defaults --apply
"""

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from app.models.center import Center
from app.models.customer import Customer
from app.models.customer_product_and_service import (
    CustomerProductAndService,
    CustomerProductAndServiceSlab,
    PricingType,
)
from app.models.product_and_service import ProductAndService
from app.models.sheet_column import SheetColumn


# ── Column layout — specific to this exact CSV export ──────────────────────

@dataclass
class ColumnSpec:
    row1_text: str                  # row-2 header text, for the sanity check
    product_candidates: list[str]   # tried in order; first existing match wins
    sheet_column_name: str | None   # None => Fixed (no sheet column)


COLUMN_MAP: dict[int, ColumnSpec] = {
    2: ColumnSpec("Olivia AI Complete BOOKING - B0001",
                   ["Olivia AI Complete BOOKING - B0001", "Olivia AI Complete Bookings B0001"], "Confirmed Appointment (4)"),
    3: ColumnSpec("Olivia AI Provisional BOOKING - B0001",
                   ["Olivia AI Provisional BOOKING - B0001", "Olivia AI - Provisional bookings B0001"], "Provisional Appointment (5)"),
    4: ColumnSpec("Olivia AI : Walkin calls handling charges - B0001",
                   ["Olivia AI  Walkin calls handling charges - B0001", "Olivia AI - Walk-in Call handling Charges B0001"],
                   "Walkin (7)"),
    5: ColumnSpec("Olivia AI Complete BOOKING (Online) - B0001",
                   ["Olivia AI Complete BOOKING - B0001", "Olivia AI Complete Bookings B0001"], "Confirmed Booking - Online Channel (17)"),
    6: ColumnSpec("Olivia AI Complete BOOKING (Telephony) - B0001",
                   ["Olivia AI Complete BOOKING - B0001", "Olivia AI Complete Bookings B0001"], "Confirmed Booking - Telephony Channel (18)"),
    7: ColumnSpec("Olivia AI Provisional BOOKING (Online)- B0001",
                   ["Olivia AI Provisional BOOKING - B0001", "Olivia AI - Provisional bookings B0001"], "Provisional Booking - Online Channel (19)"),
    8: ColumnSpec("Olivia AI Provisional BOOKING (Telephony)- B0001",
                   ["Olivia AI Provisional BOOKING - B0001", "Olivia AI - Provisional bookings B0001"], "Provisional Booking - Telephony Channel (20)"),
    9: ColumnSpec("Olivia Assist - Bookings  done by customer team (B0001)",
                   ["Olivia Assist - Bookings  done by customer team (B0001)",
                    "Olivia Assist - Bookings via customer portal ( B0001 )"],
                   "Appointments by Customer Reception (14)"),
    10: ColumnSpec("Olivia Specialist Portal Bookings B0001",
                    ["Olivia Specialist Portal Bookings B0001", "Bookings Via Specialist Portal B0001", "Olivia Specialist Portal Booking B0001"],
                    "Appointments by Specialist's Reception (15)"),
    11: ColumnSpec("Oiliva Call Forwards to Reception B0002",
                    ["Oiliva Call Forwards to Reception B0002", "Olivia Call Forwards to reception B0002"],
                    "Voice call forwarding BH and OOH (mins) (25)"),
    15: ColumnSpec("Non Appointment Call Handling Charges B0002",
                    ["Non Appointment Call Handling Charges B0002"], "Direct Call (6)"),
    16: ColumnSpec("E-Referral Greeting SMS Charges B0003",
                    ["E-Referral Greeting SMS Charges B0003"], "E-referral Greeting SMS Count (12)"),
    17: ColumnSpec("E-Referral Manual SMS Charges B0003",
                    ["E-Referral Manual SMS Charges B0003"], "E-referral Manual SMS Count (13)"),
    18: ColumnSpec("E-Referral Portal Monthly Subscription Fees B0003",
                    ["E-Referral Portal Monthly Subscription Fees B0003"], None),  # Fixed
    19: ColumnSpec("E-Referral Transmission Charges B0003",
                    ["E-Referral Transmission Charges B0003"], "Total E-referrals (11)"),
    # row0 header is "External E-Referral Charges B0003"; row1 is blank. Confirmed
    # this is really the same product/column as column 19, just entered under a
    # different label for this one customer.
    20: ColumnSpec("",
                    ["E-Referral Transmission Charges B0003"], "Total E-referrals (11)"),
}

# Populated, but explicitly left unmapped per instruction — reported, not processed.
STRAY_COLUMNS = {22: "Internal E-Referral Transmission Charges B0003"}

# CSV name -> other display_name(s) to also try. Wollongong in particular has
# flipped between "WDI - Wollongong Diagnostics" and "ALL CENTERS - Wollongong
# Diagnostics" more than once across QBO re-syncs of this validation database —
# both are listed so a resolution doesn't silently break the next time it flips.
NAME_OVERRIDES: dict[str, list[str]] = {
    "DNA Solutions Australia pty ltd (Scanaptics) - Kippax Medical Imaging": [
        "DNA Solutions Australia pty ltd (Scanaptics)",
    ],
    "WDI - Wollongong Diagnostics": [
        "ALL CENTERS - Wollongong Diagnostics",
    ],
}

EXCLUDE_PREFIX = "strategic care pty ltd"


def _resolve_customer(db, csv_name: str) -> Customer | None:
    for candidate in [csv_name, *NAME_OVERRIDES.get(csv_name, [])]:
        row = db.query(Customer).filter(Customer.display_name == candidate).first()
        if row:
            return row
    return None

_RATE_RE = re.compile(r"^\$?\s*([\d,]+(?:\.\d+)?)\s*(\(.*\))?\s*$")
_SLAB_CLOSED_RE = re.compile(r"^(\d+)\s*-\s*(\d+)\s*:\s*\$?\s*([\d,]+(?:\.\d+)?)\s*$")
_SLAB_OPEN_RE = re.compile(r"^(\d+)\s*\+\s*:\s*\$?\s*([\d,]+(?:\.\d+)?)\s*$")


@dataclass
class _Tier:
    start: int
    end: int | None
    rate: Decimal


@dataclass
class _ParsedCell:
    kind: str  # "flat" | "slab" | "error"
    rate: Decimal | None = None
    tiers: list[_Tier] = field(default_factory=list)
    note: str | None = None
    error: str | None = None


def _parse_cell(raw: str) -> _ParsedCell | None:
    text = raw.strip()
    if not text:
        return None
    if "\n" in text:
        tiers: list[_Tier] = []
        notes: list[str] = []
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            m = _SLAB_CLOSED_RE.match(line)
            if m:
                tiers.append(_Tier(int(m.group(1)), int(m.group(2)), Decimal(m.group(3).replace(",", ""))))
                continue
            m = _SLAB_OPEN_RE.match(line)
            if m:
                tiers.append(_Tier(int(m.group(1)), None, Decimal(m.group(2).replace(",", ""))))
                continue
            notes.append(line.strip("() "))
        if not tiers:
            return _ParsedCell(kind="error", error=f"no tier lines parsed from {text!r}")
        return _ParsedCell(kind="slab", tiers=tiers, note=" / ".join(notes) or None)

    m = _RATE_RE.match(text)
    if not m:
        return _ParsedCell(kind="error", error=f"unparseable cell {text!r}")
    rate = Decimal(m.group(1).replace(",", ""))
    note = m.group(2).strip("() ") if m.group(2) else None
    return _ParsedCell(kind="flat", rate=rate, note=note)


@dataclass
class _Plan:
    customer_id: int
    customer_name: str
    product_id: int
    product_name: str
    sheet_column_name: str | None
    pricing_type: PricingType
    rate: Decimal | None
    quantity: Decimal | None
    tiers: list[_Tier]
    description: str | None
    # Set when an existing row for this (customer, product) already exists with
    # no sheet column — that row is reused (UPDATEd) instead of inserting a new,
    # duplicate-looking row. existing_rate/existing_tiers are its current values,
    # compared numerically (not as formatted strings) against this plan's own
    # rate/tiers for the "will change from X to Y" report.
    existing_row_id: int | None = None
    existing_pricing_type: PricingType | None = None
    existing_rate: Decimal | None = None
    existing_tiers: list[_Tier] = field(default_factory=list)


def _cell_str(value: object) -> str:
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)


def _load_rows_xlsx(path: str) -> tuple[list[str], list[str], list[list[str]]]:
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True)
    if len(wb.sheetnames) == 1:
        ws = wb.worksheets[0]
    else:
        matches = [n for n in wb.sheetnames if n.strip().lower() == "final sheet"]
        if not matches:
            raise SystemExit(
                f"Workbook has multiple sheets ({wb.sheetnames}) and none is named "
                f"'Final sheet' — pick the right one and adjust _load_rows_xlsx."
            )
        ws = wb[matches[0]]
    rows = [
        [_cell_str(ws.cell(row=r, column=c).value) for c in range(1, ws.max_column + 1)]
        for r in range(1, ws.max_row + 1)
    ]
    return rows[0], rows[1], rows[2:]


def _load_rows(path: str) -> tuple[list[str], list[str], list[list[str]]]:
    if path.lower().endswith((".xlsx", ".xlsm", ".xls")):
        return _load_rows_xlsx(path)
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1], rows[2:]


def _sanity_check(header1: list[str]) -> None:
    for idx, spec in COLUMN_MAP.items():
        actual = header1[idx].strip() if idx < len(header1) else "<missing>"
        if actual != spec.row1_text:
            raise SystemExit(
                f"Column layout mismatch at index {idx}: expected {spec.row1_text!r}, "
                f"found {actual!r}. This script's COLUMN_MAP is hardcoded to one exact "
                f"CSV export — aborting rather than risk writing prices against the wrong "
                f"product. Re-check the file, or update COLUMN_MAP to match."
            )


def _resolve_product(db, candidates: list[str]) -> ProductAndService | None:
    for name in candidates:
        row = db.query(ProductAndService).filter(ProductAndService.name == name).first()
        if row:
            return row
    return None


def _find_reusable_row(db, customer_id: int, product_id: int) -> CustomerProductAndService | None:
    """An existing row for this (customer, product) with no sheet column and no
    centre — almost always a leftover from an older import that predates sheet
    columns. Reused (its sheet_column_id/rate/tiers updated) instead of leaving
    it dead and adding a second, duplicate-looking row for the same product."""
    return (
        db.query(CustomerProductAndService)
        .filter(
            CustomerProductAndService.customer_id == customer_id,
            CustomerProductAndService.product_and_service_id == product_id,
            CustomerProductAndService.sheet_column_id.is_(None),
            CustomerProductAndService.center_id.is_(None),
        )
        .first()
    )


def _existing_tiers(row: CustomerProductAndService) -> list[_Tier]:
    return [_Tier(s.range_start, s.range_end, s.rate) for s in sorted(row.slabs, key=lambda s: s.range_start)]


def _tiers_equal(a: list[_Tier], b: list[_Tier]) -> bool:
    if len(a) != len(b):
        return False
    return all(x.start == y.start and x.end == y.end and x.rate == y.rate for x, y in zip(a, b))


def _format_price(pricing_type: PricingType, rate: Decimal | None, tiers: list[_Tier]) -> str:
    if pricing_type == PricingType.slab:
        formatted = ", ".join(
            (f"{t.start}-{t.end}: ${t.rate}" if t.end is not None else f"{t.start}+: ${t.rate}")
            for t in tiers
        )
        return f"slab [{formatted}]"
    return f"${rate}"


def _discover(db, csv_path: str) -> tuple[list[_Plan], list[str], set[str], list[str], list[str]]:
    header0, header1, data_rows = _load_rows(csv_path)
    _sanity_check(header1)

    plans: list[_Plan] = []
    customers_not_found: list[str] = []
    missing_sheet_columns: set[str] = set()
    already_mapped: list[str] = []
    parse_errors: list[str] = []

    existing_sheet_columns = {sc.name: sc for sc in db.query(SheetColumn).all()}
    resolved_products: dict[tuple[str, ...], ProductAndService | None] = {}

    for row in data_rows:
        name = (row[0] if row else "").strip()
        if not name:
            continue
        if name.lower().startswith(EXCLUDE_PREFIX):
            continue
        customer = _resolve_customer(db, name)
        if customer is None:
            customers_not_found.append(name)
            continue

        for idx, spec in COLUMN_MAP.items():
            if idx >= len(row):
                continue
            parsed = _parse_cell(row[idx])
            if parsed is None:
                continue
            if parsed.kind == "error":
                parse_errors.append(f"{name} / {spec.row1_text}: {parsed.error}")
                continue

            key = tuple(spec.product_candidates)
            if key not in resolved_products:
                resolved_products[key] = _resolve_product(db, spec.product_candidates)
            product = resolved_products[key]
            if product is None:
                parse_errors.append(
                    f"{name} / {spec.row1_text}: none of {spec.product_candidates} found in product_and_services"
                )
                continue

            if spec.sheet_column_name is None:
                # Fixed: no sheet column.
                dup = (
                    db.query(CustomerProductAndService)
                    .filter(
                        CustomerProductAndService.customer_id == customer.id,
                        CustomerProductAndService.product_and_service_id == product.id,
                        CustomerProductAndService.sheet_column_id.is_(None),
                        CustomerProductAndService.center_id.is_(None),
                    )
                    .first()
                )
                if dup:
                    already_mapped.append(f"{name} / {product.name} (fixed)")
                    continue
                plans.append(_Plan(
                    customer_id=customer.id, customer_name=name,
                    product_id=product.id, product_name=product.name,
                    sheet_column_name=None, pricing_type=PricingType.fixed,
                    rate=parsed.rate, quantity=Decimal(1), tiers=[], description=parsed.note,
                ))
                continue

            sc = existing_sheet_columns.get(spec.sheet_column_name)
            if sc is None:
                missing_sheet_columns.add(spec.sheet_column_name)
            sc_id = sc.id if sc else None

            if sc_id is not None:
                dup = (
                    db.query(CustomerProductAndService)
                    .filter(
                        CustomerProductAndService.customer_id == customer.id,
                        CustomerProductAndService.product_and_service_id == product.id,
                        CustomerProductAndService.sheet_column_id == sc_id,
                        CustomerProductAndService.center_id.is_(None),
                    )
                    .first()
                )
                if dup:
                    already_mapped.append(f"{name} / {product.name} -> {spec.sheet_column_name}")
                    continue

            reusable = _find_reusable_row(db, customer.id, product.id)
            existing_row_id = reusable.id if reusable else None
            existing_pricing_type = reusable.pricing_type if reusable else None
            existing_rate = reusable.rate if reusable else None
            existing_tiers = _existing_tiers(reusable) if reusable else []

            if parsed.kind == "flat":
                plans.append(_Plan(
                    customer_id=customer.id, customer_name=name,
                    product_id=product.id, product_name=product.name,
                    sheet_column_name=spec.sheet_column_name, pricing_type=PricingType.flat,
                    rate=parsed.rate, quantity=None, tiers=[], description=parsed.note,
                    existing_row_id=existing_row_id, existing_pricing_type=existing_pricing_type,
                    existing_rate=existing_rate, existing_tiers=existing_tiers,
                ))
            else:  # slab
                plans.append(_Plan(
                    customer_id=customer.id, customer_name=name,
                    product_id=product.id, product_name=product.name,
                    sheet_column_name=spec.sheet_column_name, pricing_type=PricingType.slab,
                    rate=None, quantity=None, tiers=parsed.tiers, description=parsed.note,
                    existing_row_id=existing_row_id, existing_pricing_type=existing_pricing_type,
                    existing_rate=existing_rate, existing_tiers=existing_tiers,
                ))

    return plans, customers_not_found, missing_sheet_columns, already_mapped, parse_errors


@dataclass
class _Deletion:
    row_id: int
    customer_name: str
    product_name: str
    detail: str


def _column_products(db) -> dict[int, list[int]]:
    """product_and_service_id -> every COLUMN_MAP index that could target it
    (a product can be shared by more than one column, e.g. Complete Bookings
    via its bare column and its Online/Telephony split columns)."""
    result: dict[int, list[int]] = {}
    resolved: dict[tuple[str, ...], ProductAndService | None] = {}
    for idx, spec in COLUMN_MAP.items():
        key = tuple(spec.product_candidates)
        if key not in resolved:
            resolved[key] = _resolve_product(db, spec.product_candidates)
        product = resolved[key]
        if product is not None:
            result.setdefault(product.id, []).append(idx)
    return result


def _discover_deletions(db, csv_path: str) -> tuple[list[_Deletion], list[str]]:
    """Orphan rows (no sheet column) whose product is one of the pricing
    matrix's own products, where this customer's sheet has no value in ANY
    column that maps to that product — nothing in the current sheet justifies
    the row existing. Scoped strictly to COLUMN_MAP's products: a row for a
    product the matrix never covers at all is left alone, since there's no
    way to know whether "the sheet" has an opinion about it."""
    header0, header1, data_rows = _load_rows(csv_path)
    _sanity_check(header1)

    product_columns = _column_products(db)
    deletions: list[_Deletion] = []
    customers_not_found: list[str] = []

    for row in data_rows:
        name = (row[0] if row else "").strip()
        if not name:
            continue
        if name.lower().startswith(EXCLUDE_PREFIX):
            continue
        customer = _resolve_customer(db, name)
        if customer is None:
            customers_not_found.append(name)
            continue

        orphans = (
            db.query(CustomerProductAndService)
            .filter(
                CustomerProductAndService.customer_id == customer.id,
                CustomerProductAndService.sheet_column_id.is_(None),
                CustomerProductAndService.product_and_service_id.in_(product_columns.keys()),
            )
            .all()
        )
        for orphan in orphans:
            cols = product_columns.get(orphan.product_and_service_id, [])
            has_data = any(idx < len(row) and row[idx].strip() for idx in cols)
            if has_data:
                continue  # covered by the main create/update plan instead
            prod = db.get(ProductAndService, orphan.product_and_service_id)
            detail = _format_price(orphan.pricing_type, orphan.rate, _existing_tiers(orphan))
            deletions.append(_Deletion(
                row_id=orphan.id, customer_name=name,
                product_name=prod.name if prod else str(orphan.product_and_service_id),
                detail=detail,
            ))

    return deletions, customers_not_found


def _print_deletion_report(deletions: list[_Deletion], customers_not_found: list[str]) -> None:
    if customers_not_found:
        print(f"Customers in the CSV not found in the database ({len(customers_not_found)}):")
        for n in customers_not_found:
            print(f"  {n}")
        print()

    print(
        f"Orphan rows to delete ({len(deletions)}) — no sheet column, and this "
        f"customer's sheet has no value for this product in any of its columns:"
    )
    for d in deletions:
        print(f"  [row {d.row_id}] {d.customer_name} / {d.product_name}: {d.detail}")


def _apply_deletions(db, deletions: list[_Deletion]) -> None:
    deleted = 0
    for d in deletions:
        try:
            row = db.query(CustomerProductAndService).filter(CustomerProductAndService.id == d.row_id).first()
            if row is None or row.sheet_column_id is not None:
                continue  # already handled or gone since discovery
            db.delete(row)
            db.commit()
            deleted += 1
        except Exception as e:  # noqa: BLE001 — report and keep going, one row must not block the rest
            db.rollback()
            print(f"ERROR deleting {d.customer_name} / {d.product_name} (row {d.row_id}): {e}")
    print(f"Deleted {deleted} of {len(deletions)} orphan row(s).")


@dataclass
class _DriveDefaultsPlan:
    customers_to_flag: list[tuple[int, str]]           # (customer_id, customer_name) — add_attachment_in_mail False -> True
    centers_to_set: list[tuple[int, str, str]]          # (center_id, center_name, new drive_file_names)
    centers_conflict: list[tuple[str, str, str]]        # (center_name, existing value, target value) — left alone
    customers_not_found: list[str]


def _discover_drive_defaults(db, csv_path: str) -> _DriveDefaultsPlan:
    """For every customer matched by this pricing sheet (same scope as the
    main import — Strategic Care and not-found customers excluded): turn on
    Mail attachment, and set each of the customer's centres' Drive file
    name(s) to "{centre name}.xls" if it's currently blank. A centre that
    already has a DIFFERENT value set is never overwritten — it's reported as
    a conflict instead, since that value may have been set deliberately."""
    header0, header1, data_rows = _load_rows(csv_path)
    _sanity_check(header1)

    customers_to_flag: list[tuple[int, str]] = []
    centers_to_set: list[tuple[int, str, str]] = []
    centers_conflict: list[tuple[str, str, str]] = []
    customers_not_found: list[str] = []

    for row in data_rows:
        name = (row[0] if row else "").strip()
        if not name:
            continue
        if name.lower().startswith(EXCLUDE_PREFIX):
            continue
        customer = _resolve_customer(db, name)
        if customer is None:
            customers_not_found.append(name)
            continue

        if not customer.add_attachment_in_mail:
            customers_to_flag.append((customer.id, name))

        for ctr in db.query(Center).filter(Center.company_id == customer.id).all():
            target = f"{ctr.name}.xls"
            current = (ctr.drive_file_names or "").strip()
            if not current:
                centers_to_set.append((ctr.id, ctr.name, target))
            elif current != target:
                centers_conflict.append((ctr.name, current, target))

    return _DriveDefaultsPlan(customers_to_flag, centers_to_set, centers_conflict, customers_not_found)


def _print_drive_defaults_report(plan: _DriveDefaultsPlan) -> None:
    if plan.customers_not_found:
        print(f"Customers in the CSV not found in the database ({len(plan.customers_not_found)}):")
        for n in plan.customers_not_found:
            print(f"  {n}")
        print()

    print(f"Customers to turn Mail attachment ON ({len(plan.customers_to_flag)}):")
    for _cid, name in plan.customers_to_flag:
        print(f"  {name}")
    print()

    print(f"Centres to set Drive file name(s) on ({len(plan.centers_to_set)}):")
    for _ctr_id, ctr_name, target in plan.centers_to_set:
        print(f"  {ctr_name} -> {target}")
    print()

    if plan.centers_conflict:
        print(
            f"Centres already set to something else — left untouched, review by hand "
            f"({len(plan.centers_conflict)}):"
        )
        for ctr_name, current, target in plan.centers_conflict:
            print(f"  {ctr_name}: currently {current!r}, expected {target!r}")
        print()


def _apply_drive_defaults(db, plan: _DriveDefaultsPlan) -> None:
    flagged = 0
    for cid, name in plan.customers_to_flag:
        try:
            row = db.query(Customer).filter(Customer.id == cid).first()
            if row is None or row.add_attachment_in_mail:
                continue
            row.add_attachment_in_mail = True
            db.commit()
            flagged += 1
        except Exception as e:  # noqa: BLE001 — report and keep going, one row must not block the rest
            db.rollback()
            print(f"ERROR flagging {name}: {e}")
    print(f"Turned on Mail attachment for {flagged} of {len(plan.customers_to_flag)} customer(s).")

    set_count = 0
    for ctr_id, ctr_name, target in plan.centers_to_set:
        try:
            row = db.query(Center).filter(Center.id == ctr_id).first()
            if row is None or (row.drive_file_names or "").strip():
                continue  # already set by something else since discovery
            row.drive_file_names = target
            db.commit()
            set_count += 1
        except Exception as e:  # noqa: BLE001
            db.rollback()
            print(f"ERROR setting drive file name for {ctr_name}: {e}")
    print(f"Set Drive file name(s) for {set_count} of {len(plan.centers_to_set)} centre(s).")


def _rate_changed(p: _Plan) -> bool:
    """True comparison on the underlying Decimal/tier values, not their string
    formatting — Decimal("2.50") == Decimal("2.5000") is True in Python even
    though they'd print differently, and a naive string compare would wrongly
    flag that as a change. A pricing-type change (e.g. old row was flat, new
    one is slab) always counts as changed."""
    if p.existing_pricing_type != p.pricing_type:
        return True
    if p.pricing_type == PricingType.slab:
        return not _tiers_equal(p.existing_tiers, p.tiers)
    return p.existing_rate != p.rate


def _plan_detail(p: _Plan) -> str:
    price = _format_price(p.pricing_type, p.rate, p.tiers)
    if p.pricing_type == PricingType.fixed:
        return f"fixed qty {p.quantity} x ${p.rate}"
    return f"{price} via \"{p.sheet_column_name}\""


def _print_report(
    plans: list[_Plan], customers_not_found: list[str], missing_sheet_columns: set[str],
    already_mapped: list[str], parse_errors: list[str],
) -> None:
    new_rows = [p for p in plans if p.existing_row_id is None]
    reused_rows = [p for p in plans if p.existing_row_id is not None]
    changed_rate = [p for p in reused_rows if _rate_changed(p)]

    print(f"New rows to insert: {len(new_rows)}")
    print(f"Existing no-column rows to reuse (fill in the column): {len(reused_rows)}")
    print(f"  of those, the rate/tiers will also change: {len(changed_rate)}")
    by_type = {}
    for p in plans:
        by_type[p.pricing_type.value] = by_type.get(p.pricing_type.value, 0) + 1
    print(f"  by pricing type (all rows): {by_type}\n")

    if changed_rate:
        print(f"Reused rows whose rate/tiers will CHANGE ({len(changed_rate)}) — double check these:")
        for p in changed_rate:
            old_label = _format_price(p.existing_pricing_type, p.existing_rate, p.existing_tiers)
            new_label = _format_price(p.pricing_type, p.rate, p.tiers)
            print(f"  {p.customer_name} / {p.product_name}: {old_label} -> {new_label}")
        print()

    if missing_sheet_columns:
        print(f"New Sheet Column Catalog entries needed ({len(missing_sheet_columns)}):")
        for n in sorted(missing_sheet_columns):
            print(f"  {n}")
        print()

    print("Stray columns intentionally skipped (per instruction), not processed:")
    for idx, label in STRAY_COLUMNS.items():
        print(f"  column {idx}: {label}")
    print()

    if customers_not_found:
        print(f"Customers in the CSV not found in the database ({len(customers_not_found)}):")
        for n in customers_not_found:
            print(f"  {n}")
        print()

    if already_mapped:
        print(f"Already mapped, left untouched ({len(already_mapped)}):")
        for n in already_mapped:
            print(f"  {n}")
        print()

    if parse_errors:
        print(f"Could not parse / resolve ({len(parse_errors)}) — needs manual attention:")
        for n in parse_errors:
            print(f"  {n}")
        print()

    print(f"New rows ({len(new_rows)}):")
    for p in new_rows:
        desc = f" desc={p.description!r}" if p.description else ""
        print(f"  {p.customer_name} / {p.product_name}: {_plan_detail(p)}{desc}")

    print(f"\nReused rows — existing no-column row updated in place ({len(reused_rows)}):")
    for p in reused_rows:
        desc = f" desc={p.description!r}" if p.description else ""
        print(f"  {p.customer_name} / {p.product_name}: {_plan_detail(p)}{desc}")


def _apply(db, plans: list[_Plan], missing_sheet_columns: set[str]) -> None:
    created_columns: dict[str, SheetColumn] = {}
    for name in sorted(missing_sheet_columns):
        sc = SheetColumn(name=name)
        db.add(sc)
        created_columns[name] = sc
    db.commit()
    for sc in created_columns.values():
        db.refresh(sc)
    print(f"Created {len(created_columns)} new sheet column(s).")

    created = 0
    reused = 0
    for p in plans:
        try:
            sc_id = None
            if p.sheet_column_name is not None:
                sc_id = created_columns[p.sheet_column_name].id if p.sheet_column_name in created_columns else (
                    db.query(SheetColumn).filter(SheetColumn.name == p.sheet_column_name).first().id
                )

            if p.existing_row_id is not None:
                row = db.query(CustomerProductAndService).filter(
                    CustomerProductAndService.id == p.existing_row_id
                ).first()
                if row is None or row.sheet_column_id is not None:
                    # Reused between discover and apply (or already fixed by
                    # something else) — skip rather than clobber it.
                    continue
                row.pricing_type = p.pricing_type
                row.rate = p.rate
                row.quantity = p.quantity
                row.sheet_column_id = sc_id
                row.description = p.description
                for old_slab in list(row.slabs):
                    db.delete(old_slab)
                db.flush()
            else:
                row = CustomerProductAndService(
                    customer_id=p.customer_id,
                    product_and_service_id=p.product_id,
                    center_id=None,
                    pricing_type=p.pricing_type,
                    rate=p.rate,
                    quantity=p.quantity,
                    sheet_column_id=sc_id,
                    description=p.description,
                )
                db.add(row)
                db.flush()

            for t in p.tiers:
                db.add(CustomerProductAndServiceSlab(
                    customer_product_and_service_id=row.id,
                    range_start=t.start, range_end=t.end, rate=t.rate,
                ))
            db.commit()
            if p.existing_row_id is not None:
                reused += 1
            else:
                created += 1
        except Exception as e:  # noqa: BLE001 — report and keep going, one row must not block the rest
            db.rollback()
            print(f"ERROR applying {p.customer_name} / {p.product_name}: {e}")

    print(f"Created {created} new row(s), updated {reused} reused row(s), out of {len(plans)} planned.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_path", help="Path to the pricing matrix .xlsx (or a .csv export of it).")
    parser.add_argument("--apply", action="store_true", help="Write the changes (default: dry run).")
    parser.add_argument(
        "--delete-unused", action="store_true",
        help=(
            "Instead of the create/update plan, find and (with --apply) delete "
            "orphan rows whose product has no value anywhere in this customer's "
            "sheet row — run this AFTER a normal --apply so every row that "
            "genuinely has data has already been filled in first."
        ),
    )
    parser.add_argument(
        "--set-drive-defaults", action="store_true",
        help=(
            "Instead of the create/update plan, turn on Mail attachment for every "
            "customer in this sheet and set each of their centres' Drive file "
            "name(s) to \"{centre name}.xls\" (only where currently blank)."
        ),
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.delete_unused:
            deletions, customers_not_found = _discover_deletions(db, args.csv_path)
            _print_deletion_report(deletions, customers_not_found)
            if not args.apply:
                print("\nDry run only — no changes written. Re-run with --apply once this looks right.")
                return
            _apply_deletions(db, deletions)
            return

        if args.set_drive_defaults:
            drive_plan = _discover_drive_defaults(db, args.csv_path)
            _print_drive_defaults_report(drive_plan)
            if not args.apply:
                print("\nDry run only — no changes written. Re-run with --apply once this looks right.")
                return
            _apply_drive_defaults(db, drive_plan)
            return

        plans, customers_not_found, missing_sheet_columns, already_mapped, parse_errors = _discover(db, args.csv_path)
        _print_report(plans, customers_not_found, missing_sheet_columns, already_mapped, parse_errors)

        if not args.apply:
            print("\nDry run only — no changes written. Re-run with --apply once this looks right.")
            return

        _apply(db, plans, missing_sheet_columns)
    finally:
        db.close()


if __name__ == "__main__":
    main()
