"""Customer persistence helpers — map Pydantic ⇄ ORM; preserve app-only fields on QBO merges."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.customer import Customer, CustomerStatus
from app.models.customer_product_and_service import CustomerProductAndService
from app.models.customer_type import CustomerType
from app.models.product_and_service import ProductAndService
from app.models.service_code import ServiceCode
from app.schemas.customer import CustomerCreate, CustomerServiceInput, CustomerUpdate


def _apply_customer_service_links(
    db: Session, row: Customer, services: list[CustomerServiceInput] | None
) -> None:
    if services is None:
        return

    # Validate no duplicate product_and_service_id in the input list
    seen_ps_ids: set[int] = set()
    for svc in services:
        if svc.product_and_service_id in seen_ps_ids:
            raise ValueError(
                f"Duplicate product_and_service_id {svc.product_and_service_id} — each service can only appear once per customer."
            )
        seen_ps_ids.add(svc.product_and_service_id)

    if not services:
        row.customer_services = []
        return

    # Validate all referenced product IDs and service code IDs exist
    ps_ids = [s.product_and_service_id for s in services]
    sc_ids = [s.service_code_id for s in services]

    ps_rows = {
        ps.id: ps
        for ps in db.query(ProductAndService).filter(ProductAndService.id.in_(ps_ids)).all()
    }
    sc_rows = {
        sc.id: sc
        for sc in db.query(ServiceCode).filter(ServiceCode.id.in_(sc_ids)).all()
    }

    missing_ps = sorted(set(ps_ids) - set(ps_rows))
    if missing_ps:
        raise ValueError(f"Unknown product_and_service_ids: {missing_ps}")

    missing_sc = sorted(set(sc_ids) - set(sc_rows))
    if missing_sc:
        raise ValueError(f"Unknown service_code_ids: {missing_sc}")

    # Replace all existing customer_services
    row.customer_services = [
        CustomerProductAndService(
            customer_id=row.id,
            product_and_service_id=svc.product_and_service_id,
            service_code_id=svc.service_code_id,
            rate=svc.rate,
        )
        for svc in services
    ]


def _apply_customer_type_links(db: Session, row: Customer, ids: list[int] | None) -> None:
    if ids is None:
        return
    uniq = list(dict.fromkeys(ids))
    if not uniq:
        row.customer_types = []
        return
    types = db.query(CustomerType).filter(CustomerType.id.in_(uniq)).all()
    found = {ct.id for ct in types}
    if found != set(uniq):
        missing = sorted(set(uniq) - found)
        raise ValueError(f"Unknown customer_type_ids: {missing}")
    row.customer_types = types


def _apply_address_to_billing(row: Customer, addr: object | None) -> None:
    if addr is None:
        return
    d = addr.model_dump(exclude_none=True)
    row.billing_line1 = d.get("line1")
    row.billing_line2 = d.get("line2")
    row.billing_line3 = d.get("line3")
    row.billing_line4 = d.get("line4")
    row.billing_city = d.get("city")
    row.billing_state = d.get("state")
    row.billing_zip = d.get("zip")
    row.billing_country = d.get("country")


def _apply_address_to_shipping(row: Customer, addr: object | None) -> None:
    if addr is None:
        return
    d = addr.model_dump(exclude_none=True)
    row.shipping_line1 = d.get("line1")
    row.shipping_line2 = d.get("line2")
    row.shipping_line3 = d.get("line3")
    row.shipping_line4 = d.get("line4")
    row.shipping_city = d.get("city")
    row.shipping_state = d.get("state")
    row.shipping_zip = d.get("zip")
    row.shipping_country = d.get("country")


def create_customer_row(
    db: Session,
    body: CustomerCreate,
    created_by_id: int | None = None,
) -> Customer:
    row = Customer(
        status=CustomerStatus.pending,
        created_by_id=created_by_id,
        title=body.title,
        given_name=body.given_name,
        middle_name=body.middle_name,
        family_name=body.family_name,
        suffix=body.suffix,
        company_name=body.company_name,
        display_name=body.display_name,
        primary_email=str(body.primary_email) if body.primary_email else None,
        phone_number=body.phone_number,
        cc_email=body.cc_email,
        bcc_email=body.bcc_email,
        mobile=body.mobile,
        fax=body.fax,
        other_contact=body.other_contact,
        website=body.website,
        print_on_check_name=body.print_on_check_name,
        ship_same_as_billing=body.ship_same_as_billing,
        notes=body.notes,
        add_attachment_in_mail=body.add_attachment_in_mail,
    )
    _apply_address_to_billing(row, body.billing)
    if body.ship_same_as_billing:
        row.shipping_line1 = row.billing_line1
        row.shipping_line2 = row.billing_line2
        row.shipping_line3 = row.billing_line3
        row.shipping_line4 = row.billing_line4
        row.shipping_city = row.billing_city
        row.shipping_state = row.billing_state
        row.shipping_zip = row.billing_zip
        row.shipping_country = row.billing_country
    else:
        _apply_address_to_shipping(row, body.shipping)

    db.add(row)
    db.flush()
    _apply_customer_service_links(db, row, body.customer_services)
    _apply_customer_type_links(db, row, body.customer_type_ids)
    db.commit()
    db.refresh(row)
    return row


def update_customer_row(db: Session, row: Customer, body: CustomerUpdate) -> Customer:
    if body.billing is not None:
        _apply_address_to_billing(row, body.billing)
    if body.shipping is not None:
        _apply_address_to_shipping(row, body.shipping)

    if body.title is not None:
        row.title = body.title
    if body.given_name is not None:
        row.given_name = body.given_name
    if body.middle_name is not None:
        row.middle_name = body.middle_name
    if body.family_name is not None:
        row.family_name = body.family_name
    if body.suffix is not None:
        row.suffix = body.suffix
    if body.company_name is not None:
        row.company_name = body.company_name
    if body.display_name is not None:
        row.display_name = body.display_name
    if body.primary_email is not None:
        row.primary_email = str(body.primary_email)
    if body.phone_number is not None:
        row.phone_number = body.phone_number
    if body.cc_email is not None:
        row.cc_email = body.cc_email
    if body.bcc_email is not None:
        row.bcc_email = body.bcc_email
    if body.mobile is not None:
        row.mobile = body.mobile
    if body.fax is not None:
        row.fax = body.fax
    if body.other_contact is not None:
        row.other_contact = body.other_contact
    if body.website is not None:
        row.website = body.website
    if body.print_on_check_name is not None:
        row.print_on_check_name = body.print_on_check_name
    if body.ship_same_as_billing is not None:
        row.ship_same_as_billing = body.ship_same_as_billing
    if body.notes is not None:
        row.notes = body.notes
    if body.add_attachment_in_mail is not None:
        row.add_attachment_in_mail = body.add_attachment_in_mail

    if body.customer_services is not None:
        _apply_customer_service_links(db, row, body.customer_services)

    if body.customer_type_ids is not None:
        _apply_customer_type_links(db, row, body.customer_type_ids)

    if row.ship_same_as_billing:
        row.shipping_line1 = row.billing_line1
        row.shipping_line2 = row.billing_line2
        row.shipping_line3 = row.billing_line3
        row.shipping_line4 = row.billing_line4
        row.shipping_city = row.billing_city
        row.shipping_state = row.billing_state
        row.shipping_zip = row.billing_zip
        row.shipping_country = row.billing_country

    db.add(row)
    db.commit()
    db.refresh(row)
    return row
