from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.customer import Customer
from app.models.generated_invoice import GeneratedInvoice
from app.models.invoice_email_activity import InvoiceEmailActivity
from app.models.invoice_upload import InvoiceUpload
from app.models.user import User

router = APIRouter()


class DashboardStats(BaseModel):
    total_customers: int
    imports_today: int
    invoices_sent: int
    delivery_failures: int
    pending_customers: int
    approved_customers: int


@router.get("/dashboard/stats", response_model=DashboardStats)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total_customers = db.query(func.count(Customer.id)).scalar() or 0
    pending_customers = (
        db.query(func.count(Customer.id))
        .filter(Customer.status == "pending")
        .scalar()
    ) or 0
    approved_customers = (
        db.query(func.count(Customer.id))
        .filter(Customer.status == "approved")
        .scalar()
    ) or 0

    # Imports today (UTC date)
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(
        tzinfo=timezone.utc
    )
    imports_today = (
        db.query(func.count(InvoiceUpload.id))
        .filter(InvoiceUpload.created_at >= today_start)
        .scalar()
    ) or 0

    # Invoices sent = EmailSent rows in the last 30-day QBO sync window
    invoices_sent = (
        db.query(func.count(InvoiceEmailActivity.id))
        .filter(InvoiceEmailActivity.email_status == "EmailSent")
        .scalar()
    ) or 0

    # Delivery failures = NeedToSend (queued but never delivered)
    delivery_failures = (
        db.query(func.count(InvoiceEmailActivity.id))
        .filter(InvoiceEmailActivity.email_status == "NeedToSend")
        .scalar()
    ) or 0

    return DashboardStats(
        total_customers=total_customers,
        imports_today=imports_today,
        invoices_sent=invoices_sent,
        delivery_failures=delivery_failures,
        pending_customers=pending_customers,
        approved_customers=approved_customers,
    )


class RecentInvoiceRow(BaseModel):
    id: int
    invoice_number: str | None
    customer_name: str | None
    group: str
    sent_at: str | None
    send_status: str
    file_name: str | None
    created_at: str | None


class PaginatedInvoices(BaseModel):
    total: int
    items: list[RecentInvoiceRow]


@router.get("/dashboard/recent-invoices", response_model=PaginatedInvoices)
def get_recent_invoices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = 1,
    page_size: int = 10,
    search: str = "",
):
    q = db.query(GeneratedInvoice)

    if search:
        term = f"%{search.strip()}%"
        customer_ids_matching = [
            c.id for c in db.query(Customer.id).filter(Customer.display_name.ilike(term)).all()
        ]
        upload_ids_matching = [
            u.id for u in db.query(InvoiceUpload.id).filter(InvoiceUpload.file_name.ilike(term)).all()
        ]
        from sqlalchemy import or_
        q = q.filter(
            or_(
                GeneratedInvoice.invoice_number.ilike(term),
                GeneratedInvoice.center_group_name.ilike(term),
                GeneratedInvoice.customer_id.in_(customer_ids_matching) if customer_ids_matching else False,
                GeneratedInvoice.invoice_upload_id.in_(upload_ids_matching) if upload_ids_matching else False,
            )
        )

    total = q.count()
    rows = (
        q.order_by(GeneratedInvoice.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    customer_ids = [r.customer_id for r in rows if r.customer_id]
    upload_ids = [r.invoice_upload_id for r in rows if r.invoice_upload_id]

    customers = {c.id: c.display_name for c in db.query(Customer).filter(Customer.id.in_(customer_ids)).all()} if customer_ids else {}
    uploads = {u.id: u.file_name for u in db.query(InvoiceUpload).filter(InvoiceUpload.id.in_(upload_ids)).all()} if upload_ids else {}

    return PaginatedInvoices(
        total=total,
        items=[
            RecentInvoiceRow(
                id=r.id,
                invoice_number=r.invoice_number,
                customer_name=customers.get(r.customer_id) if r.customer_id else None,
                group=r.center_group_name or "—",
                sent_at=r.sent_at.isoformat() if r.sent_at else None,
                send_status=r.send_status or "pending",
                file_name=uploads.get(r.invoice_upload_id) if r.invoice_upload_id else None,
                created_at=r.created_at.isoformat() if r.created_at else None,
            )
            for r in rows
        ],
    )
