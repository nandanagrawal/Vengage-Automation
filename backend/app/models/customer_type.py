from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

customer_customer_types = Table(
    "customer_customer_types",
    Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("customer_id", ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
    Column("customer_type_id", ForeignKey("customer_types.id", ondelete="CASCADE"), nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
)


class CustomerType(Base):
    __tablename__ = "customer_types"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    customers: Mapped[list["Customer"]] = relationship(
        "Customer",
        secondary=customer_customer_types,
        back_populates="customer_types",
    )
