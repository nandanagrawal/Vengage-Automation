from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_qbo_client, require_admin
from app.db.session import get_db
from app.models.customer import Customer, CustomerStatus
from app.models.user import User, UserRole
from app.schemas.customer import ApprovalAction, CustomerCreate, CustomerResponse, CustomerUpdate
from app.services.customer_service import create_customer_row, update_customer_row
from app.services.qbo_client import SupportsQuickBooks, customer_model_to_qbo_payload, qbo_time
from app.services.qbo_sync import ensure_qbo_credentials

router = APIRouter()


def _push_to_qbo(db: Session, row: Customer, qbo: SupportsQuickBooks) -> None:
    """Push a customer to QBO; sets qbo_id on the row. No-op if QBO not connected."""
    try:
        token, realm = ensure_qbo_credentials()
    except RuntimeError:
        return

    payload = customer_model_to_qbo_payload(row)

    if not row.qbo_id:
        created = qbo.create_customer(token, realm, payload)
        row.qbo_id = str(created.get("Id", ""))
        row.qbo_sync_token = str(created.get("SyncToken", "")) or None
        t = qbo_time(created)
        if t:
            row.qbo_last_updated = t
    else:
        updated = qbo.update_customer(token, realm, row.qbo_id, payload, row.qbo_sync_token)
        row.qbo_sync_token = str(updated.get("SyncToken", "")) or row.qbo_sync_token
        t = qbo_time(updated)
        if t:
            row.qbo_last_updated = t

    row.last_pushed_to_qbo_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    db.refresh(row)


@router.get("/customers", response_model=list[CustomerResponse])
def list_customers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Customer).order_by(Customer.display_name).all()


@router.post("/customers", response_model=CustomerResponse)
def post_customer(
    body: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    qbo: SupportsQuickBooks = Depends(get_qbo_client),
):
    row = create_customer_row(db, body, created_by_id=current_user.id)

    if current_user.role == UserRole.admin:
        # Admin → immediately approved, push to QBO
        row.status = CustomerStatus.approved
        row.approved_by_id = current_user.id
        db.add(row)
        db.commit()
        db.refresh(row)
        try:
            _push_to_qbo(db, row, qbo)
        except Exception:
            pass
    # Supervisor → status stays pending, no QBO push until admin approves

    db.refresh(row)
    return row


@router.get("/customers/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(Customer).filter(Customer.id == customer_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    return row


@router.patch("/customers/{customer_id}", response_model=CustomerResponse)
def patch_customer(
    customer_id: int,
    body: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    qbo: SupportsQuickBooks = Depends(get_qbo_client),
):
    row = db.query(Customer).filter(Customer.id == customer_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Supervisors can only edit customers they created; admins can edit any
    if current_user.role == UserRole.supervisor and row.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own customers")

    row = update_customer_row(db, row, body)

    # Only push changes to QBO if customer is already approved
    if row.status == CustomerStatus.approved:
        try:
            _push_to_qbo(db, row, qbo)
        except Exception:
            pass

    db.refresh(row)
    return row


@router.delete("/customers/{customer_id}", status_code=204)
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    row = db.query(Customer).filter(Customer.id == customer_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    db.delete(row)
    db.commit()


@router.post("/customers/{customer_id}/attachments")
async def upload_customer_attachments(
    customer_id: int,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    qbo: SupportsQuickBooks = Depends(get_qbo_client),
):
    row = db.query(Customer).filter(Customer.id == customer_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not row.qbo_id:
        raise HTTPException(
            status_code=422,
            detail="Customer has no QuickBooks ID yet. Approve the customer first so it exists in QBO.",
        )
    try:
        token, realm = ensure_qbo_credentials()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    uploaded: list[str] = []
    errors: list[str] = []
    for file in files:
        try:
            content = await file.read()
            ct = file.content_type or "application/octet-stream"
            fname = file.filename or "attachment"
            qbo.upload_attachment(token, realm, row.qbo_id, fname, ct, content)
            uploaded.append(fname)
        except Exception as exc:
            errors.append(f"{file.filename}: {exc}")

    return {"uploaded": uploaded, "errors": errors, "count": len(uploaded)}


@router.post("/customers/{customer_id}/approve", response_model=CustomerResponse)
def approve_customer(
    customer_id: int,
    body: ApprovalAction,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    qbo: SupportsQuickBooks = Depends(get_qbo_client),
):
    row = db.query(Customer).filter(Customer.id == customer_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    if row.status != CustomerStatus.pending:
        raise HTTPException(status_code=409, detail=f"Customer is already {row.status.value}")

    if body.action == "approve":
        row.status = CustomerStatus.approved
        row.approved_by_id = admin.id
        db.add(row)
        db.commit()
        db.refresh(row)
        try:
            _push_to_qbo(db, row, qbo)
        except Exception:
            pass
    else:
        row.status = CustomerStatus.rejected
        row.approved_by_id = admin.id
        db.add(row)
        db.commit()

    db.refresh(row)
    return row
