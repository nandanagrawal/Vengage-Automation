from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.product_and_service import ProductAndService
from app.models.user import User
from app.schemas.product_and_service import ProductAndServiceResponse

router = APIRouter()


@router.get("/product-and-services", response_model=list[ProductAndServiceResponse])
def list_product_and_services(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return db.query(ProductAndService).order_by(ProductAndService.name).all()
