from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class GeneratedInvoice(Base):
    __tablename__ = "generated_invoices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invoice_upload_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("invoice_uploads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    quickbooks_invoice_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    center_group_name: Mapped[str] = mapped_column(String(500), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    send_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    centers: Mapped[list["GeneratedInvoiceCenter"]] = relationship(
        "GeneratedInvoiceCenter", back_populates="invoice", cascade="all, delete-orphan"
    )
    line_items: Mapped[list["GeneratedInvoiceLineItem"]] = relationship(
        "GeneratedInvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan"
    )


class GeneratedInvoiceCenter(Base):
    __tablename__ = "generated_invoice_centers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    generated_invoice_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("generated_invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    center_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("centers.id", ondelete="SET NULL"), nullable=True
    )
    center_name: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    invoice: Mapped["GeneratedInvoice"] = relationship("GeneratedInvoice", back_populates="centers")


class GeneratedInvoiceLineItem(Base):
    __tablename__ = "generated_invoice_line_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    generated_invoice_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("generated_invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_and_service_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("product_and_services.id", ondelete="SET NULL"), nullable=True
    )
    product_name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    invoice: Mapped["GeneratedInvoice"] = relationship("GeneratedInvoice", back_populates="line_items")
