"""Admin-configured product → spreadsheet-column mapping.

Kept as its own table (not a column on ProductAndService) because
ProductAndService is a read-only mirror of QBO — qbo_sync fully overwrites
every synced field and hard-deletes rows no longer present in QBO. A mapping
here must survive syncs untouched, the same reasoning that keeps
CustomerProductAndService separate from Customer/ProductAndService.

References SheetColumn (a curated catalog, not free text) so the mapping UI
can offer a dropdown, and `sheet_column_id` is unique here so one column can
only ever be assigned to one product at a time.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ProductColumnMapping(Base):
    __tablename__ = "product_column_mappings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_and_service_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("product_and_services.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # One column can only be mapped to one product — enforced by this unique constraint.
    sheet_column_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("sheet_columns.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    product_and_service: Mapped["ProductAndService"] = relationship(
        "ProductAndService", back_populates="column_mapping"
    )
    sheet_column: Mapped["SheetColumn"] = relationship(
        "SheetColumn", back_populates="product_mapping"
    )
