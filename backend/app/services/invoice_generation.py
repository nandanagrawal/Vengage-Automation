"""Generate QBO invoices from an uploaded RAW Data-Imaging XLSX/XLS/CSV file.

New file format (RAW Data-Imaging sheet)
-----------------------------------------
Row 0   : header row — column names like "Confirmed Appointment (4)", etc.
Col 0   : S.No. / Center ID  — matched case-insensitively against Center.name
          in the database (e.g. "VNG-IMG-1-A").
Col 1   : Center Name        — human-readable label, ignored for processing.
Col 2   : Center Prefix      — may be comma-separated ("PAR, SMI-ALL"); the
          first token before any comma is used in ItemDescription.
Col 3+  : metric quantity columns

Center matching
---------------
The value in col 0 is matched case-insensitively against Center.name in the
database.  Rows whose col-0 value does not match any Center are skipped
(recorded in errors).

Product → column mapping
------------------------
PRODUCT_COLUMN_MAP maps each ProductAndService name (lower-case) to one or
more column-header substrings.  The line-item quantity is the sum of all
matching column values for that center's row.  Products whose name is in
FIXED_QUANTITY_PRODUCTS always receive quantity = 1.

Invoice grouping
----------------
Existing Invoice groupings define which centers produce one combined invoice.
Centers NOT in any grouping get one individual invoice each.

Critically: grouped centers each produce their OWN set of line items inside
the combined invoice (quantities are NOT summed across centers).

Invoice fields
--------------
  TxnDate / ServiceDate : last calendar day of the current month
  DueDate               : TxnDate + 15 days
  Memo (CustomerMemo)   : "{MMMYY} Invoice"  e.g. "MAR26 Invoice"
  Rate                  : CustomerProductAndService.rate  (per-customer, per-product)
  ItemDescription       : "{center_prefix} - {MMMYY} Invoice month {service_code}"
  0-quantity items      : included (amount = 0)
"""

from __future__ import annotations

import calendar
import csv
import io
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session, selectinload

from app.models.center import Center
from app.models.customer import Customer
from app.models.customer_product_and_service import CustomerProductAndService
from app.models.generated_invoice import (
    GeneratedInvoice,
    GeneratedInvoiceCenter,
    GeneratedInvoiceLineItem,
)
from app.models.invoice import Invoice
from app.models.product_and_service import ProductAndService
from app.core.config import settings
from app.services.qbo_client import SupportsQuickBooks


# ── Product → metric-column mapping ──────────────────────────────────────────
#
# Keys   : ProductAndService.name lowercased (partial or full match via `in`)
# Values : list of column-header substrings (lowercased); the quantity is the
#          sum of all columns whose lowercased header contains one of these substrings.
#
# Multi-column entries (e.g. Call Forwarding) are summed together.

PRODUCT_COLUMN_MAP: dict[str, list[str]] = {
    "olivia ai bookings for imaging workflow": ["confirmed appointment (4)"],
    "olivia ai - provisional bookings for imaging workflow": ["provisional appointment (5)"],
    "direct calls handling charges": ["direct call (6)"],
    "e-referral transmission charges": ["total e-referrals (11)"],
    "e-referral manual sms charges": ["e-referral manual sms count (13)"],
    "bookings via specialist portal": ["appointments (specialist) (15)"],
    "e-referral greeting sms charges": ["e-referral greeting sms count (12)"],
    "bookings directly done by customer team": ["appointments (operators) (14)"],
    "misc item": ["sms count (chat) (16)"],
    "e-referral portal monthly subscription fees": ["total e-referrals (11)"],
    "call forwarding - telephony charges": [
        "voice call forwarding bh (mins) (9)",
        "voice call forwarding ooh (mins) (10)",
    ],
    "olivia ai - walkin services call handling": ["walkin (7)"],
    "internal e-referral charges": ["total e-referrals (11)"],
    "external e-referral charges": ["e-referral greeting sms count (12)"],
    # Slab variants all source from Confirmed Appointment
    "olivia ai bookings for imaging workflow  (slab-1)": ["confirmed appointment (4)"],
    "olivia ai bookings for imaging workflow  (slab-2)": ["confirmed appointment (4)"],
    "olivia ai bookings for imaging workflow  (slab-3)": ["confirmed appointment (4)"],
}

