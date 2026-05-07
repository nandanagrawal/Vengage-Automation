"""Generate QBO invoices from an uploaded XLS/XLSX/CSV file.

File format
-----------
- Row 0  : header row
- Col 0  : center name  (header label is irrelevant — always treated as center column)
- Col 1+ : product/service names — any column whose header matches a synced
           ProductAndService.name (case-insensitive) is treated as a quantity column.
           Columns that don't match any product are silently ignored.

Center matching is **case-insensitive** — rows whose center name does not match
any Center.name in the database (ignoring case) are skipped (recorded in errors).

Invoice grouping
----------------
The existing `invoices` table already holds center groupings for each customer.
- Centers in a grouping → one combined QBO invoice (quantities summed).
- Centers NOT in any grouping → one individual QBO invoice per center.

Rate comes exclusively from ProductAndService.unit_price (synced from QBO).
If unit_price is null or ≤ 0, the line item is skipped.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session, selectinload

from sqlalchemy import func as sa_func

from app.models.center import Center
from app.models.customer import Customer
from app.models.generated_invoice import (
    GeneratedInvoice,
    GeneratedInvoiceCenter,
    GeneratedInvoiceLineItem,
)
from app.models.invoice import Invoice
from app.models.product_and_service import ProductAndService
from app.services.qbo_client import SupportsQuickBooks


# ── Parsing ───────────────────────────────────────────────────────────────────

@dataclass
class ParsedFile:
    """First-column values → {product_col_name: quantity} for each data row."""
    # {center_name: {product_name_lower: Decimal}}
    rows: dict[str, dict[str, Decimal]] = field(default_factory=dict)
    # original casing of product column headers (as they appear in the file)
    product_columns: list[str] = field(default_factory=list)


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return Decimal("0")
    try:
        return Decimal(str(value).strip())
    except InvalidOperation:
        return None


def _parse_rows(headers: list[str], data_rows: list[list[Any]]) -> ParsedFile:
    if not headers:
        raise ValueError("File has no columns.")
    product_cols = headers[1:]  # everything after the center column
    result = ParsedFile(product_columns=product_cols)

    for row in data_rows:
        if not row:
            continue
        center_name = str(row[0]).strip() if row[0] is not None else ""
        if not center_name:
            continue
        quantities: dict[str, Decimal] = {}
        for i, col in enumerate(product_cols, start=1):
            raw = row[i] if i < len(row) else None
            qty = _to_decimal(raw)
            if qty is None:
                continue  # non-numeric → skip cell
            lower_col = col.lower()
            quantities[lower_col] = quantities.get(lower_col, Decimal("0")) + qty

        # Sum rows with duplicate center names
        if center_name in result.rows:
            existing = result.rows[center_name]
            for k, v in quantities.items():
                existing[k] = existing.get(k, Decimal("0")) + v
        else:
            result.rows[center_name] = quantities

    return result


def parse_csv(content: bytes) -> ParsedFile:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise ValueError("CSV file is empty.")
    headers = [str(h).strip() for h in rows[0]]
    return _parse_rows(headers, rows[1:])


def parse_xlsx(content: bytes) -> ParsedFile:
    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError("openpyxl is required for .xlsx files. Run: pip install openpyxl") from exc

    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    ws = wb.active
    rows_raw = list(ws.iter_rows(values_only=True))
    if not rows_raw:
        raise ValueError("XLSX file is empty.")
    headers = [str(h).strip() if h is not None else "" for h in rows_raw[0]]
    return _parse_rows(headers, [list(r) for r in rows_raw[1:]])


def parse_xls(content: bytes) -> ParsedFile:
    try:
        import xlrd
    except ImportError as exc:
        raise RuntimeError("xlrd is required for .xls files. Run: pip install xlrd") from exc

    wb = xlrd.open_workbook(file_contents=content)
    ws = wb.sheet_by_index(0)
    if ws.nrows == 0:
        raise ValueError("XLS file is empty.")
    headers = [str(ws.cell_value(0, c)).strip() for c in range(ws.ncols)]
    data_rows = [
        [ws.cell_value(r, c) for c in range(ws.ncols)]
        for r in range(1, ws.nrows)
    ]
    return _parse_rows(headers, data_rows)


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


# ── Generation ────────────────────────────────────────────────────────────────

@dataclass
class _LineItem:
    product_and_service_id: int | None
    product_name: str
    quantity: Decimal
    rate: Decimal
    amount: Decimal
    qbo_payload: dict[str, Any]


@dataclass
class InvoiceDetail:
    customer_display_name: str
    group_description: str      # e.g. "ac + acc" or "ad (standalone)"
    qbo_invoice_id: str
    invoice_number: str | None  # DocNumber from QBO
    total_amount: float
    send_status: str            # sent | failed | pending

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
                    "total_amount": d.total_amount,
                    "send_status": d.send_status,
                    "sent": d.sent,
                }
                for d in self.invoice_details
            ],
            "errors": self.errors,
        }


def _build_qbo_invoice_payload(
    customer: Customer,
    center_names: list[str],
    quantities_by_product_lower: dict[str, Decimal],
    products: list[ProductAndService],
) -> tuple[dict[str, Any], Decimal, list[_LineItem]] | None:
    """Build QBO invoice JSON payload. Returns (payload, total_amount, line_items) or None."""
    line_items: list[_LineItem] = []
    total = Decimal("0")

    for ps in products:
        rate = ps.unit_price
        if rate is None or rate <= 0:
            continue
        qty = quantities_by_product_lower.get(ps.name.lower(), Decimal("0"))
        if qty <= 0:
            continue
        amount = (qty * rate).quantize(Decimal("0.01"))
        total += amount
        qbo_payload: dict[str, Any] = {
            "DetailType": "SalesItemLineDetail",
            "Amount": float(amount),
            "SalesItemLineDetail": {
                "ItemRef": {"value": ps.qbo_id},
                "Qty": float(qty),
                "UnitPrice": float(rate),
            },
        }
        line_items.append(_LineItem(
            product_and_service_id=ps.id,
            product_name=ps.name,
            quantity=qty,
            rate=rate,
            amount=amount,
            qbo_payload=qbo_payload,
        ))

    if not line_items:
        return None

    memo = "Centers: " + ", ".join(center_names)
    payload: dict[str, Any] = {
        "CustomerRef": {"value": customer.qbo_id},
        "Line": [li.qbo_payload for li in line_items],
        "CustomerMemo": {"value": memo[:4000]},
    }
    return payload, total, line_items


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

    if not parsed.rows:
        result.errors.append("File contains no data rows.")
        return result

    if not parsed.product_columns:
        result.errors.append("File has only one column. At least one product/service column is required.")
        return result

    result.total_center_rows = len(parsed.rows)

    # 2. Load all centers by name (case-insensitive lookup)
    center_names_in_file = list(parsed.rows.keys())
    centers_in_db: list[Center] = (
        db.query(Center)
        .filter(sa_func.lower(Center.name).in_([n.lower() for n in center_names_in_file]))
        .all()
    )
    # keyed by lowercase name so lookups are case-insensitive
    center_by_name: dict[str, Center] = {c.name.lower(): c for c in centers_in_db}

    matched_names: list[str] = []
    for name in center_names_in_file:
        if name.lower() in center_by_name:
            matched_names.append(name)
            result.centers_matched += 1
        else:
            result.centers_skipped += 1
            result.errors.append(f"Center '{name}' not found in database — row skipped.")

    if not matched_names:
        result.errors.append("No center names in the file matched any center in the database.")
        return result

    # 3. Group matched centers by customer (company_id)
    customer_ids: set[int] = {center_by_name[n.lower()].company_id for n in matched_names}
    customers: list[Customer] = (
        db.query(Customer)
        .filter(Customer.id.in_(customer_ids))
        .options(selectinload(Customer.product_and_services))
        .all()
    )
    customer_by_id: dict[int, Customer] = {c.id: c for c in customers}

    # Load invoice groupings for all relevant customers
    invoices: list[Invoice] = (
        db.query(Invoice)
        .options(selectinload(Invoice.centers))
        .filter(Invoice.company_id.in_(customer_ids))
        .all()
    )
    # {company_id: [Invoice, ...]}
    invoices_by_company: dict[int, list[Invoice]] = {}
    for inv in invoices:
        invoices_by_company.setdefault(inv.company_id, []).append(inv)

    # 4. Load all product/service records (name → model)
    all_product_col_lowers = {col.lower() for col in parsed.product_columns}
    products_in_file: list[ProductAndService] = (
        db.query(ProductAndService)
        .filter(ProductAndService.active == True)  # noqa: E712
        .all()
    )
    # filter to only those whose name matches a column in the file
    product_lower_to_model: dict[str, ProductAndService] = {
        ps.name.lower(): ps
        for ps in products_in_file
        if ps.name.lower() in all_product_col_lowers
    }

    # 5. Generate invoices per customer
    for company_id in customer_ids:
        customer = customer_by_id.get(company_id)
        if not customer:
            continue
        if not customer.qbo_id:
            result.errors.append(
                f"Customer '{customer.display_name}' has no QBO ID — skipped (sync first)."
            )
            continue

        # Centers in the file that belong to this customer
        customer_centers_in_file = [
            n for n in matched_names if center_by_name[n.lower()].company_id == company_id
        ]
        if not customer_centers_in_file:
            continue

        # Customer's selected products that also appear in the file
        customer_products = [
            ps for ps in customer.product_and_services
            if ps.name.lower() in product_lower_to_model and ps.active
        ]
        if not customer_products:
            result.errors.append(
                f"Customer '{customer.display_name}' has no matching product/service columns in the file — skipped."
            )
            continue

        # Map center id → grouped invoice (or None = standalone)
        center_id_to_invoice: dict[int, Invoice | None] = {
            center_by_name[n.lower()].id: None for n in customer_centers_in_file
        }
        for inv in invoices_by_company.get(company_id, []):
            for c in inv.centers:
                if c.id in center_id_to_invoice:
                    center_id_to_invoice[c.id] = inv

        # Build groups: invoice_id (or None=standalone) → list of center names
        group_map: dict[int | None, list[str]] = {}
        for name in customer_centers_in_file:
            ctr = center_by_name[name.lower()]
            inv = center_id_to_invoice.get(ctr.id)
            key = inv.id if inv else None
            group_map.setdefault(key, []).append(name)

        for group_key, group_center_names in group_map.items():
            # Sum quantities across all centers in this group
            combined: dict[str, Decimal] = {}
            for name in group_center_names:
                for prod_lower, qty in parsed.rows[name].items():
                    combined[prod_lower] = combined.get(prod_lower, Decimal("0")) + qty

            if group_key is None:
                # Standalone centers — one invoice per center
                for standalone_name in group_center_names:
                    qty_map = parsed.rows[standalone_name]
                    _create_and_send(
                        db=db,
                        qbo=qbo,
                        access_token=access_token,
                        realm_id=realm_id,
                        customer=customer,
                        center_names=[standalone_name],
                        center_by_name=center_by_name,
                        quantities=qty_map,
                        products=customer_products,
                        result=result,
                        is_standalone=True,
                        invoice_upload_id=invoice_upload_id,
                    )
            else:
                # Grouped centers — one combined invoice
                _create_and_send(
                    db=db,
                    qbo=qbo,
                    access_token=access_token,
                    realm_id=realm_id,
                    customer=customer,
                    center_names=group_center_names,
                    center_by_name=center_by_name,
                    quantities=combined,
                    products=customer_products,
                    result=result,
                    is_standalone=False,
                    invoice_upload_id=invoice_upload_id,
                )

    return result


def _create_and_send(
    db: Session,
    qbo: SupportsQuickBooks,
    access_token: str,
    realm_id: str,
    customer: Customer,
    center_names: list[str],
    center_by_name: dict[str, Center],
    quantities: dict[str, Decimal],
    products: list[ProductAndService],
    result: GenerationResult,
    is_standalone: bool,
    invoice_upload_id: int | None = None,
) -> None:
    label = (
        f"{center_names[0]} (standalone)"
        if is_standalone
        else " + ".join(center_names)
    )
    built = _build_qbo_invoice_payload(customer, center_names, quantities, products)
    if built is None:
        result.errors.append(
            f"Customer '{customer.display_name}' / {label}: no line items with valid rate and non-zero quantity — invoice skipped."
        )
        return

    payload, total_amount, line_items = built

    # Create DB record upfront so failures are also persisted
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
        db.flush()  # populate gen_inv.id

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

        send_status = "failed"
        send_error: str | None = None
        try:
            qbo.send_invoice(access_token, realm_id, inv_id, customer.primary_email or None)
            send_status = "sent"
        except Exception as send_err:
            send_error = str(send_err)
            result.errors.append(f"Invoice {inv_id} created but failed to send: {send_err}")

        if gen_inv is not None:
            gen_inv.send_status = send_status
            gen_inv.error_message = send_error

        result.invoices_created += 1
        result.invoice_details.append(
            InvoiceDetail(
                customer_display_name=customer.display_name,
                group_description=label,
                qbo_invoice_id=inv_id,
                invoice_number=inv_number,
                total_amount=float(total_amount),
                send_status=send_status,
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
