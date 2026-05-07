from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.product_and_service import customer_product_and_services


class CustomerStatus(str, enum.Enum):
    pending = "pending"      # created by supervisor, awaiting admin approval
    approved = "approved"    # approved by admin — eligible for QBO push
    rejected = "rejected"    # rejected by admin


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Approval workflow
    status: Mapped[CustomerStatus] = mapped_column(
        Enum(CustomerStatus, name="customerstatus", native_enum=False),
        nullable=False,
        default=CustomerStatus.pending,
        index=True,
    )
    created_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # QuickBooks identity — canonical external key when synced
    qbo_id: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True, index=True)
    qbo_sync_token: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Name & contact (QBO-aligned)
    title: Mapped[str | None] = mapped_column(String(40), nullable=True)
    given_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    middle_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    family_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    suffix: Mapped[str | None] = mapped_column(String(16), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)

    primary_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    cc_email: Mapped[str | None] = mapped_column(String(500), nullable=True)
    bcc_email: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(40), nullable=True)
    fax: Mapped[str | None] = mapped_column(String(40), nullable=True)
    other_contact: Mapped[str | None] = mapped_column(String(500), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    print_on_check_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Billing address
    billing_line1: Mapped[str | None] = mapped_column(String(500), nullable=True)
    billing_line2: Mapped[str | None] = mapped_column(String(500), nullable=True)
    billing_line3: Mapped[str | None] = mapped_column(String(500), nullable=True)
    billing_line4: Mapped[str | None] = mapped_column(String(500), nullable=True)
    billing_city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    billing_state: Mapped[str | None] = mapped_column(String(255), nullable=True)
    billing_zip: Mapped[str | None] = mapped_column(String(30), nullable=True)
    billing_country: Mapped[str | None] = mapped_column(String(255), nullable=True)

    ship_same_as_billing: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    shipping_line1: Mapped[str | None] = mapped_column(String(500), nullable=True)
    shipping_line2: Mapped[str | None] = mapped_column(String(500), nullable=True)
    shipping_line3: Mapped[str | None] = mapped_column(String(500), nullable=True)
    shipping_line4: Mapped[str | None] = mapped_column(String(500), nullable=True)
    shipping_city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shipping_state: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shipping_zip: Mapped[str | None] = mapped_column(String(30), nullable=True)
    shipping_country: Mapped[str | None] = mapped_column(String(255), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # App-specific extensions
    rate: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    add_attachment_in_mail: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    last_pushed_to_qbo_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    qbo_last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    attachments: Mapped[list["CustomerAttachment"]] = relationship(
        "CustomerAttachment",
        back_populates="customer",
        cascade="all, delete-orphan",
    )

    product_and_services: Mapped[list["ProductAndService"]] = relationship(
        "ProductAndService",
        secondary=customer_product_and_services,
        back_populates="customers",
    )

    centers: Mapped[list["Center"]] = relationship(
        "Center",
        back_populates="company",
        cascade="all, delete-orphan",
    )

    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice",
        back_populates="company",
        cascade="all, delete-orphan",
    )
