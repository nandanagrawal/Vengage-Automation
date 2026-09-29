from __future__ import annotations

from decimal import Decimal

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


class InputRequirement(BaseModel):
    """One 'Input'-priced service row still needing a quantity typed in for
    this run. Not a blocking error by itself — the frontend shows a number
    box for each of these between Validate and Preview; the list is
    unsatisfied-only, so it empties out as quantities are supplied."""
    customer_product_and_service_id: int
    customer_id: int
    customer_display_name: str
    product_name: str
    description: str | None
    center_id: int | None
    center_name: str | None


class InputQuantityEntry(BaseModel):
    customer_product_and_service_id: int
    quantity: Decimal


class ValidationResponse(BaseModel):
    metric_columns: list[str]
    rows: list[ValidatedRow]
    customer_errors: list[CustomerError] = []
    has_errors: bool
    input_requirements: list[InputRequirement] = []


class RevalidateRequest(BaseModel):
    metric_columns: list[str]
    rows: list[ValidatedRow]
    # Optional Drive folder link — checked here (not just at Generate) so a
    # customer requiring an attachment with no matching file is a blocking
    # validation error. See app/services/gdrive_client.py.
    drive_folder_url: str | None = None
    # Quantities typed in for "input"-priced service rows so far this run —
    # unsatisfied ones come back in ValidationResponse.input_requirements.
    input_quantities: list[InputQuantityEntry] = []


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


class GenerateRequest(BaseModel):
    metric_columns: list[str]
    rows: list[ValidatedRow]
    # Optional Drive folder link holding per-center raw-data files (e.g.
    # "VNG-IMG-60.xlsx") — each matched center's file is attached to its
    # QBO invoice. See app/services/gdrive_client.py. Already checked as a
    # blocking Validate-stage error (see RevalidateRequest.drive_folder_url);
    # carried again here since it's the actual download/attach step.
    drive_folder_url: str | None = None
    # Quantities typed in for "input"-priced service rows — required (and
    # already enforced) to be complete by the time Generate is called.
    input_quantities: list[InputQuantityEntry] = []
