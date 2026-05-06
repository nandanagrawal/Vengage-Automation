from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_qbo_client
from app.db.session import get_db
from app.schemas.customer import SyncResult
from app.services.qbo_client import SupportsQuickBooks
from app.services.qbo_sync import ensure_qbo_credentials, run_quickbooks_sync

router = APIRouter()


@router.post("/sync/quickbooks", response_model=SyncResult)
def sync_quickbooks(
    db: Session = Depends(get_db),
    qbo: SupportsQuickBooks = Depends(get_qbo_client),
):
    try:
        ensure_qbo_credentials()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    try:
        return run_quickbooks_sync(db, qbo)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"QuickBooks sync failed: {e}") from e
