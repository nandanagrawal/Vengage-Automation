from pydantic import BaseModel, ConfigDict


class ProductAndServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    qbo_id: str
    name: str
    sku: str | None = None
    item_type: str | None = None
    active: bool = True
    description: str | None = None
