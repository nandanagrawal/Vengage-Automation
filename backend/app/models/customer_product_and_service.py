from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PricingType(str, enum.Enum):
    flat = "flat"     # single whole-number rate, taken straight from the sheet column
    slab = "slab"     # quantity distributed across one or more range tiers, each its own rate
    fixed = "fixed"   # no sheet column: a fixed quantity x rate added to every customer invoice run


class CustomerProductAndService(Base):
    __tablename__ = "customer_product_and_services"
    __table_args__ = (
        # The same product can now be mapped twice for one customer as long as it
        # reads its quantity from a different sheet column — only the exact same
        # (product, column) pair is rejected. Column mapping used to live globally
        # on ProductColumnMapping (one column -> one product, for everyone); it now
        # lives per customer-service row instead, see `sheet_column_id` below.
        UniqueConstraint(
            "customer_id", "product_and_service_id", "sheet_column_id",
            name="uq_customer_product_column",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_and_service_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("product_and_services.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pricing_type: Mapped[PricingType] = mapped_column(
        Enum(PricingType, name="pricingtype", native_enum=False),
        nullable=False,
        default=PricingType.flat,
        server_default=PricingType.flat.value,
    )
    # Used when pricing_type is flat or fixed. Slab rows carry their rates on `slabs` instead.
    rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    # Only meaningful when pricing_type == fixed: the quantity billed every run,
    # instead of one read from a sheet column.
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)

    # Which RAW Data-Imaging sheet column this row reads its quantity from — see
    # SheetColumn. Required by the API for flat/slab rows, and always NULL for
    # fixed rows (they don't read the sheet). Nullable at the DB level also for
    # the transitional backfill window (scripts/backfill_customer_service_columns.py).
    # A flat/slab row with no column produces no invoice line item, same as the
    # old unmapped-product behavior.
    sheet_column_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sheet_columns.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    # Free text, combined with the auto-generated "{Center} for {Mon YY}" text in
    # every QBO line-item description this row produces (and in the sheet
    # preview) — see _standard_desc/_slab_desc in invoice_generation.py.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    customer: Mapped["Customer"] = relationship("Customer", back_populates="customer_services")
    product_and_service: Mapped["ProductAndService"] = relationship(
        "ProductAndService", back_populates="customer_services"
    )
    sheet_column: Mapped["SheetColumn | None"] = relationship("SheetColumn")
    slabs: Mapped[list["CustomerProductAndServiceSlab"]] = relationship(
        "CustomerProductAndServiceSlab",
        back_populates="customer_product_and_service",
        cascade="all, delete-orphan",
        order_by="CustomerProductAndServiceSlab.range_start",
    )


class CustomerProductAndServiceSlab(Base):
    """One pricing tier of a slab-priced CustomerProductAndService.

    `range_end = None` means the tier is open-ended ("2501+"). Ranges are
    inclusive on both ends and must not overlap within the same
    CustomerProductAndService — enforced in app code, not the DB.
    """

    __tablename__ = "customer_product_and_service_slabs"
    __table_args__ = (
        UniqueConstraint(
            "customer_product_and_service_id", "range_start", name="uq_cps_slab_range_start"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_product_and_service_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("customer_product_and_services.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    range_start: Mapped[int] = mapped_column(Integer, nullable=False)
    range_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    customer_product_and_service: Mapped["CustomerProductAndService"] = relationship(
        "CustomerProductAndService", back_populates="slabs"
    )
