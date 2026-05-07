"""App-managed invoices: group one or more centers for generation (not QuickBooks rows)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

invoice_centers = Table(
    "invoice_centers",
    Base.metadata,
    Column("invoice_id", ForeignKey("invoices.id", ondelete="CASCADE"), primary_key=True),
    Column("center_id", ForeignKey("centers.id", ondelete="CASCADE"), primary_key=True),
)


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    company: Mapped["Customer"] = relationship("Customer", back_populates="invoices")
    centers: Mapped[list["Center"]] = relationship(
        "Center",
        secondary=invoice_centers,
    )
