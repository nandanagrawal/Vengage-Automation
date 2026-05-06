from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.customer import InvoiceActivityItem
from app.models.invoice_email_activity import InvoiceEmailActivity

router = APIRouter()


@router.get("/activity/recent-invoices", response_model=list[InvoiceActivityItem])
def recent_invoice_activity(db: Session = Depends(get_db)):
    rows = (
        db.query(InvoiceEmailActivity)
        .filter(InvoiceEmailActivity.email_status != "NotSet")
        .order_by(InvoiceEmailActivity.id.desc())
        .limit(50)
        .all()
    )
    return [
        InvoiceActivityItem(
            customer_display_name=r.customer_display_name,
            invoice_number=r.doc_number,
            email_status=r.email_status,
            txn_date=r.txn_date,
        )
        for r in rows
    ]
