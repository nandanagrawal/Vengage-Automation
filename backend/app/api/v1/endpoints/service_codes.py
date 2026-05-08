from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.customer_product_and_service import CustomerProductAndService
from app.models.service_code import ServiceCode
from app.models.user import User
from app.schemas.service_code import ServiceCodeCreate, ServiceCodeResponse, ServiceCodeUpdate

router = APIRouter()


@router.get("/service-codes", response_model=list[ServiceCodeResponse])
def list_service_codes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(ServiceCode).order_by(ServiceCode.code).all()


@router.post("/service-codes", response_model=ServiceCodeResponse, status_code=201)
def create_service_code(
    body: ServiceCodeCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    existing = db.query(ServiceCode).filter(ServiceCode.code == body.code).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Service code '{body.code}' already exists.")
    sc = ServiceCode(code=body.code, status=True)
    db.add(sc)
    db.commit()
    db.refresh(sc)
    return sc


@router.patch("/service-codes/{code_id}", response_model=ServiceCodeResponse)
def update_service_code(
    code_id: int,
    body: ServiceCodeUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    sc = db.query(ServiceCode).filter(ServiceCode.id == code_id).first()
    if not sc:
        raise HTTPException(status_code=404, detail="Service code not found.")

    if body.code is not None:
        dup = db.query(ServiceCode).filter(ServiceCode.code == body.code, ServiceCode.id != code_id).first()
        if dup:
            raise HTTPException(status_code=409, detail=f"Service code '{body.code}' already exists.")
        sc.code = body.code

    if body.status is not None:
        sc.status = body.status

    db.add(sc)
    db.commit()
    db.refresh(sc)
    return sc


@router.delete("/service-codes/{code_id}", status_code=204)
def delete_service_code(
    code_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    sc = db.query(ServiceCode).filter(ServiceCode.id == code_id).first()
    if not sc:
        raise HTTPException(status_code=404, detail="Service code not found.")

    in_use = db.query(CustomerProductAndService).filter(
        CustomerProductAndService.service_code_id == code_id
    ).first()
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete: this service code is assigned to one or more customers.",
        )

    db.delete(sc)
    db.commit()
