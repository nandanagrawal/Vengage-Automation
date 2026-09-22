"""QuickBooks Item (Product/Service) — read-only mirror from QBO sync."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ProductAndService(Base):
    __tablename__ = "product_and_services"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    qbo_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    sync_token: Mapped[str | None] = mapped_column(String(16), nullable=True)

    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    sku: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    item_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fully_qualified_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    taxable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    purchase_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    purchase_desc: Mapped[str | None] = mapped_column(Text, nullable=True)

    track_qty_on_hand: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    qty_on_hand: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    inv_start_date: Mapped[str | None] = mapped_column(String(32), nullable=True)

    parent_qbo_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    parent_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    income_account_qbo_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    expense_account_qbo_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    asset_account_qbo_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    qbo_last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    customer_services: Mapped[list["CustomerProductAndService"]] = relationship(
        "CustomerProductAndService",
        back_populates="product_and_service",
        passive_deletes=True,
    )
