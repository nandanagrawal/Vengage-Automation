from datetime import datetime
from decimal import Decimal

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field

from app.models.customer import Customer, CustomerStatus


class AddressMixin(BaseModel):
    line1: str | None = None
    line2: str | None = None
    line3: str | None = None
    line4: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    country: str | None = None


class CustomerCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = None
    given_name: str | None = Field(None, validation_alias=AliasChoices("given_name", "first_name"))
    middle_name: str | None = None
    family_name: str | None = Field(None, validation_alias=AliasChoices("family_name", "last_name"))
    suffix: str | None = None
    company_name: str | None = None
    display_name: str = Field(..., min_length=1, max_length=500)

    primary_email: EmailStr | None = None
    phone_number: str | None = None
    cc_email: str | None = None
    bcc_email: str | None = None
    mobile: str | None = None
    fax: str | None = None
    other_contact: str | None = None
    website: str | None = None
    print_on_check_name: str | None = None

    billing: AddressMixin | None = None
    ship_same_as_billing: bool = True
    shipping: AddressMixin | None = None

    notes: str | None = None
    rate: Decimal = Field(default=Decimal("0"), ge=0)
    add_attachment_in_mail: bool = False
    product_and_service_ids: list[int] | None = None


class CustomerUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = None
    given_name: str | None = Field(None, validation_alias=AliasChoices("given_name", "first_name"))
    middle_name: str | None = None
    family_name: str | None = Field(None, validation_alias=AliasChoices("family_name", "last_name"))
    suffix: str | None = None
    company_name: str | None = None
    display_name: str | None = Field(None, min_length=1, max_length=500)

    primary_email: EmailStr | None = None
    phone_number: str | None = None
    cc_email: str | None = None
    bcc_email: str | None = None
    mobile: str | None = None
    fax: str | None = None
    other_contact: str | None = None
    website: str | None = None
    print_on_check_name: str | None = None

    billing: AddressMixin | None = None
    ship_same_as_billing: bool | None = None
    shipping: AddressMixin | None = None

    notes: str | None = None
    rate: Decimal | None = Field(None, ge=0)
    add_attachment_in_mail: bool | None = None
    product_and_service_ids: list[int] | None = None


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: CustomerStatus
    created_by_id: int | None = None
    approved_by_id: int | None = None
    qbo_id: str | None = None

    title: str | None = None
    given_name: str | None = None
    middle_name: str | None = None
    family_name: str | None = None
    suffix: str | None = None
    company_name: str | None = None
    display_name: str

    primary_email: str | None = None
    phone_number: str | None = None
    cc_email: str | None = None
    bcc_email: str | None = None
    mobile: str | None = None
    fax: str | None = None
    other_contact: str | None = None
    website: str | None = None
    print_on_check_name: str | None = None

    billing_line1: str | None = None
    billing_line2: str | None = None
    billing_line3: str | None = None
    billing_line4: str | None = None
    billing_city: str | None = None
    billing_state: str | None = None
    billing_zip: str | None = None
    billing_country: str | None = None

    ship_same_as_billing: bool = True

    shipping_line1: str | None = None
    shipping_line2: str | None = None
    shipping_line3: str | None = None
    shipping_line4: str | None = None
    shipping_city: str | None = None
    shipping_state: str | None = None
    shipping_zip: str | None = None
    shipping_country: str | None = None

    notes: str | None = None
    rate: Decimal = Field(default=Decimal("0"))
    add_attachment_in_mail: bool = False
    product_and_service_ids: list[int] = Field(default_factory=list)

    created_at: datetime
    updated_at: datetime
    qbo_last_updated: datetime | None = None
    last_pushed_to_qbo_at: datetime | None = None


class ApprovalAction(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")


class SyncResult(BaseModel):
    customers_pulled: int = 0
    customers_pushed: int = 0
    customers_created_remote: int = 0
    invoice_activity_rows: int = 0
    attachments_pruned: int = 0
    items_upserted: int = 0
    items_removed_local: int = 0
    message: str = "OK"


def customer_response_from_row(row: Customer) -> CustomerResponse:
    base = CustomerResponse.model_validate(row, from_attributes=True)
    return base.model_copy(
        update={"product_and_service_ids": [p.id for p in row.product_and_services]},
    )


class InvoiceActivityItem(BaseModel):
    customer_display_name: str
    invoice_number: str
    email_status: str
    txn_date: str | None = None
