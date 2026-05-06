from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class InvoiceEmailActivity(Base):
    """Read-only mirror of invoice email delivery rows synced from QuickBooks (last 30 days)."""

    __tablename__ = "invoice_email_activity"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    qbo_invoice_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    doc_number: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_qbo_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    customer_display_name: Mapped[str] = mapped_column(String(500), nullable=False)

    email_status: Mapped[str] = mapped_column(String(64), nullable=False)
    txn_date: Mapped[str | None] = mapped_column(String(32), nullable=True)

    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
