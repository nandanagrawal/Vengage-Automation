from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_qbo_client, require_admin
from app.db.session import get_db
from app.models.customer import Customer, CustomerStatus
from app.models.customer_attachment import CustomerAttachment
from app.models.customer_type import CustomerType
from app.models.user import User, UserRole
from app.schemas.customer import (
    ApprovalAction,
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
    customer_response_from_row,
)
from app.schemas.customer_attachment import CustomerAttachmentResponse, UploadAttachmentsResult
from app.services.customer_attachment_storage import (
    delete_stored_file,
    full_path_for_relpath,
    new_storage_relpath,
    parse_qbo_attachable_id,
    write_bytes_atomic,
)
from app.services.customer_service import create_customer_row, update_customer_row
from app.services.qbo_client import SupportsQuickBooks, customer_model_to_qbo_payload, qbo_time
from app.services.qbo_sync import ensure_qbo_credentials

router = APIRouter()


def _get_customer_or_404(db: Session, customer_id: int) -> Customer:
    row = (
        db.query(Customer)
        .options(
            selectinload(Customer.customer_services),
            selectinload(Customer.customer_types),
        )
        .filter(Customer.id == customer_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    return row


def _require_can_access_customer_attachments(user: User, row: Customer) -> None:
    if user.role == UserRole.admin:
        return
    if user.role == UserRole.supervisor and row.created_by_id == user.id:
        return
    raise HTTPException(
        status_code=403,
        detail="You can only access attachments for customers you created",
    )


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
    rows = (
        db.query(Customer)
        .options(
            selectinload(Customer.customer_services),
            selectinload(Customer.customer_types),
        )
        .order_by(Customer.display_name)
        .all()
    )
    return [customer_response_from_row(r) for r in rows]


@router.post("/customers", response_model=CustomerResponse)
def post_customer(
    body: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    qbo: SupportsQuickBooks = Depends(get_qbo_client),
):
    try:
        row = create_customer_row(db, body, created_by_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

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

    row = _get_customer_or_404(db, row.id)
    return customer_response_from_row(row)


@router.get("/customers/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = _get_customer_or_404(db, customer_id)
    return customer_response_from_row(row)


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

    try:
        row = update_customer_row(db, row, body)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    # Only push changes to QBO if customer is already approved
    if row.status == CustomerStatus.approved:
        try:
            _push_to_qbo(db, row, qbo)
        except Exception:
            pass

    row = _get_customer_or_404(db, customer_id)
    return customer_response_from_row(row)


@router.delete("/customers/{customer_id}", status_code=204)
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    row = _get_customer_or_404(db, customer_id)
    for att in db.query(CustomerAttachment).filter(CustomerAttachment.customer_id == customer_id).all():
        delete_stored_file(att.storage_relpath)
    db.delete(row)
    db.commit()


@router.get("/customers/{customer_id}/attachments", response_model=list[CustomerAttachmentResponse])
def list_customer_attachments(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = _get_customer_or_404(db, customer_id)
    _require_can_access_customer_attachments(current_user, row)
    return (
        db.query(CustomerAttachment)
        .filter(CustomerAttachment.customer_id == customer_id)
        .order_by(CustomerAttachment.created_at.desc())
        .all()
    )


@router.get("/customers/{customer_id}/attachments/{attachment_id}/file")
def download_customer_attachment(
    customer_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = _get_customer_or_404(db, customer_id)
    _require_can_access_customer_attachments(current_user, row)
    att = (
        db.query(CustomerAttachment)
        .filter(
            CustomerAttachment.id == attachment_id,
            CustomerAttachment.customer_id == customer_id,
        )
        .first()
    )
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = full_path_for_relpath(att.storage_relpath)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File missing on server")
    return FileResponse(
        path,
        media_type=att.content_type,
        filename=att.original_filename,
    )


@router.post("/customers/{customer_id}/attachments", response_model=UploadAttachmentsResult)
async def upload_customer_attachments(
    customer_id: int,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    qbo: SupportsQuickBooks = Depends(get_qbo_client),
):
    row = _get_customer_or_404(db, customer_id)
    _require_can_access_customer_attachments(current_user, row)
    if not row.qbo_id:
        raise HTTPException(
            status_code=422,
            detail="Customer has no QuickBooks ID yet. Approve the customer first so it exists in QBO.",
        )
    try:
        token, realm = ensure_qbo_credentials()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    saved: list[CustomerAttachmentResponse] = []
    errors: list[str] = []
    for file in files:
        relpath: str | None = None
        try:
            content = await file.read()
            ct = file.content_type or "application/octet-stream"
            fname = file.filename or "attachment"
            qbo_result = qbo.upload_attachment(token, realm, row.qbo_id, fname, ct, content)
            qbo_aid = parse_qbo_attachable_id(qbo_result)
            relpath = new_storage_relpath(row.id, fname)
            write_bytes_atomic(relpath, content)
            att = CustomerAttachment(
                customer_id=row.id,
                original_filename=fname,
                content_type=ct,
                size_bytes=len(content),
                storage_relpath=relpath,
                qbo_attachable_id=qbo_aid,
            )
            db.add(att)
            db.commit()
            db.refresh(att)
            saved.append(CustomerAttachmentResponse.model_validate(att))
        except Exception as exc:
            db.rollback()
            if relpath:
                delete_stored_file(relpath)
            errors.append(f"{file.filename}: {exc}")

    return UploadAttachmentsResult(attachments=saved, errors=errors)


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
    return customer_response_from_row(_get_customer_or_404(db, customer_id))
