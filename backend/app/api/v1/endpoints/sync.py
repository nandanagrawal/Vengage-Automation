from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_qbo_client
from app.db.session import get_db
from app.models.user import User
from app.schemas.customer import SyncResult
from app.services.qbo_client import SupportsQuickBooks
from app.services.qbo_sync import (
    ensure_qbo_credentials,
    push_item_tax_codes,
    run_quickbooks_sync,
)

router = APIRouter()


@router.post("/sync/quickbooks", response_model=SyncResult)
def sync_quickbooks(
    db: Session = Depends(get_db),
    qbo: SupportsQuickBooks = Depends(get_qbo_client),
    _user: User = Depends(get_current_user),
):
    try:
        ensure_qbo_credentials()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    try:
        return run_quickbooks_sync(db, qbo)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"QuickBooks sync failed: {e}") from e


@router.post("/sync/push-item-tax-codes")
def sync_push_item_tax_codes(
    db: Session = Depends(get_db),
    qbo: SupportsQuickBooks = Depends(get_qbo_client),
    _user: User = Depends(get_current_user),
):
    """Set SalesTaxCodeRef = GST (10% Australian GST) on every product/service item in QBO."""
    try:
        ensure_qbo_credentials()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    try:
        return push_item_tax_codes(db, qbo)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to push item tax codes: {e}") from e


@router.get("/sync/tax-codes")
def get_tax_codes(
    qbo: SupportsQuickBooks = Depends(get_qbo_client),
    _user: User = Depends(get_current_user),
):
    """Return all TaxCode objects from QBO so you can find the correct code name."""
    try:
        token, realm = ensure_qbo_credentials()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    try:
        codes = qbo.query_tax_codes(token, realm)
        return [
            {
                "id": c.get("Id"),
                "name": c.get("Name"),
                "active": c.get("Active"),
                "taxable": c.get("Taxable"),
                "description": c.get("Description"),
            }
            for c in codes
        ]
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch tax codes: {e}") from e
