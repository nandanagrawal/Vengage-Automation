import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_qbo_client, require_admin, get_db
from app.models.customer import Customer
from app.models.generated_invoice import GeneratedInvoice
from app.models.invoice_upload import InvoiceUpload
from app.models.user import User
from app.schemas.invoice_validation import (
    AttachmentPreviewRequest,
    GenerateRequest,
    PreviewResponse,
    RevalidateRequest,
    ValidationResponse,
)
from app.services.invoice_generation import (
    generate_invoices,
    generate_invoices_from_parsed,
)
from app.services.invoice_validation import (
    build_preview,
    generate_attachment_preview,
    revalidate,
    validate_file,
    _rows_to_parsed_file,
)
from app.services.qbo_client import SupportsQuickBooks
from app.services.qbo_tokens import get_valid_tokens_sync

router = APIRouter()

_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/invoice-uploads", status_code=200)
def upload_and_generate(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
    qbo: SupportsQuickBooks = Depends(get_qbo_client),
):
    filename = file.filename or "upload"
    if not any(filename.lower().endswith(ext) for ext in (".csv", ".xlsx", ".xls")):
        raise HTTPException(
            status_code=422,
            detail="Unsupported file type. Upload a .csv, .xlsx, or .xls file.",
        )

    content = file.file.read(_MAX_BYTES + 1)
    if len(content) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB).")

    tokens = get_valid_tokens_sync()
    if not tokens:
        raise HTTPException(
            status_code=503,
            detail="QuickBooks is not connected. Connect QBO before generating invoices.",
        )

    record = InvoiceUpload(
        file_name=filename,
        uploaded_by_id=user.id,
        status="processing",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    try:
        result = generate_invoices(
            db=db,
            qbo=qbo,
            access_token=tokens.access_token,
            realm_id=tokens.realm_id,
            filename=filename,
            content=content,
            invoice_upload_id=record.id,
        )
    except Exception as exc:
        record.status = "failed"
        record.errors_json = json.dumps([str(exc)])
        db.add(record)
        db.commit()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Determine final status
    if result.invoices_failed == 0:
        final_status = "completed"
    elif result.invoices_created == 0:
        final_status = "failed"
    else:
        final_status = "completed_with_errors"

    record.status = final_status
    record.total_invoices = result.invoices_created + result.invoices_failed
    record.success_count = result.invoices_created
    record.failed_count = result.invoices_failed
    record.errors_json = json.dumps(result.errors) if result.errors else None
    db.add(record)
    db.commit()

    return {"upload_id": record.id, "status": final_status, **result.to_dict()}


# ── Flat generated-invoice list ───────────────────────────────────────────────

@router.get("/generated-invoices")
def list_generated_invoices(
    customer_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    q = (
        db.query(GeneratedInvoice)
        .options(
            selectinload(GeneratedInvoice.centers),
            selectinload(GeneratedInvoice.line_items),
        )
        .order_by(GeneratedInvoice.id.desc())
    )
    if customer_id is not None:
        q = q.filter(GeneratedInvoice.customer_id == customer_id)

    total = q.count()
    rows = q.offset(offset).limit(limit).all()

    customer_ids = {r.customer_id for r in rows if r.customer_id}
    customers = db.query(Customer).filter(Customer.id.in_(customer_ids)).all()
    customer_names = {c.id: c.display_name for c in customers}

    return {
        "total": total,
        "items": [
            {
                "id": r.id,
                "invoice_number": r.invoice_number,
                "quickbooks_invoice_id": r.quickbooks_invoice_id,
                "customer_id": r.customer_id,
                "customer_name": customer_names.get(r.customer_id) if r.customer_id else None,
                "center_group_name": r.center_group_name,
                "total_amount": str(r.total_amount),
                "send_status": r.send_status,
                "source": r.source,
                "error_message": r.error_message,
                "created_at": r.created_at.isoformat(),
                "centers": [{"id": c.id, "center_name": c.center_name} for c in r.centers],
                "line_items": [
                    {
                        "id": li.id,
                        "product_name": li.product_name,
                        "quantity": str(li.quantity),
                        "rate": str(li.rate),
                        "amount": str(li.amount),
                    }
                    for li in r.line_items
                ],
            }
            for r in rows
        ],
    }


@router.get("/invoice-uploads")
def list_uploads(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    rows = (
        db.query(InvoiceUpload)
        .order_by(InvoiceUpload.id.desc())
        .limit(50)
        .all()
    )

    user_ids = [r.uploaded_by_id for r in rows if r.uploaded_by_id]
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    user_names = {u.id: (u.full_name or u.email) for u in users}

    return [
        {
            "id": r.id,
            "file_name": r.file_name,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
            "total_invoices": r.total_invoices,
            "success_count": r.success_count,
            "failed_count": r.failed_count,
            "uploaded_by": user_names.get(r.uploaded_by_id) if r.uploaded_by_id else None,
        }
        for r in rows
    ]


@router.get("/invoice-uploads/{upload_id}")
def get_upload_detail(
    upload_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    record = db.query(InvoiceUpload).filter(InvoiceUpload.id == upload_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Upload not found.")

    gen_invoices = (
        db.query(GeneratedInvoice)
        .options(
            selectinload(GeneratedInvoice.centers),
            selectinload(GeneratedInvoice.line_items),
        )
        .filter(GeneratedInvoice.invoice_upload_id == upload_id)
        .order_by(GeneratedInvoice.id)
        .all()
    )

    customer_ids = [gi.customer_id for gi in gen_invoices if gi.customer_id]
    customers = db.query(Customer).filter(Customer.id.in_(customer_ids)).all()
    customer_names = {c.id: c.display_name for c in customers}

    uploaded_by_name: str | None = None
    if record.uploaded_by_id:
        u = db.query(User).filter(User.id == record.uploaded_by_id).first()
        if u:
            uploaded_by_name = u.full_name or u.email

    invoices_data = [
        {
            "id": gi.id,
            "invoice_number": gi.invoice_number,
            "quickbooks_invoice_id": gi.quickbooks_invoice_id,
            "customer_name": customer_names.get(gi.customer_id) if gi.customer_id else None,
            "center_group_name": gi.center_group_name,
            "total_amount": str(gi.total_amount),
            "send_status": gi.send_status,
            "error_message": gi.error_message,
            "centers": [{"id": c.id, "center_name": c.center_name} for c in gi.centers],
            "line_items": [
                {
                    "id": li.id,
                    "product_name": li.product_name,
                    "quantity": str(li.quantity),
                    "rate": str(li.rate),
                    "amount": str(li.amount),
                }
                for li in gi.line_items
            ],
        }
        for gi in gen_invoices
    ]

    return {
        "id": record.id,
        "file_name": record.file_name,
        "status": record.status,
        "created_at": record.created_at.isoformat(),
        "total_invoices": record.total_invoices,
        "success_count": record.success_count,
        "failed_count": record.failed_count,
        "uploaded_by": uploaded_by_name,
        "errors": json.loads(record.errors_json) if record.errors_json else [],
        "generated_invoices": invoices_data,
    }


# ── New multi-step flow endpoints ─────────────────────────────────────────────

@router.post("/invoice-uploads/validate", response_model=ValidationResponse, status_code=200)
def validate_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    filename = file.filename or "upload"
    if not any(filename.lower().endswith(ext) for ext in (".csv", ".xlsx", ".xls")):
        raise HTTPException(status_code=422, detail="Unsupported file type.")
    content = file.file.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB).")
    try:
        return validate_file(filename, content, db)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/invoice-uploads/revalidate", response_model=ValidationResponse, status_code=200)
def revalidate_upload(
    body: RevalidateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    return revalidate(body, db)


@router.post("/invoice-uploads/preview", response_model=PreviewResponse, status_code=200)
def preview_upload(
    body: RevalidateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    return build_preview(body, db)


@router.post("/invoice-uploads/attachment-preview", status_code=200)
def attachment_preview(
    body: AttachmentPreviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        xlsx = generate_attachment_preview(body, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return Response(
        content=xlsx,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="Invoice_Preview.xlsx"'},
    )


@router.post("/invoice-uploads/generate", status_code=200)
def generate_from_validated(
    body: GenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
    qbo: SupportsQuickBooks = Depends(get_qbo_client),
):
    tokens = get_valid_tokens_sync()
    if not tokens:
        raise HTTPException(
            status_code=503,
            detail="QuickBooks is not connected. Connect QBO before generating invoices.",
        )

    parsed = _rows_to_parsed_file(body.rows, body.metric_columns)

    record = InvoiceUpload(
        file_name="validated-upload",
        uploaded_by_id=user.id,
        status="processing",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    try:
        result = generate_invoices_from_parsed(
            db=db,
            qbo=qbo,
            access_token=tokens.access_token,
            realm_id=tokens.realm_id,
            parsed=parsed,
            invoice_upload_id=record.id,
        )
    except Exception as exc:
        record.status = "failed"
        record.errors_json = json.dumps([str(exc)])
        db.add(record)
        db.commit()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    final_status = (
        "completed" if result.invoices_failed == 0
        else "failed" if result.invoices_created == 0
        else "completed_with_errors"
    )
    record.status = final_status
    record.total_invoices = result.invoices_created + result.invoices_failed
    record.success_count = result.invoices_created
    record.failed_count = result.invoices_failed
    record.errors_json = json.dumps(result.errors) if result.errors else None
    db.add(record)
    db.commit()

    return {"upload_id": record.id, "status": final_status, **result.to_dict()}
