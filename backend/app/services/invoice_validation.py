"""Validation, preview, and helper logic for the new multi-step invoice upload flow."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session, selectinload

from app.models.center import Center
from app.models.customer import Customer
from app.models.customer_product_and_service import CustomerProductAndService, PricingType
from app.models.invoice import Invoice
from app.schemas.invoice_validation import (
    CustomerError,
    InputQuantityEntry,
    InputRequirement,
    PreviewCenter,
    PreviewCustomer,
    PreviewGroup,
    PreviewResponse,
    RevalidateRequest,
    ValidatedRow,
    ValidationResponse,
)
from app.services import gdrive_client
from app.services.invoice_generation import (
    ParsedFile,
    _build_line_items_for_center,
    _has_valid_pricing,
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
    drive_folder_url: str | None = None,
    input_quantities: list[InputQuantityEntry] | None = None,
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
            selectinload(Customer.customer_services)
            .selectinload(CustomerProductAndService.slabs),
            selectinload(Customer.customer_services)
            .selectinload(CustomerProductAndService.sheet_column),
            selectinload(Customer.customer_services)
            .selectinload(CustomerProductAndService.center),
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

    centers_by_customer: dict[int, list[Center]] = {}
    for c in centers_in_db:
        centers_by_customer.setdefault(c.company_id, []).append(c)

    customer_errors_by_id: dict[int, list[str]] = {}

    def _add_customer_error(cust_id: int, msg: str) -> None:
        customer_errors_by_id.setdefault(cust_id, []).append(msg)

    # Customer-level checks, plus collect Input rows still needing a quantity
    input_qty_by_cps_id = {
        e.customer_product_and_service_id: e.quantity for e in (input_quantities or [])
    }
    input_requirements: list[InputRequirement] = []

    for cust in customers:
        if not cust.qbo_id:
            _add_customer_error(cust.id, "No QBO ID — sync customer first.")
        if not cust.primary_email:
            _add_customer_error(cust.id, "No primary email address.")
        active = [
            cs for cs in cust.customer_services
            if cs.product_and_service.active and _has_valid_pricing(cs)
        ]
        if not active:
            _add_customer_error(cust.id, "No active services with valid rates.")

        matched_center_ids = {c.id for c in centers_by_customer.get(cust.id, [])}
        for cs in active:
            if cs.pricing_type != PricingType.input:
                continue
            # Customer-wide (center_id is None) rows always apply; centre-scoped
            # ones only if that centre is actually in this batch.
            if cs.center_id is not None and cs.center_id not in matched_center_ids:
                continue
            supplied = input_qty_by_cps_id.get(cs.id)
            if supplied is not None and supplied > 0:
                continue
            input_requirements.append(InputRequirement(
                customer_product_and_service_id=cs.id,
                customer_id=cust.id,
                customer_display_name=cust.display_name,
                product_name=cs.product_and_service.name,
                description=cs.description,
                center_id=cs.center_id,
                center_name=cs.center.name if cs.center else None,
            ))

    # Drive attachment check — blocking, not the old Preview-stage warning.
    # Requires BOTH: the customer has Mail attachment on, AND the centre has
    # a Drive file name configured. Either one being off/blank means that
    # centre is never looked up — Mail attachment off suppresses the check
    # entirely for that customer, even if a centre still has a name set.
    customers_needing_drive = [
        cust
        for cust in customers
        if cust.add_attachment_in_mail
        and any(ctr.drive_file_name_list() for ctr in centers_by_customer.get(cust.id, []))
    ]
    if customers_needing_drive:
        all_wanted: list[str] = [
            name
            for cust in customers_needing_drive
            for ctr in centers_by_customer.get(cust.id, [])
            for name in ctr.drive_file_name_list()
        ]
        drive_files: dict[str, dict] | None = None
        drive_error: str | None = None
        if not drive_folder_url:
            drive_error = "A centre requires a Drive attachment but no Drive folder link was provided."
        else:
            try:
                folder_id = gdrive_client.extract_folder_id(drive_folder_url)
                drive_files = gdrive_client.match_exact_filenames(folder_id, all_wanted)
            except Exception as e:  # noqa: BLE001 — surfaced per-customer below, not raised
                drive_error = f"Could not read Drive folder: {e}"

        for cust in customers_needing_drive:
            if drive_error:
                _add_customer_error(cust.id, drive_error)
                continue
            for ctr in centers_by_customer.get(cust.id, []):
                for name in ctr.drive_file_name_list():
                    if name.lower() not in (drive_files or {}):
                        _add_customer_error(cust.id, f"Centre '{ctr.name}': Drive file '{name}' not found.")

    customer_errors = [
        CustomerError(customer_display_name=customer_by_id[cid].display_name, errors=errs)
        for cid, errs in customer_errors_by_id.items()
    ]

    has_errors = any(r.errors for r in rows) or bool(customer_errors)
    return ValidationResponse(
        metric_columns=metric_columns,
        rows=rows,
        customer_errors=customer_errors,
        has_errors=has_errors,
        input_requirements=input_requirements,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def validate_file(
    filename: str, content: bytes, db: Session, drive_folder_url: str | None = None,
) -> ValidationResponse:
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
    return _run_validation(rows, parsed.metric_columns, db, drive_folder_url=drive_folder_url)


def revalidate(body: RevalidateRequest, db: Session) -> ValidationResponse:
    rows = [r.model_copy(deep=True) for r in body.rows]
    return _run_validation(
        rows, body.metric_columns, db,
        drive_folder_url=body.drive_folder_url,
        input_quantities=body.input_quantities,
    )


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


