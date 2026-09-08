"""Admin-curated catalog of RAW Data-Imaging spreadsheet column headers.

Populated by hand (admin types/adds the exact header text seen in the sheet).
ProductColumnMapping references rows here rather than storing free text, so
the mapping UI can offer a dropdown and enforce "one column -> one product".
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SheetColumn(Base):
    __tablename__ = "sheet_columns"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Exact column header text as it appears in the RAW Data-Imaging sheet.
    name: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    product_mapping: Mapped["ProductColumnMapping | None"] = relationship(
        "ProductColumnMapping", back_populates="sheet_column", uselist=False
    )
