from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PricingType(str, enum.Enum):
    flat = "flat"     # single whole-number rate, taken straight from the sheet column
    slab = "slab"     # quantity distributed across one or more range tiers, each its own rate


class CustomerProductAndService(Base):
    __tablename__ = "customer_product_and_services"
    __table_args__ = (
        UniqueConstraint("customer_id", "product_and_service_id", name="uq_customer_product"),
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
    # Only meaningful when pricing_type == flat. Slab rows carry their rates on `slabs` instead.
    rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)

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
