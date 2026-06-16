from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update as sqla_update
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.customer import Customer, CustomerStatus
from app.models.customer_type import CustomerType
from app.models.user import User, UserRole
from app.schemas.customer import (
    ApprovalAction,
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
    customer_response_from_row,
)
from app.services.customer_service import create_customer_row, update_customer_row

router = APIRouter()


def _get_customer_or_404(db: Session, customer_id: int) -> Customer:
    row = (
        db.query(Customer)
        .options(
            selectinload(Customer.customer_services),
            selectinload(Customer.customer_types),
        )
        .filter(Customer.id == customer_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    return row


@router.get("/customers", response_model=list[CustomerResponse])
def list_customers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(Customer)
        .options(
            selectinload(Customer.customer_services),
            selectinload(Customer.customer_types),
        )
        .order_by(Customer.display_name)
        .all()
    )
    return [customer_response_from_row(r) for r in rows]


@router.post("/customers", response_model=CustomerResponse)
def post_customer(
    body: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        row = create_customer_row(db, body, created_by_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    if current_user.role == UserRole.admin:
        row.status = CustomerStatus.approved
        row.approved_by_id = current_user.id
        db.add(row)
        db.commit()
        db.refresh(row)
    # Supervisor → status stays pending until admin approves

    row = _get_customer_or_404(db, row.id)
    return customer_response_from_row(row)


@router.get("/customers/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = _get_customer_or_404(db, customer_id)
    return customer_response_from_row(row)


@router.patch("/customers/{customer_id}", response_model=CustomerResponse)
def patch_customer(
    customer_id: int,
    body: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(Customer).filter(Customer.id == customer_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Supervisors can only edit customers they created; admins can edit any
    if current_user.role == UserRole.supervisor and row.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own customers")

    try:
        row = update_customer_row(db, row, body)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    # Local-only edit — never pushed to QBO. QBO is pulled in via Sync.
    row = _get_customer_or_404(db, customer_id)
    return customer_response_from_row(row)


@router.delete("/customers/{customer_id}", status_code=204)
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    row = _get_customer_or_404(db, customer_id)
    db.delete(row)
    db.commit()


@router.post("/customers/{customer_id}/approve", response_model=CustomerResponse)
def approve_customer(
    customer_id: int,
    body: ApprovalAction,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    row = db.query(Customer).filter(Customer.id == customer_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    if row.status != CustomerStatus.pending:
        raise HTTPException(status_code=409, detail=f"Customer is already {row.status.value}")

    if body.action == "approve":
        # Local-only — never pushed to QBO.
        # Atomic status flip: UPDATE WHERE status='pending' so that a concurrent
        # request that also passed the initial check cannot double-approve.
        result = db.execute(
            sqla_update(Customer)
            .where(Customer.id == customer_id, Customer.status == CustomerStatus.pending)
            .values(status=CustomerStatus.approved, approved_by_id=admin.id)
            .execution_options(synchronize_session=False)
        )
        db.commit()
        if result.rowcount == 0:
            raise HTTPException(
                status_code=409,
                detail="Customer was already approved by a concurrent request",
            )
    else:
        row.status = CustomerStatus.rejected
        row.approved_by_id = admin.id
        db.add(row)
        db.commit()

    db.refresh(row)
    return customer_response_from_row(_get_customer_or_404(db, customer_id))
