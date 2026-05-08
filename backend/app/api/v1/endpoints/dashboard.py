from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.customer import Customer
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
