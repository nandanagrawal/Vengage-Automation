from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import assert_customer_access, get_current_user
from app.db.session import get_db
from app.models.center import Center
from app.models.customer import Customer
from app.models.user import User
from app.schemas.center import CenterCreate, CenterResponse, CenterUpdate

router = APIRouter()


@router.get("/customers/{customer_id}/centers", response_model=list[CenterResponse])
def list_centers(
    customer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    assert_customer_access(db, user, customer_id)
    return (
        db.query(Center)
        .filter(Center.company_id == customer_id)
        .order_by(Center.name)
        .all()
    )


@router.post("/customers/{customer_id}/centers", response_model=CenterResponse)
def create_center(
    customer_id: int,
    body: CenterCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    assert_customer_access(db, user, customer_id)
    name = body.name.strip()
    exists = (
        db.query(Center)
        .filter(Center.company_id == customer_id, Center.name == name)
        .first()
    )
    if exists:
        raise HTTPException(status_code=409, detail=f"A center named '{name}' already exists for this customer.")
    row = Center(company_id=customer_id, name=name)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/customers/{customer_id}/centers/{center_id}", response_model=CenterResponse)
def update_center(
    customer_id: int,
    center_id: int,
    body: CenterUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    assert_customer_access(db, user, customer_id)
    row = (
        db.query(Center)
        .filter(Center.id == center_id, Center.company_id == customer_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Center not found")
    name = body.name.strip()
    conflict = (
        db.query(Center)
        .filter(Center.company_id == customer_id, Center.name == name, Center.id != center_id)
        .first()
    )
    if conflict:
        raise HTTPException(status_code=409, detail=f"A center named '{name}' already exists for this customer.")
    row.name = name
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/customers/{customer_id}/centers/{center_id}", status_code=204)
def delete_center(
    customer_id: int,
    center_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    assert_customer_access(db, user, customer_id)
    row = (
        db.query(Center)
        .filter(Center.id == center_id, Center.company_id == customer_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Center not found")
    db.delete(row)
    db.commit()
