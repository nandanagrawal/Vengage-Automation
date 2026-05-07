from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CenterCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)


class CenterUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)


class CenterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    name: str
    created_at: datetime
    updated_at: datetime
