from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class InvoiceUpload(Base):
    __tablename__ = "invoice_uploads"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # processing | completed | completed_with_errors | failed
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    total_invoices: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failed_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # JSON array of non-per-invoice error strings (skipped centers, QBO config issues, etc.)
    errors_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # kept for backwards compat with migration 0002; no longer written
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    uploaded_by: Mapped["User"] = relationship("User")  # type: ignore[name-defined]