# Products that always have quantity = 1 regardless of file data
FIXED_QUANTITY_PRODUCTS: frozenset[str] = frozenset({
    "kiosk monthly usage and support charges",
})


# ── Parsing ───────────────────────────────────────────────────────────────────

@dataclass
class ParsedFile:
    """center_name_lower (col 0) → {col_header_lower: Decimal quantity}"""
    rows: dict[str, dict[str, Decimal]] = field(default_factory=dict)
    # original-case column headers (col 3+ only)
    metric_columns: list[str] = field(default_factory=list)
    # center_name_lower → first token of col 2 (used in line-item descriptions)
    center_prefixes: dict[str, str] = field(default_factory=dict)
    # center_name_lower → original-case col 0 value
    center_display_names: dict[str, str] = field(default_factory=dict)
    # center_name_lower → col 1 value (Center Name column)
    center_col1_names: dict[str, str] = field(default_factory=dict)


def _to_decimal(value: Any) -> Decimal:
    if value is None or (isinstance(value, str) and not value.strip()):
        return Decimal("0")
    try:
        return Decimal(str(value).strip())
    except InvalidOperation:
        return Decimal("0")


def _extract_center_prefix(raw: Any) -> str:
    """Return the first comma-token of a Center Prefix cell, stripped."""
    text = str(raw).strip() if raw is not None else ""
    return text.split(",")[0].strip()


def _parse_raw_data_rows(
    headers: list[str],
    data_rows: list[list[Any]],
) -> ParsedFile:
    """Parse RAW Data-Imaging sheet.

    Expects:
      col 0 = Center ID / S.No.  → matched against Center.name in DB
      col 1 = Center Name        → ignored
      col 2 = Center Prefix      → first comma-token used in descriptions
      col 3+ = metric columns
    """
    if len(headers) < 3:
        raise ValueError("File must have at least 3 columns (S.No., Center Name, Center Prefix).")

    metric_headers = headers[3:]  # col 3 onwards
    result = ParsedFile(metric_columns=metric_headers)

    for row in data_rows:
        if not row or len(row) < 1:
            continue
        center_name = str(row[0]).strip() if row[0] is not None else ""
        if not center_name:
            continue

        center_name_lower = center_name.lower()
        # col 2 first token is used for line-item descriptions (fallback: center_name)
        desc_prefix = _extract_center_prefix(row[2]) if len(row) > 2 else ""
        if not desc_prefix:
            desc_prefix = center_name

        metrics: dict[str, Decimal] = {}
        for i, col_header in enumerate(metric_headers, start=3):
            raw_val = row[i] if i < len(row) else None
            metrics[col_header.lower()] = _to_decimal(raw_val)

        col1_name = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""

        # Accumulate if the same center appears on multiple rows
        if center_name_lower in result.rows:
            existing = result.rows[center_name_lower]
            for k, v in metrics.items():
                existing[k] = existing.get(k, Decimal("0")) + v
        else:
            result.rows[center_name_lower] = metrics
            result.center_prefixes[center_name_lower] = desc_prefix
            result.center_display_names[center_name_lower] = center_name
            result.center_col1_names[center_name_lower] = col1_name

    return result


def _load_xlsx_sheet(content: bytes, sheet_name: str = "RAW Data-Imaging") -> tuple[list[str], list[list[Any]]]:
    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError("openpyxl is required for .xlsx files.") from exc

    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    # Prefer the named sheet; fall back to active
    ws = wb[sheet_name] if sheet_name in wb.sheetnames else wb.active
    rows_raw = list(ws.iter_rows(values_only=True))
    if not rows_raw:
        raise ValueError("XLSX file is empty.")
    headers = [str(h).strip() if h is not None else "" for h in rows_raw[0]]
    return headers, [list(r) for r in rows_raw[1:]]


