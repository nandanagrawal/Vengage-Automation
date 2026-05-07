from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.api.deps import assert_customer_access, get_current_user
from app.db.session import get_db
from app.models.center import Center
from app.models.customer import Customer
from app.models.invoice import Invoice, invoice_centers
from app.models.user import User, UserRole
from app.schemas.invoice import InvoiceCreate, InvoiceResponse, InvoiceUpdate, invoice_response_from_row

router = APIRouter()


def _load_centers_for_company(db: Session, company_id: int, center_ids: list[int]) -> list[Center]:
    uniq = list(dict.fromkeys(center_ids))
    rows = (
        db.query(Center)
        .filter(Center.company_id == company_id, Center.id.in_(uniq))
        .all()
    )
    if len(rows) != len(uniq):
        raise HTTPException(status_code=422, detail="One or more center_ids are invalid for this company")
    return rows


def _assert_centers_exclusive_to_one_grouping(
    db: Session,
    company_id: int,
    center_ids: list[int],
    exclude_invoice_id: int | None,
) -> None:
    """Each center may appear in at most one invoice grouping per company."""
    uniq = list(dict.fromkeys(center_ids))
    if not uniq:
        return
    q = (
        db.query(invoice_centers.c.center_id, Invoice.id)
        .join(Invoice, Invoice.id == invoice_centers.c.invoice_id)
        .filter(
            Invoice.company_id == company_id,
            invoice_centers.c.center_id.in_(uniq),
        )
    )
    if exclude_invoice_id is not None:
        q = q.filter(Invoice.id != exclude_invoice_id)
    conflicts = q.all()
    if not conflicts:
        return
    by_center: dict[int, set[int]] = {}
    for center_id, inv_id in conflicts:
        by_center.setdefault(center_id, set()).add(inv_id)
    parts = [
        f"center {cid} is already in grouping #{min(inv_ids)}"
        for cid, inv_ids in sorted(by_center.items())
    ]
    raise HTTPException(
        status_code=422,
        detail="Each center can only belong to one invoice grouping for this company. " + "; ".join(parts),
    )


def _visible_invoice_query(db: Session, user: User):
    q = db.query(Invoice).options(selectinload(Invoice.centers))
    if user.role == UserRole.admin:
        return q
    return q.join(Customer).filter(Customer.created_by_id == user.id)


@router.get("/invoices", response_model=list[InvoiceResponse])
def list_invoices(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = _visible_invoice_query(db, user).order_by(Invoice.id.desc()).all()
    return [invoice_response_from_row(r) for r in rows]


@router.post("/invoices", response_model=InvoiceResponse)
def create_invoice(
    body: InvoiceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    assert_customer_access(db, user, body.company_id)
    centers = _load_centers_for_company(db, body.company_id, body.center_ids)
    _assert_centers_exclusive_to_one_grouping(db, body.company_id, body.center_ids, exclude_invoice_id=None)
    inv = Invoice(company_id=body.company_id, title=body.title.strip() if body.title else None)
    inv.centers = centers
    db.add(inv)
    db.commit()
    db.refresh(inv)
    inv = (
        db.query(Invoice)
        .options(selectinload(Invoice.centers))
        .filter(Invoice.id == inv.id)
        .one()
    )
    return invoice_response_from_row(inv)


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = (
        _visible_invoice_query(db, user)
        .filter(Invoice.id == invoice_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice_response_from_row(row)


@router.patch("/invoices/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(
    invoice_id: int,
    body: InvoiceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = (
        _visible_invoice_query(db, user)
        .filter(Invoice.id == invoice_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Invoice not found")

    assert_customer_access(db, user, row.company_id)

    if body.title is not None:
        inv_title = body.title.strip() if body.title else None
        row.title = inv_title if inv_title else None
    if body.center_ids is not None:
        _assert_centers_exclusive_to_one_grouping(
            db, row.company_id, body.center_ids, exclude_invoice_id=row.id
        )
        row.centers = _load_centers_for_company(db, row.company_id, body.center_ids)
    db.add(row)
    db.commit()
    db.refresh(row)
    row = (
        db.query(Invoice)
        .options(selectinload(Invoice.centers))
        .filter(Invoice.id == invoice_id)
        .one()
    )
    return invoice_response_from_row(row)


@router.delete("/invoices/{invoice_id}", status_code=204)
def delete_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = (
        _visible_invoice_query(db, user)
        .filter(Invoice.id == invoice_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Invoice not found")
    db.delete(row)
    db.commit()
