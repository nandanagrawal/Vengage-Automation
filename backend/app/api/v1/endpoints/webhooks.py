from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_qbo_client
from app.core.config import settings
from app.db.session import get_db
from app.services.qbo_client import SupportsQuickBooks
from app.services.qbo_sync import upsert_customer_from_qbo_id

router = APIRouter()


@router.post("/webhooks/intuit")
async def intuit_webhook(
    request: Request,
    db: Session = Depends(get_db),
    qbo: SupportsQuickBooks = Depends(get_qbo_client),
):
    """
    Intuit webhook receiver — on Customer Create / Merge, fetch entity and upsert locally.
    When INTUIT_WEBHOOK_VERIFIER_TOKEN is set, require the same value in header intuit-signature (dev placeholder).
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
            if name == "customer" and eid and op in ("create", "update", "merge"):
                upsert_customer_from_qbo_id(db, qbo, str(eid))
                processed += 1

    return {"ok": True, "processed": processed}
