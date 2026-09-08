from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.product_and_service import ProductAndService
from app.models.product_column_mapping import ProductColumnMapping
from app.models.user import User
from app.schemas.product_and_service import ProductAndServiceResponse

router = APIRouter()


@router.get("/product-and-services", response_model=list[ProductAndServiceResponse])
def list_product_and_services(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    rows = (
        db.query(ProductAndService)
        .options(
            selectinload(ProductAndService.column_mapping).selectinload(ProductColumnMapping.sheet_column)
        )
        .order_by(ProductAndService.name)
        .all()
    )
    return [
        ProductAndServiceResponse.model_validate(row, from_attributes=True).model_copy(
            update={
                "sheet_column_id": row.column_mapping.sheet_column_id if row.column_mapping else None,
                "column_header": row.column_mapping.sheet_column.name if row.column_mapping else None,
            }
        )
        for row in rows
    ]
