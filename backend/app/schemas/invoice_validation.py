from __future__ import annotations

from pydantic import BaseModel


class ValidatedRow(BaseModel):
    row_index: int
    center_id: str       # col 0 original case
    center_name: str     # col 1
    center_prefix: str   # col 2 first token
    metrics: dict[str, float]   # original-case metric column name → value
    # server-populated on validate/revalidate
    errors: list[str] = []
    customer_id: int | None = None
    customer_display_name: str | None = None
    matched: bool = False


class CustomerError(BaseModel):
    customer_display_name: str
    errors: list[str]


class ValidationResponse(BaseModel):
    metric_columns: list[str]
    rows: list[ValidatedRow]
    customer_errors: list[CustomerError] = []
    has_errors: bool


class RevalidateRequest(BaseModel):
    metric_columns: list[str]
    rows: list[ValidatedRow]


# ── Preview ───────────────────────────────────────────────────────────────────

class PreviewCenter(BaseModel):
    center_id: str
    center_name: str
    center_prefix: str
    metrics: dict[str, float]


class PreviewGroup(BaseModel):
    group_label: str
    centers: list[PreviewCenter]


class PreviewCustomer(BaseModel):
    customer_id: int
    display_name: str
    add_attachment_in_mail: bool
    primary_email: str | None
    has_qbo_id: bool
    groups: list[PreviewGroup]


class PreviewResponse(BaseModel):
    metric_columns: list[str]
    customers: list[PreviewCustomer]
    warnings: list[str] = []


# ── Attachment preview + generate ─────────────────────────────────────────────

class AttachmentPreviewRequest(BaseModel):
    customer_id: int
    metric_columns: list[str]
    rows: list[ValidatedRow]   # only rows belonging to this customer's centers


class GenerateRequest(BaseModel):
    metric_columns: list[str]
    rows: list[ValidatedRow]
