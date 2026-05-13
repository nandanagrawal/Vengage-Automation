import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
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

_logger = logging.getLogger(__name__)

if not settings.INTUIT_WEBHOOK_VERIFIER_TOKEN:
    _logger.warning(
        "INTUIT_WEBHOOK_VERIFIER_TOKEN is not set — "
        "all Intuit webhook requests will be rejected until it is configured"
    )

router = APIRouter()


def _parse_qbo_datetime(value: str | None) -> datetime | None:
    """Parse a QBO ISO-8601 datetime string into a UTC-aware datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).astimezone(timezone.utc)
    except Exception:
        return None


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
    is_sent = email_status == "EmailSent"
    send_status = "sent" if is_sent else "pending"

    # QBO provides DeliveryInfo.DeliveryTime when the invoice email was delivered
    delivery_time_raw = ((inv.get("DeliveryInfo") or {}).get("DeliveryTime"))
    sent_at: datetime | None = _parse_qbo_datetime(delivery_time_raw) if is_sent else None

    existing = (
        db.query(GeneratedInvoice)
        .filter(GeneratedInvoice.quickbooks_invoice_id == qbo_invoice_id)
        .first()
    )
    if existing:
        existing.invoice_number = inv.get("DocNumber")
        existing.send_status = send_status
        # Only stamp sent_at the first time the invoice transitions to sent
        if is_sent and existing.sent_at is None:
            existing.sent_at = sent_at or datetime.now(timezone.utc)
        if existing.customer_id is None:
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
            sent_at=sent_at,
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
    if not verifier:
        raise HTTPException(
            status_code=503,
            detail="Webhook endpoint is disabled: INTUIT_WEBHOOK_VERIFIER_TOKEN is not configured.",
        )

    # Read raw body first — needed for HMAC verification AND JSON parsing.
    # Intuit signs the raw request body with HMAC-SHA256 using the verifier token as key,
    # then base64-encodes the digest and sends it as the intuit-signature header.
    raw_body = await request.body()

    sig = request.headers.get("intuit-signature") or request.headers.get("Intuit-Signature")
    if not sig:
        raise HTTPException(status_code=401, detail="Missing intuit-signature header")

    expected = base64.b64encode(
        hmac.new(verifier.encode("utf-8"), raw_body, hashlib.sha256).digest()
    ).decode("utf-8")

    if not hmac.compare_digest(sig.strip(), expected):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload: dict[str, Any] = json.loads(raw_body) if raw_body else {}
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
