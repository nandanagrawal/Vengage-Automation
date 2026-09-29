from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CenterCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    drive_file_names: str | None = None


class CenterUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    drive_file_names: str | None = None


class CenterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    name: str
    drive_file_names: str | None = None
    created_at: datetime
    updated_at: datetime
