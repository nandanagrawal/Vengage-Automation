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
    # Admin-configured spreadsheet column — see ProductColumnMapping. Quantity
    # resolution is dynamic-mapping-only; a product with no mapping (None
    # here) produces no invoice line item at all.
    sheet_column_id: int | None = None
    column_header: str | None = None


class SheetColumnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    # Set when this column is already assigned to a product — lets the
    # frontend explain why a column is greyed out in the dropdown.
    mapped_product_name: str | None = None


class SheetColumnInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)


class ProductColumnMappingInput(BaseModel):
    sheet_column_id: int


class ProductColumnMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_and_service_id: int
    product_name: str
    sheet_column_id: int
    column_header: str