def parse_xlsx(content: bytes) -> ParsedFile:
    headers, data_rows = _load_xlsx_sheet(content)
    return _parse_raw_data_rows(headers, data_rows)


def parse_xls(content: bytes) -> ParsedFile:
    try:
        import xlrd
    except ImportError as exc:
        raise RuntimeError("xlrd is required for .xls files.") from exc

    wb = xlrd.open_workbook(file_contents=content)
    # Prefer "RAW Data-Imaging" sheet
    sheet_names = [wb.sheet_by_index(i).name for i in range(wb.nsheets)]
    idx = sheet_names.index("RAW Data-Imaging") if "RAW Data-Imaging" in sheet_names else 0
    ws = wb.sheet_by_index(idx)
    if ws.nrows == 0:
        raise ValueError("XLS file is empty.")
    headers = [str(ws.cell_value(0, c)).strip() for c in range(ws.ncols)]
    data_rows = [
        [ws.cell_value(r, c) for c in range(ws.ncols)]
        for r in range(1, ws.nrows)
    ]
    return _parse_raw_data_rows(headers, data_rows)


def parse_csv(content: bytes) -> ParsedFile:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise ValueError("CSV file is empty.")
    headers = [str(h).strip() for h in rows[0]]
    return _parse_raw_data_rows(headers, rows[1:])


def parse_spreadsheet(filename: str, content: bytes) -> ParsedFile:
    name_lower = filename.lower()
    if name_lower.endswith(".csv"):
        return parse_csv(content)
    elif name_lower.endswith(".xlsx"):
        return parse_xlsx(content)
    elif name_lower.endswith(".xls"):
        return parse_xls(content)
    raise ValueError(
        f"Unsupported file type '{filename}'. Upload a .csv, .xlsx, or .xls file."
    )


# ── Date helpers ──────────────────────────────────────────────────────────────

def _invoice_date() -> date:
    today = date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    return date(today.year, today.month, last_day)


def _due_date(inv_date: date) -> date:
    return inv_date + timedelta(days=15)


def _memo(inv_date: date) -> str:
    return inv_date.strftime("%b%y").upper() + " Invoice"


def _month_label(inv_date: date) -> str:
    """e.g. MAR26"""
    return inv_date.strftime("%b%y").upper()


# ── Quantity lookup ───────────────────────────────────────────────────────────

def _get_quantity(
    product_name_lower: str,
    center_metrics: dict[str, Decimal],
) -> Decimal | None:
    """Look up quantity for a product from a center's metric row.

    Returns None if there is no mapping at all (product should be skipped).
    Returns Decimal (possibly 0) when a mapping exists but has zero value.
    """
    if product_name_lower in FIXED_QUANTITY_PRODUCTS:
        return Decimal("1")

    col_substrings = PRODUCT_COLUMN_MAP.get(product_name_lower)
    if col_substrings:
        total = Decimal("0")
        for substr in col_substrings:
            for col_lower, val in center_metrics.items():
                if substr in col_lower:
                    total += val
        return total

    # Fallback: column header contains the product name as a substring.
    # Allows custom/future products and test data to work without an explicit entry.
    for col_lower, val in center_metrics.items():
        if product_name_lower in col_lower:
            return val

    return None  # no mapping → line item skipped


# ── Invoice generation ────────────────────────────────────────────────────────

@dataclass
class _LineItem:
    product_and_service_id: int | None
    product_name: str
    center_prefix: str
    description: str
    quantity: Decimal
    rate: Decimal
    amount: Decimal
    qbo_payload: dict[str, Any]


@dataclass
class InvoiceDetail:
    customer_display_name: str
    group_description: str
    qbo_invoice_id: str
    invoice_number: str | None
    sent_at: str | None
    send_status: str

    @property
    def sent(self) -> bool:
        return self.send_status == "sent"


