from pydantic import BaseModel, ConfigDict, Field


class ProductAndServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    qbo_id: str
    name: str
    sku: str | None = None
    item_type: str | None = None
    active: bool = True
    description: str | None = None


class SheetColumnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class SheetColumnInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
