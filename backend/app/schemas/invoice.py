from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from app.models.invoice import Invoice


class InvoiceCreate(BaseModel):
    company_id: int = Field(..., ge=1)
    center_ids: list[int] = Field(..., min_length=1)
    title: str | None = Field(None, max_length=500)


class InvoiceUpdate(BaseModel):
    center_ids: list[int] | None = Field(None, min_length=1)
    title: str | None = Field(None, max_length=500)


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    title: str | None
    center_ids: list[int]
    created_at: datetime
    updated_at: datetime


def invoice_response_from_row(row: "Invoice") -> InvoiceResponse:
    return InvoiceResponse(
        id=row.id,
        company_id=row.company_id,
        title=row.title,
        center_ids=[c.id for c in row.centers],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
