from datetime import datetime

from pydantic import BaseModel, Field


class ServiceCodeCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=255)


class ServiceCodeUpdate(BaseModel):
    code: str | None = Field(None, min_length=1, max_length=255)
    status: bool | None = None


class ServiceCodeResponse(BaseModel):
    id: int
    code: str
    status: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
