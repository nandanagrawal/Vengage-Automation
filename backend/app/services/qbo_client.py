"""QuickBooks Online REST client — sync HTTP calls; mock/replace in tests via dependency overrides."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from app.core.config import settings


class SupportsQuickBooks(Protocol):
    """Protocol for DI / mocking."""

    def base_url(self) -> str: ...

    def query_customers(self, access_token: str, realm_id: str) -> list[dict[str, Any]]: ...

    def get_customer(self, access_token: str, realm_id: str, customer_id: str) -> dict[str, Any]: ...

    def create_customer(self, access_token: str, realm_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...

    def update_customer(
        self,
        access_token: str,
        realm_id: str,
        customer_id: str,
        payload: dict[str, Any],
        sync_token: str | None,
    ) -> dict[str, Any]: ...

    def query_invoice_email_rows(
        self,
        access_token: str,
        realm_id: str,
        since: date,
    ) -> list[dict[str, Any]]: ...

    def query_items(self, access_token: str, realm_id: str) -> list[dict[str, Any]]: ...

    def query_tax_codes(self, access_token: str, realm_id: str) -> list[dict[str, Any]]: ...

    def update_item(
        self,
        access_token: str,
        realm_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]: ...

    def create_invoice(
        self,
        access_token: str,
        realm_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]: ...

    def send_invoice(
        self,
        access_token: str,
        realm_id: str,
        invoice_id: str,
        email: str | None = None,
    ) -> dict[str, Any]: ...

    def attach_to_invoice(
        self,
        access_token: str,
        realm_id: str,
        invoice_id: str,
        filename: str,
        content_type: str,
        file_bytes: bytes,
    ) -> dict[str, Any]: ...

    def get_invoice(
        self,
        access_token: str,
        realm_id: str,
        invoice_id: str,
    ) -> dict[str, Any]: ...

    def query_invoices(
        self,
        access_token: str,
        realm_id: str,
        start_position: int = 1,
        max_results: int = 1000,
    ) -> list[dict[str, Any]]: ...


def _headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


class QuickBooksClient:
    def base_url(self) -> str:
        if settings.QBO_ENVIRONMENT == "sandbox":
            return "https://sandbox-quickbooks.api.intuit.com"
        return "https://quickbooks.api.intuit.com"

    def _minor(self) -> str:
        return settings.QBO_MINOR_VERSION

    def query_customers(self, access_token: str, realm_id: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        start = 1
        page_size = 100
        with httpx.Client(timeout=60.0) as client:
            while True:
                q = quote(f"SELECT * FROM Customer STARTPOSITION {start} MAXRESULTS {page_size}")
                url = f"{self.base_url()}/v3/company/{realm_id}/query?query={q}&minorversion={self._minor()}"
                res = client.get(url, headers=_headers(access_token))
                res.raise_for_status()
                data = res.json()
                batch = data.get("QueryResponse", {}).get("Customer", []) or []
                if isinstance(batch, dict):
                    batch = [batch]
                if not batch:
                    break
                out.extend(batch)
                if len(batch) < page_size:
                    break
                start += page_size
        return out

    def get_customer(self, access_token: str, realm_id: str, customer_id: str) -> dict[str, Any]:
        with httpx.Client(timeout=60.0) as client:
            url = f"{self.base_url()}/v3/company/{realm_id}/customer/{customer_id}?minorversion={self._minor()}"
            res = client.get(url, headers=_headers(access_token))
            res.raise_for_status()
            return res.json().get("Customer", {})

    def create_customer(self, access_token: str, realm_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=60.0) as client:
            url = f"{self.base_url()}/v3/company/{realm_id}/customer?minorversion={self._minor()}"
            res = client.post(url, headers=_headers(access_token), json=payload)
            if not res.is_success:
                raise httpx.HTTPStatusError(
                    f"{res.status_code} from QBO create_customer: {res.text}",
                    request=res.request,
                    response=res,
                )
            return res.json().get("Customer", {})

    def update_customer(
        self,
        access_token: str,
        realm_id: str,
        customer_id: str,
        payload: dict[str, Any],
        sync_token: str | None,
    ) -> dict[str, Any]:
        body = {**payload, "Id": customer_id}
        if sync_token:
            body["SyncToken"] = sync_token
        sparse = os.getenv("QBO_CUSTOMER_SPARSE", "true").lower() in ("1", "true", "yes")
        url = f"{self.base_url()}/v3/company/{realm_id}/customer?minorversion={self._minor()}"
        if sparse:
            url += "&sparse=true"
        with httpx.Client(timeout=60.0) as client:
            res = client.post(url, headers=_headers(access_token), json=body)
            if not res.is_success:
                raise httpx.HTTPStatusError(
                    f"{res.status_code} from QBO update_customer({customer_id}): {res.text}",
                    request=res.request,
                    response=res,
                )
            return res.json().get("Customer", {})

    def query_invoice_email_rows(
        self,
        access_token: str,
        realm_id: str,
        since: date,
    ) -> list[dict[str, Any]]:
        since_str = since.isoformat()
        q = quote(
            "SELECT Id, DocNumber, CustomerRef, EmailStatus, TxnDate FROM Invoice "
            f"WHERE TxnDate >= '{since_str}' MAXRESULTS 1000"
        )
        url = f"{self.base_url()}/v3/company/{realm_id}/query?query={q}&minorversion={self._minor()}"
        with httpx.Client(timeout=60.0) as client:
            res = client.get(url, headers=_headers(access_token))
            res.raise_for_status()
            data = res.json()
            rows = data.get("QueryResponse", {}).get("Invoice", []) or []
            if isinstance(rows, dict):
                rows = [rows]
            return rows

    def query_items(self, access_token: str, realm_id: str) -> list[dict[str, Any]]:
        """Paginated Item query — full catalog (no Active/Type filter)."""
        out: list[dict[str, Any]] = []
        start = 1
        page_size = 100
        with httpx.Client(timeout=120.0) as client:
            while True:
                q = quote(f"SELECT * FROM Item STARTPOSITION {start} MAXRESULTS {page_size}")
                url = f"{self.base_url()}/v3/company/{realm_id}/query?query={q}&minorversion={self._minor()}"
                res = client.get(url, headers=_headers(access_token))
                res.raise_for_status()
                data = res.json()
                batch = data.get("QueryResponse", {}).get("Item", []) or []
                if isinstance(batch, dict):
                    batch = [batch]
                if not batch:
                    break
                out.extend(batch)
                if len(batch) < page_size:
                    break
                start += page_size
        return out

    def query_tax_codes(self, access_token: str, realm_id: str) -> list[dict[str, Any]]:
        """Return all TaxCode objects from QBO (shows valid codes for TaxCodeRef)."""
        q = quote("SELECT * FROM TaxCode MAXRESULTS 100")
        url = f"{self.base_url()}/v3/company/{realm_id}/query?query={q}&minorversion={self._minor()}"
        with httpx.Client(timeout=30.0) as client:
            res = client.get(url, headers=_headers(access_token))
            res.raise_for_status()
            data = res.json()
            result = data.get("QueryResponse", {}).get("TaxCode", []) or []
            return result if isinstance(result, list) else [result]

    def update_item(
        self,
        access_token: str,
        realm_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        url = f"{self.base_url()}/v3/company/{realm_id}/item?minorversion={self._minor()}"
        with httpx.Client(timeout=60.0) as client:
            res = client.post(url, headers=_headers(access_token), json=payload)
            if not res.is_success:
                raise httpx.HTTPStatusError(
                    f"{res.status_code} from QBO update_item: {res.text}",
                    request=res.request,
                    response=res,
                )
            return res.json().get("Item", {})

    def create_invoice(
        self,
        access_token: str,
        realm_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        url = f"{self.base_url()}/v3/company/{realm_id}/invoice?minorversion={self._minor()}"
        with httpx.Client(timeout=60.0) as client:
            res = client.post(url, headers=_headers(access_token), json=payload)
            if not res.is_success:
                raise httpx.HTTPStatusError(
                    f"{res.status_code} from QBO create_invoice: {res.text}",
                    request=res.request,
                    response=res,
                )
            return res.json().get("Invoice", {})

    def send_invoice(
        self,
        access_token: str,
        realm_id: str,
        invoice_id: str,
        email: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url()}/v3/company/{realm_id}/invoice/{invoice_id}/send?minorversion={self._minor()}"
        if email:
            from urllib.parse import quote as _q
            url += f"&sendTo={_q(email)}"
        with httpx.Client(timeout=60.0) as client:
            res = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/octet-stream",
                },
                content=b"",
            )
            if not res.is_success:
                raise httpx.HTTPStatusError(
                    f"{res.status_code} from QBO send_invoice({invoice_id}): {res.text}",
                    request=res.request,
                    response=res,
                )
            return res.json().get("Invoice", {})


    def attach_to_invoice(
        self,
        access_token: str,
        realm_id: str,
        invoice_id: str,
        filename: str,
        content_type: str,
        file_bytes: bytes,
    ) -> dict[str, Any]:
        import json as _json
        import time as _time

        metadata = _json.dumps({
            "AttachableRef": [
                {"EntityRef": {"type": "Invoice", "value": invoice_id}, "IncludeOnSend": True}
            ],
            "ContentType": content_type,
            "FileName": filename,
        })
        url = f"{self.base_url()}/v3/company/{realm_id}/upload?minorversion={self._minor()}"

        last_err: Exception | None = None
        for attempt in range(3):
            if attempt:
                _time.sleep(2 ** attempt)  # 2s, 4s
            with httpx.Client(timeout=120.0) as client:
                res = client.post(
                    url,
                    headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                    files={
                        "file_metadata_01": ("attachment.json", metadata.encode(), "application/json"),
                        "file_content_01": (filename, file_bytes, content_type),
                    },
                )
            if res.is_success:
                return res.json()
            if res.status_code != 503:
                raise httpx.HTTPStatusError(
                    f"{res.status_code} from QBO attach_to_invoice({invoice_id}): {res.text}",
                    request=res.request,
                    response=res,
                )
            last_err = httpx.HTTPStatusError(
                f"503 from QBO attach_to_invoice({invoice_id}) after {attempt + 1} attempt(s): {res.text}",
                request=res.request,
                response=res,
            )

        raise last_err  # type: ignore[misc]

    def get_invoice(
        self,
        access_token: str,
        realm_id: str,
        invoice_id: str,
    ) -> dict[str, Any]:
        url = f"{self.base_url()}/v3/company/{realm_id}/invoice/{invoice_id}?minorversion={self._minor()}"
        with httpx.Client(timeout=30.0) as client:
            res = client.get(url, headers=_headers(access_token))
            if not res.is_success:
                raise httpx.HTTPStatusError(
                    f"{res.status_code} from QBO get_invoice({invoice_id}): {res.text}",
                    request=res.request,
                    response=res,
                )
            return res.json().get("Invoice", {})

    def query_invoices(
        self,
        access_token: str,
        realm_id: str,
        start_position: int = 1,
        max_results: int = 1000,
    ) -> list[dict[str, Any]]:
        from urllib.parse import quote as _q
        sql = f"SELECT * FROM Invoice STARTPOSITION {start_position} MAXRESULTS {max_results} ORDERBY MetaData.LastUpdatedTime DESC"
        url = f"{self.base_url()}/v3/company/{realm_id}/query?query={_q(sql)}&minorversion={self._minor()}"
        with httpx.Client(timeout=60.0) as client:
            res = client.get(url, headers=_headers(access_token))
            if not res.is_success:
                raise httpx.HTTPStatusError(
                    f"{res.status_code} from QBO query_invoices: {res.text}",
                    request=res.request,
                    response=res,
                )
            qr = res.json().get("QueryResponse", {})
            return qr.get("Invoice", [])


def phone_block(number: str | None) -> dict[str, str] | None:
    if not number:
        return None
    return {"FreeFormNumber": number}


def build_qbo_addr(
    line1: str | None = None,
    line2: str | None = None,
    line3: str | None = None,
    line4: str | None = None,
    city: str | None = None,
    state: str | None = None,
    zip_code: str | None = None,
    country: str | None = None,
) -> dict[str, Any]:
    block: dict[str, Any] = {}
    if line1:
        block["Line1"] = line1[:500]
    if line2:
        block["Line2"] = line2[:500]
    if line3:
        block["Line3"] = line3[:500]
    if line4:
        block["Line4"] = line4[:500]
    if city:
        block["City"] = city[:255]
    if country:
        block["Country"] = country[:255]
    if state:
        block["CountrySubDivisionCode"] = state[:255]
    if zip_code:
        block["PostalCode"] = zip_code[:31]
    return block


def customer_model_to_qbo_payload(row: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"DisplayName": row.display_name}
    if row.title:
        payload["Title"] = row.title
    if row.given_name:
        payload["GivenName"] = row.given_name
    if row.middle_name:
        payload["MiddleName"] = row.middle_name
    if row.family_name:
        payload["FamilyName"] = row.family_name
    if row.suffix:
        payload["Suffix"] = row.suffix
    if row.company_name:
        payload["CompanyName"] = row.company_name
    if row.primary_email:
        payload["PrimaryEmailAddr"] = {"Address": row.primary_email}
    if row.phone_number:
        payload["PrimaryPhone"] = phone_block(row.phone_number)
    if row.mobile:
        payload["Mobile"] = phone_block(row.mobile)
    if row.fax:
        payload["Fax"] = phone_block(row.fax)
    if row.website:
        payload["WebAddr"] = {"URI": row.website[:500]}
    if row.print_on_check_name:
        payload["PrintOnCheckName"] = row.print_on_check_name[:500]
    if row.notes:
        payload["Notes"] = row.notes[:4000]

    ba = build_qbo_addr(
        line1=row.billing_line1,
        line2=row.billing_line2,
        line3=row.billing_line3,
        line4=row.billing_line4,
        city=row.billing_city,
        state=row.billing_state,
        zip_code=row.billing_zip,
        country=row.billing_country,
    )
    if ba:
        payload["BillAddr"] = ba

    if row.ship_same_as_billing and payload.get("BillAddr"):
        payload["ShipAddr"] = dict(payload["BillAddr"])
    elif not row.ship_same_as_billing:
        sa = build_qbo_addr(
            line1=row.shipping_line1,
            line2=row.shipping_line2,
            line3=row.shipping_line3,
            line4=row.shipping_line4,
            city=row.shipping_city,
            state=row.shipping_state,
            zip_code=row.shipping_zip,
            country=row.shipping_country,
        )
        if sa:
            payload["ShipAddr"] = sa

    return payload


def datetime_from_qbo(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _item_decimal(val: Any) -> Decimal | None:
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except (ArithmeticError, ValueError, TypeError):
        return None


def _ref_id(ref: Any) -> str | None:
    if not ref or not isinstance(ref, dict):
        return None
    v = ref.get("value")
    return str(v) if v is not None else None


def _ref_name(ref: Any) -> str | None:
    if not ref or not isinstance(ref, dict):
        return None
    n = ref.get("name")
    return str(n) if n is not None else None


def apply_qbo_item_to_model(row: Any, qbo: dict[str, Any]) -> None:
    """Map QBO Item JSON onto ProductAndService ORM row (flattened columns)."""
    row.qbo_id = str(qbo.get("Id", row.qbo_id or ""))
    row.sync_token = str(qbo.get("SyncToken", "")) or None
    row.name = (qbo.get("Name") or getattr(row, "name", None) or "Item")[:500]
    sku = qbo.get("Sku")
    row.sku = (str(sku)[:200] if sku is not None else None)
    row.item_type = qbo.get("Type")
    row.active = bool(qbo.get("Active", True))
    fqn = qbo.get("FullyQualifiedName")
    row.fully_qualified_name = str(fqn)[:500] if fqn is not None else None
    row.taxable = qbo.get("Taxable")

    unit = qbo.get("UnitPrice")
    pc = qbo.get("PurchaseCost")
    if unit is None or pc is None:
        sp = qbo.get("SalesOrPurchase") or qbo.get("SalesAndPurchase") or {}
        if unit is None:
            unit = sp.get("UnitPrice") or sp.get("SalesPrice")
        if pc is None:
            pc = sp.get("PurchaseCost")
    row.unit_price = _item_decimal(unit)
    row.purchase_cost = _item_decimal(pc)

    row.description = qbo.get("Description")
    row.purchase_desc = qbo.get("PurchaseDesc")

    row.track_qty_on_hand = qbo.get("TrackQtyOnHand")
    row.qty_on_hand = _item_decimal(qbo.get("QtyOnHand"))
    inv = qbo.get("InvStartDate")
    row.inv_start_date = str(inv) if inv is not None else None

    pf = qbo.get("ParentRef") or {}
    row.parent_qbo_id = _ref_id(pf)
    row.parent_name = _ref_name(pf)

    row.income_account_qbo_id = _ref_id(qbo.get("IncomeAccountRef"))
    row.expense_account_qbo_id = _ref_id(qbo.get("ExpenseAccountRef"))
    row.asset_account_qbo_id = _ref_id(qbo.get("AssetAccountRef"))

    qt = qbo_time(qbo)
    if qt:
        row.qbo_last_updated = qt


def qbo_time(qbo: dict[str, Any]) -> datetime | None:
    meta = qbo.get("MetaData") or {}
    lu = meta.get("LastUpdatedTime")
    if not lu:
        return None
    try:
        return datetime_from_qbo(lu)
    except ValueError:
        return None


def apply_qbo_customer_to_model(row: Any, qbo: dict[str, Any]) -> None:
    qt = qbo_time(qbo)
    if qt:
        row.qbo_last_updated = qt

    row.qbo_id = str(qbo.get("Id", row.qbo_id or ""))
    row.display_name = qbo.get("DisplayName") or row.display_name
    row.title = qbo.get("Title")
    row.given_name = qbo.get("GivenName")
    row.middle_name = qbo.get("MiddleName")
    row.family_name = qbo.get("FamilyName")
    row.suffix = qbo.get("Suffix")
    row.company_name = qbo.get("CompanyName")

    pe = qbo.get("PrimaryEmailAddr") or {}
    row.primary_email = pe.get("Address")

    row.phone_number = _read_phone(qbo.get("PrimaryPhone"))
    row.mobile = _read_phone(qbo.get("Mobile"))
    row.fax = _read_phone(qbo.get("Fax"))

    web = qbo.get("WebAddr") or {}
    row.website = web.get("URI")

    row.print_on_check_name = qbo.get("PrintOnCheckName")
    row.notes = qbo.get("Notes")

    ba = qbo.get("BillAddr") or {}
    row.billing_line1 = ba.get("Line1")
    row.billing_line2 = ba.get("Line2")
    row.billing_line3 = ba.get("Line3")
    row.billing_line4 = ba.get("Line4")
    row.billing_city = ba.get("City")
    row.billing_country = ba.get("Country")
    row.billing_state = ba.get("CountrySubDivisionCode")
    row.billing_zip = ba.get("PostalCode")

    sa = qbo.get("ShipAddr") or {}
    if sa:
        row.ship_same_as_billing = False
        row.shipping_line1 = sa.get("Line1")
        row.shipping_line2 = sa.get("Line2")
        row.shipping_line3 = sa.get("Line3")
        row.shipping_line4 = sa.get("Line4")
        row.shipping_city = sa.get("City")
        row.shipping_country = sa.get("Country")
        row.shipping_state = sa.get("CountrySubDivisionCode")
        row.shipping_zip = sa.get("PostalCode")


def _read_phone(block: Any) -> str | None:
    if not block:
        return None
    return block.get("FreeFormNumber")


def effective_local_time(row: Any) -> datetime:
    u = row.updated_at
    if u.tzinfo is None:
        u = u.replace(tzinfo=timezone.utc)
    q = row.qbo_last_updated
    if q is None:
        return u
    if q.tzinfo is None:
        q = q.replace(tzinfo=timezone.utc)
    return max(u, q)