@dataclass
class GenerationResult:
    total_center_rows: int = 0
    centers_matched: int = 0
    centers_skipped: int = 0
    invoices_created: int = 0
    invoices_failed: int = 0
    invoice_details: list[InvoiceDetail] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_center_rows": self.total_center_rows,
            "centers_matched": self.centers_matched,
            "centers_skipped": self.centers_skipped,
            "invoices_created": self.invoices_created,
            "invoices_failed": self.invoices_failed,
            "invoice_details": [
                {
                    "customer": d.customer_display_name,
                    "group": d.group_description,
                    "qbo_invoice_id": d.qbo_invoice_id,
                    "invoice_number": d.invoice_number,
                    "sent_at": d.sent_at,
                    "send_status": d.send_status,
                    "sent": d.sent,
                }
                for d in self.invoice_details
            ],
            "errors": self.errors,
        }


def _build_line_items_for_center(
    center_prefix: str,
    center_metrics: dict[str, Decimal],
    customer_services: list[CustomerProductAndService],
    month_label: str,
) -> list[_LineItem]:
    """Build one _LineItem per (customer service) for a single center."""
    items: list[_LineItem] = []
    for cs in customer_services:
        ps = cs.product_and_service
        rate = cs.rate
        if rate is None or rate <= 0:
            continue

        qty = _get_quantity(ps.name.lower(), center_metrics)
        if qty is None:
            continue  # product has no column mapping in this file format
        amount = (qty * rate).quantize(Decimal("0.01"))

        service_code = cs.service_code.code if cs.service_code else ""
        description = f"{center_prefix} - {month_label} Invoice month {service_code}".strip()

        qbo_payload: dict[str, Any] = {
            "DetailType": "SalesItemLineDetail",
            "Description": description,
            "Amount": float(amount),
            "SalesItemLineDetail": {
                "ItemRef": {"value": ps.qbo_id},
                "Qty": float(qty),
                "UnitPrice": float(rate),
                "TaxCodeRef": {"value": "TAX"},
            },
        }
        items.append(_LineItem(
            product_and_service_id=ps.id,
            product_name=ps.name,
            center_prefix=center_prefix,
            description=description,
            quantity=qty,
            rate=rate,
            amount=amount,
            qbo_payload=qbo_payload,
        ))
    return items


def _build_qbo_invoice_payload(
    customer: Customer,
    center_names: list[str],
    parsed: ParsedFile,
    center_by_name: dict[str, Center],
    customer_services: list[CustomerProductAndService],
    inv_date: date,
) -> tuple[dict[str, Any], Decimal, list[_LineItem]] | None:
    """Build the QBO invoice payload with per-center line items."""
    month_label = _month_label(inv_date)
    due = _due_date(inv_date)
    memo = _memo(inv_date)

    all_line_items: list[_LineItem] = []

    for name in center_names:
        ctr = center_by_name.get(name.lower())
        if ctr is None:
            continue
        name_lower = name.lower()
        # Metrics keyed by col-0 value (= Center.name lower)
        center_metrics = parsed.rows.get(name_lower, {})
        # Description prefix = first token of col-2; fall back to center name
        center_prefix = parsed.center_prefixes.get(name_lower, ctr.name)

        items = _build_line_items_for_center(
            center_prefix=center_prefix,
            center_metrics=center_metrics,
            customer_services=customer_services,
            month_label=month_label,
        )
        all_line_items.extend(items)

    if not all_line_items:
        return None

    total = sum(li.amount for li in all_line_items)

    payload: dict[str, Any] = {
        "CustomerRef": {"value": customer.qbo_id},
        "TxnDate": inv_date.isoformat(),
        "DueDate": due.isoformat(),
        "CustomerMemo": {"value": memo},
        "GlobalTaxCalculation": "TaxExcluded",
        "Line": [li.qbo_payload for li in all_line_items],
    }
    if settings.QBO_INVOICE_TEMPLATE_ID:
        payload["CustomForm"] = {"value": settings.QBO_INVOICE_TEMPLATE_ID}
    return payload, total, all_line_items


