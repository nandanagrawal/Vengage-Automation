from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.product_and_service import ProductAndService
from app.models.product_column_mapping import ProductColumnMapping
from app.models.sheet_column import SheetColumn
from app.models.user import User
from app.schemas.product_and_service import (
    ProductColumnMappingInput,
    ProductColumnMappingResponse,
)

router = APIRouter()


def _to_response(row: ProductColumnMapping) -> ProductColumnMappingResponse:
    return ProductColumnMappingResponse(
        product_and_service_id=row.product_and_service_id,
        product_name=row.product_and_service.name,
        sheet_column_id=row.sheet_column_id,
        column_header=row.sheet_column.name,
    )


@router.get("/product-column-mappings", response_model=list[ProductColumnMappingResponse])
def list_product_column_mappings(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    rows = (
        db.query(ProductColumnMapping)
        .join(ProductAndService, ProductColumnMapping.product_and_service_id == ProductAndService.id)
        .order_by(ProductAndService.name)
        .all()
    )
    return [_to_response(row) for row in rows]


@router.patch("/product-and-services/{product_id}/column-mapping", response_model=ProductColumnMappingResponse)
def set_product_column_mapping(
    product_id: int,
    body: ProductColumnMappingInput,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    product = db.query(ProductAndService).filter(ProductAndService.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    sheet_column = db.query(SheetColumn).filter(SheetColumn.id == body.sheet_column_id).first()
    if not sheet_column:
        raise HTTPException(status_code=404, detail="Sheet column not found")

    # One column -> one product. Block if another product already has this column,
    # unless it's this exact product's own existing mapping being re-saved.
    clash = (
        db.query(ProductColumnMapping)
        .filter(
            ProductColumnMapping.sheet_column_id == body.sheet_column_id,
            ProductColumnMapping.product_and_service_id != product_id,
        )
        .first()
    )
    if clash:
        raise HTTPException(
            status_code=409,
            detail=f"Column '{sheet_column.name}' is already mapped to '{clash.product_and_service.name}'.",
        )

    row = (
        db.query(ProductColumnMapping)
        .filter(ProductColumnMapping.product_and_service_id == product_id)
        .first()
    )
    if row:
        row.sheet_column_id = body.sheet_column_id
    else:
        row = ProductColumnMapping(product_and_service_id=product_id, sheet_column_id=body.sheet_column_id)
        db.add(row)
    db.commit()
    db.refresh(row)

    return _to_response(row)


@router.delete("/product-and-services/{product_id}/column-mapping", status_code=204)
def delete_product_column_mapping(
    product_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    row = (
        db.query(ProductColumnMapping)
        .filter(ProductColumnMapping.product_and_service_id == product_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="No column mapping set for this product")
    db.delete(row)
    db.commit()
