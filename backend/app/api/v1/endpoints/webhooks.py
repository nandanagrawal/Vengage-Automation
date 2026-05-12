from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_qbo_client
from app.core.config import settings
from app.db.session import get_db
from app.models.customer import Customer
from app.models.generated_invoice import GeneratedInvoice
from app.services.qbo_client import SupportsQuickBooks
from app.services.qbo_sync import upsert_customer_from_qbo_id
from app.services.qbo_tokens import get_valid_tokens_sync

router = APIRouter()


def _upsert_invoice_from_qbo(db: Session, qbo: SupportsQuickBooks, qbo_invoice_id: str) -> None:
    tokens = get_valid_tokens_sync()
    if not tokens:
        return

    try:
        inv = qbo.get_invoice(tokens.access_token, tokens.realm_id, qbo_invoice_id)
    except Exception:
        return

    if not inv:
        return

    customer_qbo_id = (inv.get("CustomerRef") or {}).get("value")
    customer_id: int | None = None
    if customer_qbo_id:
        cust = db.query(Customer).filter(Customer.qbo_id == customer_qbo_id).first()
        if cust:
            customer_id = cust.id

    email_status = inv.get("EmailStatus", "NotSet")
    send_status = "sent" if email_status == "EmailSent" else "pending"

    existing = (
        db.query(GeneratedInvoice)
        .filter(GeneratedInvoice.quickbooks_invoice_id == qbo_invoice_id)
        .first()
    )
    if existing:
        existing.invoice_number = inv.get("DocNumber")
        existing.total_amount = Decimal(str(inv.get("TotalAmt", 0)))
        existing.send_status = send_status
        existing.customer_id = customer_id
        db.add(existing)
    else:
        customer_name = (inv.get("CustomerRef") or {}).get("name", "")
        new_inv = GeneratedInvoice(
            invoice_upload_id=None,
            source="quickbooks",
            customer_id=customer_id,
            quickbooks_invoice_id=qbo_invoice_id,
            invoice_number=inv.get("DocNumber"),
            center_group_name=customer_name or "QBO",
            total_amount=Decimal(str(inv.get("TotalAmt", 0))),
            send_status=send_status,
        )
        db.add(new_inv)

    db.commit()


@router.post("/webhooks/intuit")
async def intuit_webhook(
    request: Request,
    db: Session = Depends(get_db),
    qbo: SupportsQuickBooks = Depends(get_qbo_client),
):
    """
    Intuit webhook receiver.
    - Customer create/update/merge → fetch & upsert customer locally.
    - Invoice create/update → fetch & upsert into generated_invoices with source="quickbooks".
    """
    verifier = settings.INTUIT_WEBHOOK_VERIFIER_TOKEN
    if verifier:
        sig = request.headers.get("intuit-signature") or request.headers.get("Intuit-Signature")
        if not sig or sig.strip() != verifier.strip():
            raise HTTPException(status_code=401, detail="Invalid webhook verification")

    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        payload = {}

    processed = 0
    for env in payload.get("eventNotifications") or []:
        entities = (env.get("dataChangeEvent") or {}).get("entities") or []
        for ent in entities:
            name = (ent.get("name") or "").lower()
            op = (ent.get("operation") or "").lower()
            eid = ent.get("id")
            if not eid:
                continue

            if name == "customer" and op in ("create", "update", "merge"):
                upsert_customer_from_qbo_id(db, qbo, str(eid))
                processed += 1
            elif name == "invoice" and op in ("create", "update"):
                _upsert_invoice_from_qbo(db, qbo, str(eid))
                processed += 1

    return {"ok": True, "processed": processed}
