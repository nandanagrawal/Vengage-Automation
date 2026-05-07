from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CustomerAttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    original_filename: str
    content_type: str
    size_bytes: int
    qbo_attachable_id: str | None
    created_at: datetime


class UploadAttachmentsResult(BaseModel):
    attachments: list[CustomerAttachmentResponse]
    errors: list[str]
