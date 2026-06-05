"""Orchestrate QuickBooks pull/push and invoice email activity refresh."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.customer import Customer, CustomerStatus
from app.models.invoice_email_activity import InvoiceEmailActivity
from app.models.product_and_service import ProductAndService
from app.schemas.customer import SyncResult
from app.services.qbo_client import (
    QuickBooksClient,
    SupportsQuickBooks,
    apply_qbo_customer_to_model,
    apply_qbo_item_to_model,
    customer_model_to_qbo_payload,
    effective_local_time,
    qbo_time,
)
from app.services.qbo_tokens import get_valid_tokens_sync


def ensure_qbo_credentials() -> tuple[str, str]:
    stored = get_valid_tokens_sync()
    if stored and stored.access_token and stored.realm_id:
        return stored.access_token, stored.realm_id
    token = settings.QBO_ACCESS_TOKEN
    realm = settings.QBO_REALM_ID
    if token and realm:
        return token, realm
    raise RuntimeError(
        "QuickBooks not connected. Use OAuth (GET /api/v1/auth/qbo/connect) or set "
        "QBO_ACCESS_TOKEN and QBO_REALM_ID for manual tokens."
    )


def _sync_items_from_qbo(
    db: Session,
    client: SupportsQuickBooks,
    token: str,
    realm: str,
) -> tuple[int, int]:
    """Upsert all QBO Items; remove local rows whose qbo_id is not in the QBO result."""
    raw = client.query_items(token, realm)
    fetched_ids: set[str] = set()
    upserted = 0
    for qbo_item in raw:
        qid = str(qbo_item.get("Id", ""))
        if not qid:
            continue
        fetched_ids.add(qid)
        row = db.query(ProductAndService).filter(ProductAndService.qbo_id == qid).first()
        if row is None:
            row = ProductAndService(
                qbo_id=qid,
                name=qbo_item.get("Name") or "Item",
                active=bool(qbo_item.get("Active", True)),
            )
            db.add(row)
        apply_qbo_item_to_model(row, qbo_item)
        db.add(row)
        upserted += 1

        # Ensure each item has the correct tax code set in QBO
        current_tax = (qbo_item.get("SalesTaxCodeRef") or {}).get("value")
        if current_tax != settings.QBO_LINE_TAX_CODE and row.sync_token:
            try:
                client.update_item(token, realm, {
                    "sparse": True,
                    "Id": qid,
                    "SyncToken": row.sync_token,
                    "SalesTaxCodeRef": {"value": settings.QBO_LINE_TAX_CODE},
                })
            except Exception:
                pass  # non-fatal — invoice TaxCodeRef still overrides per-line

    db.commit()

    qdel = db.query(ProductAndService)
    if fetched_ids:
        qdel = qdel.filter(ProductAndService.qbo_id.notin_(fetched_ids))
    removed = 0
    for dead in qdel.all():
        db.delete(dead)
        removed += 1
    db.commit()
    return upserted, removed


def run_quickbooks_sync(db: Session, qbo: SupportsQuickBooks | None = None) -> SyncResult:
    client = qbo or QuickBooksClient()
    token, realm = ensure_qbo_credentials()

    pulled = pushed = created_remote = 0
    activity_rows = 0

    # ── Pull customers (QBO → app), last-write-wins vs local timestamps
    qbo_customers = client.query_customers(token, realm)
    for qc in qbo_customers:
        qid = str(qc.get("Id", ""))
        if not qid:
            continue
        qt = qbo_time(qc)
        row = db.query(Customer).filter(Customer.qbo_id == qid).first()
        if row is None:
            row = Customer(
                display_name=qc.get("DisplayName") or "Customer",
                status=CustomerStatus.approved,  # from QBO = already approved
                add_attachment_in_mail=False,
            )
            apply_qbo_customer_to_model(row, qc)
            row.qbo_sync_token = str(qc.get("SyncToken", "")) or None
            db.add(row)
            db.commit()
            db.refresh(row)
            pulled += 1
            continue

        local_eff = effective_local_time(row)
        if qt and qt > local_eff:
            attach = row.add_attachment_in_mail
            cc = row.cc_email
            bcc = row.bcc_email
            other = row.other_contact
            apply_qbo_customer_to_model(row, qc)
            row.add_attachment_in_mail = attach
            row.cc_email = cc
            row.bcc_email = bcc
            row.other_contact = other
            row.qbo_sync_token = str(qc.get("SyncToken", "")) or None
            db.add(row)
            db.commit()
            pulled += 1
        else:
            row.qbo_sync_token = str(qc.get("SyncToken", row.qbo_sync_token or "")) or row.qbo_sync_token
            db.add(row)
            db.commit()

    # ── Push local changes (app → QBO) — only approved customers
    for row in db.query(Customer).filter(Customer.status == CustomerStatus.approved).order_by(Customer.id).all():
        payload = customer_model_to_qbo_payload(row)

        if not row.qbo_id:
            created = client.create_customer(token, realm, payload)
            row.qbo_id = str(created.get("Id", ""))
            row.qbo_sync_token = str(created.get("SyncToken", "")) or None
            t = qbo_time(created)
            if t:
                row.qbo_last_updated = t
            row.last_pushed_to_qbo_at = datetime.now(timezone.utc)
            db.add(row)
            db.commit()
            created_remote += 1
            continue

        last_push = row.last_pushed_to_qbo_at
        if last_push is None:
            should_push = True
        else:
            if last_push.tzinfo is None:
                last_push = last_push.replace(tzinfo=timezone.utc)
            ua = row.updated_at
            if ua.tzinfo is None:
                ua = ua.replace(tzinfo=timezone.utc)
            should_push = ua > last_push

        if should_push:
            updated = client.update_customer(
                token,
                realm,
                row.qbo_id,
                payload,
                row.qbo_sync_token,
            )
            row.qbo_sync_token = str(updated.get("SyncToken", "")) or row.qbo_sync_token
            t = qbo_time(updated)
            if t:
                row.qbo_last_updated = t
            row.last_pushed_to_qbo_at = datetime.now(timezone.utc)
            db.add(row)
            db.commit()
            pushed += 1

    items_upserted, items_removed_local = _sync_items_from_qbo(db, client, token, realm)

    # ── Invoice email activity (last 30 days): replace snapshot
    since = date.today() - timedelta(days=30)
    invoices = client.query_invoice_email_rows(token, realm, since)
    db.query(InvoiceEmailActivity).delete()
    db.commit()

    for inv in invoices:
        cref = inv.get("CustomerRef") or {}
        db.add(
            InvoiceEmailActivity(
                qbo_invoice_id=str(inv.get("Id", "")),
                doc_number=str(inv.get("DocNumber", "")),
                customer_qbo_id=str(cref.get("value", "")) if cref.get("value") else None,
                customer_display_name=str(cref.get("name", "")) or "—",
                email_status=str(inv.get("EmailStatus", "NotSet")),
                txn_date=inv.get("TxnDate"),
            )
        )
        activity_rows += 1
    db.commit()

    return SyncResult(
        customers_pulled=pulled,
        customers_pushed=pushed,
        customers_created_remote=created_remote,
        invoice_activity_rows=activity_rows,
        items_upserted=items_upserted,
        items_removed_local=items_removed_local,
        message="Sync completed",
    )


def upsert_customer_from_qbo_id(db: Session, qbo: SupportsQuickBooks, customer_id: str) -> Customer | None:
    token, realm = ensure_qbo_credentials()
    qc = qbo.get_customer(token, realm, customer_id)
    if not qc or not qc.get("Id"):
        return None
    qid = str(qc["Id"])
    row = db.query(Customer).filter(Customer.qbo_id == qid).first()
    if row is None:
        row = Customer(
            display_name=qc.get("DisplayName") or "Customer",
            status=CustomerStatus.approved,  # from QBO = already approved
            add_attachment_in_mail=False,
        )
        db.add(row)
    attach = row.add_attachment_in_mail
    cc = row.cc_email
    bcc = row.bcc_email
    other = row.other_contact
    apply_qbo_customer_to_model(row, qc)
    row.add_attachment_in_mail = attach
    row.cc_email = cc
    row.bcc_email = bcc
    row.other_contact = other
    row.qbo_sync_token = str(qc.get("SyncToken", "")) or None
    db.commit()
    db.refresh(row)
    return row