def generate_invoices_from_parsed(
    db: Session,
    qbo: SupportsQuickBooks,
    access_token: str,
    realm_id: str,
    parsed: ParsedFile,
    invoice_upload_id: int | None = None,
) -> GenerationResult:
    """Run invoice generation from a pre-built ParsedFile (skips file parsing)."""
    result = GenerationResult()

    if not parsed.rows:
        result.errors.append("File contains no data rows.")
        return result

    result.total_center_rows = len(parsed.rows)

    names_in_file = list(parsed.rows.keys())
    centers_in_db: list[Center] = (
        db.query(Center)
        .filter(sa_func.lower(Center.name).in_(names_in_file))
        .all()
    )
    center_by_name: dict[str, Center] = {c.name.lower(): c for c in centers_in_db}

    matched_names: list[str] = []
    for name_lower in names_in_file:
        if name_lower in center_by_name:
            matched_names.append(name_lower)
            result.centers_matched += 1
        else:
            result.centers_skipped += 1
            result.errors.append(f"Center '{name_lower}' not found in database — row skipped.")

    if not matched_names:
        result.errors.append("No centers in the file matched any center in the database.")
        return result

    customer_ids: set[int] = {center_by_name[n].company_id for n in matched_names}
    customers: list[Customer] = (
        db.query(Customer)
        .filter(Customer.id.in_(customer_ids))
        .options(
            selectinload(Customer.customer_services)
            .selectinload(CustomerProductAndService.product_and_service),
            selectinload(Customer.customer_services)
            .selectinload(CustomerProductAndService.service_code),
        )
        .all()
    )
    customer_by_id: dict[int, Customer] = {c.id: c for c in customers}

    invoices: list[Invoice] = (
        db.query(Invoice)
        .options(selectinload(Invoice.centers))
        .filter(Invoice.company_id.in_(customer_ids))
        .all()
    )
    invoices_by_company: dict[int, list[Invoice]] = {}
    for inv in invoices:
        invoices_by_company.setdefault(inv.company_id, []).append(inv)

    inv_date = _invoice_date()

    for company_id in customer_ids:
        customer = customer_by_id.get(company_id)
        if not customer:
            continue
        if not customer.qbo_id:
            result.errors.append(
                f"Customer '{customer.display_name}' has no QBO ID — skipped (sync first)."
            )
            continue

        customer_centers = [n for n in matched_names if center_by_name[n].company_id == company_id]
        if not customer_centers:
            continue

        active_services = [
            cs for cs in customer.customer_services
            if cs.product_and_service.active and cs.rate and cs.rate > 0
        ]
        if not active_services:
            result.errors.append(
                f"Customer '{customer.display_name}' has no active services with valid rates — skipped."
            )
            continue

        center_id_to_invoice: dict[int, Invoice | None] = {
            center_by_name[n].id: None for n in customer_centers
        }
        for inv in invoices_by_company.get(company_id, []):
            for c in inv.centers:
                if c.id in center_id_to_invoice:
                    center_id_to_invoice[c.id] = inv

        group_map: dict[int | None, list[str]] = {}
        for name_lower in customer_centers:
            ctr = center_by_name[name_lower]
            inv = center_id_to_invoice.get(ctr.id)
            key = inv.id if inv else None
            group_map.setdefault(key, []).append(name_lower)

        for group_key, group_name_lowers in group_map.items():
            group_center_names = [center_by_name[n].name for n in group_name_lowers]

            if group_key is None:
                for standalone_name in group_name_lowers:
                    ctr_name = center_by_name[standalone_name].name
                    _create_and_send(
                        db=db, qbo=qbo, access_token=access_token, realm_id=realm_id,
                        customer=customer, center_names=[ctr_name],
                        center_by_name=center_by_name, parsed=parsed,
                        customer_services=active_services, inv_date=inv_date,
                        result=result, is_standalone=True,
                        invoice_upload_id=invoice_upload_id,
                    )
            else:
                _create_and_send(
                    db=db, qbo=qbo, access_token=access_token, realm_id=realm_id,
                    customer=customer, center_names=group_center_names,
                    center_by_name=center_by_name, parsed=parsed,
                    customer_services=active_services, inv_date=inv_date,
                    result=result, is_standalone=False,
                    invoice_upload_id=invoice_upload_id,
                )

    return result


