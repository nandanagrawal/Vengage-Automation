"""Company centers — each row belongs to a customer (company) record."""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

# Same extensions gdrive_client treats as spreadsheet-like (its _SPREADSHEET_EXT_RE).
_SPREADSHEET_EXT_RE = re.compile(r"\.(xlsx|xls)$", re.IGNORECASE)


class Center(Base):
    __tablename__ = "centers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)
    # Comma-separated exact Google Drive file name(s) for this centre, extension
    # included (e.g. "VNG-IMG-14-A.xlsx, VNG-IMG-14-A-B.xls") — looked up in the
    # Drive folder given at Validate time. See gdrive_client.match_exact_filenames.
    # A filename may itself contain a comma (e.g. "Matrix, Lalor.xlsx", a real
    # Australian suburb name) — drive_file_name_list() below only treats a
    # comma as a separator once it finds one after something that already
    # looks like a complete filename, so this doesn't get misparsed.
    drive_file_names: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    company: Mapped["Customer"] = relationship("Customer", back_populates="centers")

    def drive_file_name_list(self) -> list[str]:
        """Parsed, trimmed, non-empty entries from drive_file_names.

        Comma separates multiple filenames, but a single filename can
        legitimately contain a comma itself (e.g. "VNG-IMG-18-F-Matrix,
        Lalor.xlsx"). A naive split(",") would cut that in half, so instead:
        split on every comma, then glue adjacent pieces back together until
        the accumulated piece ends in a recognized spreadsheet extension —
        only then is it a complete filename and the next piece starts a new
        one. A piece with no extension at all (a genuine input mistake) ends
        up glued onto whatever follows rather than silently dropped.
        """
        if not self.drive_file_names:
            return []
        raw_parts = [p for p in self.drive_file_names.split(",")]
        if not raw_parts:
            return []

        result: list[str] = []
        current = raw_parts[0]
        for part in raw_parts[1:]:
            if _SPREADSHEET_EXT_RE.search(current.strip()):
                result.append(current.strip())
                current = part
            else:
                current = f"{current},{part}"
        if current.strip():
            result.append(current.strip())
        return [n for n in result if n]
