from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.customer import Customer, CustomerStatus
from app.models.customer_type import CustomerType
from app.models.user import User
from app.schemas.customer_type import CustomerTypeCreate, CustomerTypeResponse, CustomerTypeUpdate

router = APIRouter()


def _get_type_or_404(db: Session, type_id: int) -> CustomerType:
    row = db.query(CustomerType).filter(CustomerType.id == type_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Customer type not found")
    return row


@router.get("/customer-types", response_model=list[CustomerTypeResponse])
def list_customer_types(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(CustomerType).order_by(CustomerType.name).all()


@router.post("/customer-types", response_model=CustomerTypeResponse, status_code=201)
def create_customer_type(
    body: CustomerTypeCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    existing = db.query(CustomerType).filter(CustomerType.name == body.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="A customer type with this name already exists")
    row = CustomerType(name=body.name, status=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/customer-types/{type_id}", response_model=CustomerTypeResponse)
def update_customer_type(
    type_id: int,
    body: CustomerTypeUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    row = _get_type_or_404(db, type_id)
    if body.name is not None:
        existing = (
            db.query(CustomerType)
            .filter(CustomerType.name == body.name, CustomerType.id != type_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=409, detail="A customer type with this name already exists"
            )
        row.name = body.name
    if body.status is not None:
        row.status = body.status
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/customer-types/{type_id}", status_code=204)
def delete_customer_type(
    type_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    row = _get_type_or_404(db, type_id)

    # Block deletion if any approved customer is assigned this type
    blocking_customer = (
        db.query(Customer)
        .filter(
            Customer.status == CustomerStatus.approved,
            Customer.customer_types.any(CustomerType.id == type_id),
        )
        .first()
    )
    if blocking_customer:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot delete: this customer type is assigned to one or more approved customers. "
                "Remove the assignment before deleting."
            ),
        )

    db.delete(row)
    db.commit()