def generate_invoices(
    db: Session,
    qbo: SupportsQuickBooks,
    access_token: str,
    realm_id: str,
    filename: str,
    content: bytes,
    invoice_upload_id: int | None = None,
) -> GenerationResult:
    result = GenerationResult()

    # 1. Parse file
    parsed = parse_spreadsheet(filename, content)
    return generate_invoices_from_parsed(
        db=db, qbo=qbo, access_token=access_token, realm_id=realm_id,
        parsed=parsed, invoice_upload_id=invoice_upload_id,
    )


def _create_and_send(
    db: Session,
    qbo: SupportsQuickBooks,
    access_token: str,
    realm_id: str,
    customer: Customer,
    center_names: list[str],
    center_by_name: dict[str, Center],
    parsed: ParsedFile,
    customer_services: list[CustomerProductAndService],
    inv_date: date,
    result: GenerationResult,
    is_standalone: bool,
    invoice_upload_id: int | None = None,
) -> None:
    label = (
        f"{center_names[0]} (standalone)"
        if is_standalone
        else " + ".join(center_names)
    )
    built = _build_qbo_invoice_payload(
        customer=customer,
        center_names=center_names,
        parsed=parsed,
        center_by_name=center_by_name,
        customer_services=customer_services,
        inv_date=inv_date,
    )
    if built is None:
        result.errors.append(
            f"Customer '{customer.display_name}' / {label}: no line items — invoice skipped."
        )
        return

    payload, total_amount, line_items = built

    gen_inv: GeneratedInvoice | None = None
    if invoice_upload_id is not None:
        gen_inv = GeneratedInvoice(
            invoice_upload_id=invoice_upload_id,
            customer_id=customer.id,
            center_group_name=label,
            total_amount=total_amount,
            send_status="pending",
        )
        db.add(gen_inv)
        db.flush()

        for name in center_names:
            ctr = center_by_name.get(name.lower())
            db.add(GeneratedInvoiceCenter(
                generated_invoice_id=gen_inv.id,
                center_id=ctr.id if ctr else None,
                center_name=name,
            ))

        for li in line_items:
            db.add(GeneratedInvoiceLineItem(
                generated_invoice_id=gen_inv.id,
                product_and_service_id=li.product_and_service_id,
                product_name=li.product_name,
                description=li.description,
                quantity=li.quantity,
                rate=li.rate,
                amount=li.amount,
            ))

    try:
        qbo_inv = qbo.create_invoice(access_token, realm_id, payload)
        inv_id = str(qbo_inv.get("Id", ""))
        inv_number: str | None = qbo_inv.get("DocNumber")

        if gen_inv is not None:
            gen_inv.quickbooks_invoice_id = inv_id
            gen_inv.invoice_number = inv_number
            db.commit()  # Commit QBO ID immediately so any concurrent webhook sees this record

        if gen_inv is not None:
            gen_inv.send_status = "pending"

        result.invoices_created += 1
        result.invoice_details.append(
            InvoiceDetail(
                customer_display_name=customer.display_name,
                group_description=label,
                qbo_invoice_id=inv_id,
                invoice_number=inv_number,
                sent_at=None,
                send_status="pending",
            )
        )
    except Exception as err:
        if gen_inv is not None:
            gen_inv.send_status = "failed"
            gen_inv.error_message = str(err)
        result.invoices_failed += 1
        result.errors.append(
            f"Customer '{customer.display_name}' / {label}: failed to create invoice — {err}"
        )
