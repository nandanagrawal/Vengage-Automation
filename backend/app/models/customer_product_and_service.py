from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


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
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

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
