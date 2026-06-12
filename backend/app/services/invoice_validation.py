"""Validation, preview, and helper logic for the new multi-step invoice upload flow."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session, selectinload

from app.models.center import Center
from app.models.customer import Customer
from app.models.customer_product_and_service import CustomerProductAndService
from app.models.invoice import Invoice
from app.schemas.invoice_validation import (
    CustomerError,
    PreviewCenter,
    PreviewCustomer,
    PreviewGroup,
    PreviewResponse,
    RevalidateRequest,
    ValidatedRow,
    ValidationResponse,
)
from app.services.invoice_generation import (
    ParsedFile,
    _build_line_items_for_center,
    _invoice_date,
    _month_label,
    parse_spreadsheet,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rows_to_parsed_file(rows: list[ValidatedRow], metric_columns: list[str]) -> ParsedFile:
    """Convert frontend ValidatedRow list back into a ParsedFile for invoice generation."""
    pf = ParsedFile(metric_columns=metric_columns)
    for row in rows:
        cid = row.center_id.strip()
        if not cid:
            continue
        name_lower = cid.lower()
        pf.center_display_names[name_lower] = cid
        pf.center_col1_names[name_lower] = row.center_name
        pf.center_prefixes[name_lower] = row.center_prefix.strip() or cid
        metrics_decimal: dict[str, Decimal] = {
            col.lower(): Decimal(str(row.metrics.get(col, 0.0)))
            for col in metric_columns
        }
        if name_lower in pf.rows:
            for k, v in metrics_decimal.items():
                pf.rows[name_lower][k] = pf.rows[name_lower].get(k, Decimal(0)) + v
        else:
            pf.rows[name_lower] = metrics_decimal
    return pf


def _run_validation(
    rows: list[ValidatedRow],
    metric_columns: list[str],
    db: Session,
) -> ValidationResponse:
    """Validate rows in-place; returns a fresh ValidationResponse."""
    center_ids_lower = [r.center_id.strip().lower() for r in rows if r.center_id.strip()]
    centers_in_db: list[Center] = (
        db.query(Center)
        .filter(sa_func.lower(Center.name).in_(center_ids_lower))
        .all()
    ) if center_ids_lower else []
    center_by_name: dict[str, Center] = {c.name.lower(): c for c in centers_in_db}

    customer_ids = {c.company_id for c in centers_in_db}
    customers: list[Customer] = (
        db.query(Customer)
        .filter(Customer.id.in_(customer_ids))
        .options(
            selectinload(Customer.customer_services)
            .selectinload(CustomerProductAndService.product_and_service),
        )
        .all()
    ) if customer_ids else []
    customer_by_id: dict[int, Customer] = {c.id: c for c in customers}

    seen: dict[str, int] = {}  # center_id_lower → first row_index
    for row in rows:
        row.errors = []
        row.matched = False
        row.customer_id = None
        row.customer_display_name = None

        cid = row.center_id.strip()
        if not cid:
            row.errors.append("Center ID is required.")
            continue

        cid_lower = cid.lower()
        if cid_lower in seen:
            row.errors.append(f"Duplicate center ID — also on row {seen[cid_lower] + 1}.")
        else:
            seen[cid_lower] = row.row_index

        ctr = center_by_name.get(cid_lower)
        if ctr is None:
            row.errors.append(f"Center '{cid}' not found in database.")
            continue

        row.matched = True
        cust = customer_by_id.get(ctr.company_id)
        if cust:
            row.customer_id = cust.id
            row.customer_display_name = cust.display_name

    # Customer-level checks
    customer_errors: list[CustomerError] = []
    for cust in customers:
        errs: list[str] = []
        if not cust.qbo_id:
            errs.append("No QBO ID — sync customer first.")
        if not cust.primary_email:
            errs.append("No primary email address.")
        active = [
            cs for cs in cust.customer_services
            if cs.product_and_service.active and cs.rate and cs.rate > 0
        ]
        if not active:
            errs.append("No active services with valid rates.")
        if errs:
            customer_errors.append(CustomerError(
                customer_display_name=cust.display_name,
                errors=errs,
            ))

    has_errors = any(r.errors for r in rows) or bool(customer_errors)
    return ValidationResponse(
        metric_columns=metric_columns,
        rows=rows,
        customer_errors=customer_errors,
        has_errors=has_errors,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def validate_file(filename: str, content: bytes, db: Session) -> ValidationResponse:
    parsed = parse_spreadsheet(filename, content)

    if not parsed.rows:
        return ValidationResponse(
            metric_columns=parsed.metric_columns,
            rows=[],
            customer_errors=[CustomerError(
                customer_display_name="",
                errors=["File contains no data rows."],
            )],
            has_errors=True,
        )

    rows: list[ValidatedRow] = [
        ValidatedRow(
            row_index=i,
            center_id=parsed.center_display_names.get(name_lower, name_lower),
            center_name=parsed.center_col1_names.get(name_lower, ""),
            center_prefix=parsed.center_prefixes.get(name_lower, name_lower),
            metrics={
                col: float(metrics.get(col.lower(), Decimal(0)))
                for col in parsed.metric_columns
            },
        )
        for i, (name_lower, metrics) in enumerate(parsed.rows.items())
    ]
    return _run_validation(rows, parsed.metric_columns, db)


def revalidate(body: RevalidateRequest, db: Session) -> ValidationResponse:
    rows = [r.model_copy(deep=True) for r in body.rows]
    return _run_validation(rows, body.metric_columns, db)


def build_preview(body: RevalidateRequest, db: Session) -> PreviewResponse:
    rows = body.rows
    metric_columns = body.metric_columns

    # Build center → customer mapping from DB
    center_ids_lower = [r.center_id.strip().lower() for r in rows if r.center_id.strip() and r.matched]
    if not center_ids_lower:
        return PreviewResponse(metric_columns=metric_columns, customers=[], warnings=["No matched centers."])

    centers_in_db: list[Center] = (
        db.query(Center)
        .filter(sa_func.lower(Center.name).in_(center_ids_lower))
        .all()
    )
    center_by_name: dict[str, Center] = {c.name.lower(): c for c in centers_in_db}

    customer_ids = {c.company_id for c in centers_in_db}
    customers: list[Customer] = (
        db.query(Customer)
        .filter(Customer.id.in_(customer_ids))
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

    # row.center_id (original case) → ValidatedRow
    row_by_center_id: dict[str, ValidatedRow] = {
        r.center_id.strip().lower(): r for r in rows if r.center_id.strip() and r.matched
    }

    warnings: list[str] = []
    preview_customers: list[PreviewCustomer] = []

    for company_id in sorted(customer_ids):
        cust = customer_by_id.get(company_id)
        if not cust:
            continue

        # Centers belonging to this customer that are in the validated rows
        cust_center_names_lower = [
            n for n in center_ids_lower
            if center_by_name.get(n) and center_by_name[n].company_id == company_id
        ]
        if not cust_center_names_lower:
            continue

        # Map center DB id → invoice group
        center_id_to_inv: dict[int, Invoice | None] = {
            center_by_name[n].id: None for n in cust_center_names_lower
        }
        for inv in invoices_by_company.get(company_id, []):
            for c in inv.centers:
                if c.id in center_id_to_inv:
                    center_id_to_inv[c.id] = inv

        group_map: dict[int | None, list[str]] = {}
        for name_lower in cust_center_names_lower:
            ctr = center_by_name[name_lower]
            inv = center_id_to_inv.get(ctr.id)
            key = inv.id if inv else None
            group_map.setdefault(key, []).append(name_lower)

        groups: list[PreviewGroup] = []
        for group_key, group_names_lower in group_map.items():
            centers_out: list[PreviewCenter] = []
            for name_lower in group_names_lower:
                row = row_by_center_id.get(name_lower)
                if row:
                    centers_out.append(PreviewCenter(
                        center_id=row.center_id,
                        center_name=row.center_name,
                        center_prefix=row.center_prefix,
                        metrics=row.metrics,
                    ))

            actual_names = [center_by_name[n].name for n in group_names_lower]
            label = (
                f"{actual_names[0]} (standalone)"
                if group_key is None and len(actual_names) == 1
                else " + ".join(actual_names)
            )
            groups.append(PreviewGroup(group_label=label, centers=centers_out))

        preview_customers.append(PreviewCustomer(
            customer_id=cust.id,
            display_name=cust.display_name,
            add_attachment_in_mail=cust.add_attachment_in_mail,
            primary_email=cust.primary_email,
            has_qbo_id=bool(cust.qbo_id),
            groups=groups,
        ))

    return PreviewResponse(
        metric_columns=metric_columns,
        customers=preview_customers,
        warnings=warnings,
    )


