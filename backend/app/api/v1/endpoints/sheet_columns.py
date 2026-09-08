from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.product_column_mapping import ProductColumnMapping
from app.models.sheet_column import SheetColumn
from app.models.user import User
from app.schemas.product_and_service import SheetColumnInput, SheetColumnResponse

router = APIRouter()


def _to_response(row: SheetColumn) -> SheetColumnResponse:
    mapping = row.product_mapping
    return SheetColumnResponse(
        id=row.id,
        name=row.name,
        mapped_product_name=mapping.product_and_service.name if mapping else None,
    )


@router.get("/sheet-columns", response_model=list[SheetColumnResponse])
def list_sheet_columns(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    rows = (
        db.query(SheetColumn)
        .options(
            selectinload(SheetColumn.product_mapping).selectinload(ProductColumnMapping.product_and_service)
        )
        .order_by(SheetColumn.name)
        .all()
    )
    return [_to_response(row) for row in rows]


@router.post("/sheet-columns", response_model=SheetColumnResponse, status_code=201)
def create_sheet_column(
    body: SheetColumnInput,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name cannot be blank")

    existing = db.query(SheetColumn).filter(SheetColumn.name == name).first()
    if existing:
        raise HTTPException(status_code=409, detail="This column is already in the catalog")

    row = SheetColumn(name=name)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.delete("/sheet-columns/{column_id}", status_code=204)
def delete_sheet_column(
    column_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    row = db.query(SheetColumn).filter(SheetColumn.id == column_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Column not found")

    in_use = (
        db.query(ProductColumnMapping)
        .filter(ProductColumnMapping.sheet_column_id == column_id)
        .first()
    )
    if in_use:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot delete: this column is mapped to a product. "
                "Clear that mapping first."
            ),
        )

    db.delete(row)
    db.commit()
