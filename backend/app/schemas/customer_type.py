from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CustomerTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class CustomerTypeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    status: bool | None = None


class CustomerTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: bool
    created_at: datetime
    updated_at: datetime
