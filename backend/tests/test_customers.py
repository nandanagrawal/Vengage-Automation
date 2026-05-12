"""Customer module tests: creation, approval workflow, QBO sync, webhooks, field validation."""

import pytest

from tests.conftest import token_for
from app.models.user import UserRole

_BASE = {
    "display_name": "Test Labs",
    "primary_email": "billing@testlabs.example",
    "given_name": "Sam",
    "family_name": "Rivera",
    "add_attachment_in_mail": True,
    "billing": {"line1": "1 Main St", "city": "Sydney", "zip": "2000"},
    "ship_same_as_billing": True,
}


# ── Creation ──────────────────────────────────────────────────────────────────

def test_admin_creates_customer_approved_and_pushed_to_qbo(admin_client, fake_qbo):
    r = admin_client.post("/api/v1/customers", json=_BASE)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "approved"
    assert data["add_attachment_in_mail"] is True
    assert data["qbo_id"] is not None  # admin creation pushes to QBO


def test_supervisor_creates_customer_pending_no_qbo(supervisor_client):
    r = supervisor_client.post("/api/v1/customers", json=_BASE)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "pending"
    assert data["qbo_id"] is None  # not pushed until approved


def test_unauthenticated_cannot_create_customer(client):
    r = client.post("/api/v1/customers", json=_BASE)
    assert r.status_code == 401


def test_list_customers_requires_auth(client):
    assert client.get("/api/v1/customers").status_code == 401


def test_both_roles_can_list_all_customers(admin_client, supervisor_client):
    admin_client.post("/api/v1/customers", json={**_BASE, "display_name": "Acme"})
    supervisor_client.post("/api/v1/customers", json={**_BASE, "display_name": "Beta"})
    rows = admin_client.get("/api/v1/customers").json()
    names = [c["display_name"] for c in rows]
    assert "Acme" in names and "Beta" in names


# ── Approval workflow ─────────────────────────────────────────────────────────

def test_admin_approves_pending_customer_and_pushes_qbo(admin_client, supervisor_client, fake_qbo):
    cid = supervisor_client.post("/api/v1/customers", json=_BASE).json()["id"]
    r = admin_client.post(f"/api/v1/customers/{cid}/approve", json={"action": "approve"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "approved"
    assert data["qbo_id"] is not None  # pushed to QBO on approval


def test_admin_rejects_pending_customer(admin_client, supervisor_client):
    cid = supervisor_client.post("/api/v1/customers", json=_BASE).json()["id"]
    r = admin_client.post(f"/api/v1/customers/{cid}/approve", json={"action": "reject"})
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"


def test_supervisor_cannot_call_approve_endpoint(supervisor_client, admin_client):
    cid = admin_client.post("/api/v1/customers", json=_BASE).json()["id"]
    r = supervisor_client.post(f"/api/v1/customers/{cid}/approve", json={"action": "approve"})
    assert r.status_code == 403


def test_cannot_approve_already_approved_customer(admin_client):
    cid = admin_client.post("/api/v1/customers", json=_BASE).json()["id"]
    r = admin_client.post(f"/api/v1/customers/{cid}/approve", json={"action": "approve"})
    assert r.status_code == 409


def test_cannot_approve_already_rejected_customer(admin_client, supervisor_client):
    cid = supervisor_client.post("/api/v1/customers", json=_BASE).json()["id"]
    admin_client.post(f"/api/v1/customers/{cid}/approve", json={"action": "reject"})
    r = admin_client.post(f"/api/v1/customers/{cid}/approve", json={"action": "approve"})
    assert r.status_code == 409


# ── QBO Sync ──────────────────────────────────────────────────────────────────

def test_sync_pulls_qbo_customer_marked_approved(admin_client, fake_qbo):
    fake_qbo.customers = [{
        "Id": "55",
        "DisplayName": "Remote Co",
        "SyncToken": "1",
        "MetaData": {"LastUpdatedTime": "2026-05-01T10:00:00+00:00"},
        "PrimaryEmailAddr": {"Address": "a@remote.example"},
    }]
    body = admin_client.post("/api/v1/sync/quickbooks").json()
    assert body["customers_pulled"] >= 1

    rows = admin_client.get("/api/v1/customers").json()
    remote = next(c for c in rows if c["display_name"] == "Remote Co")
    assert remote["status"] == "approved"
    assert remote["qbo_id"] == "55"


def test_sync_does_not_push_pending_customers(admin_client, supervisor_client, fake_qbo):
    supervisor_client.post("/api/v1/customers", json={**_BASE, "display_name": "Pending Co"})

    admin_client.post("/api/v1/sync/quickbooks")

    rows = admin_client.get("/api/v1/customers").json()
    pending = next(c for c in rows if c["display_name"] == "Pending Co")
    assert pending["qbo_id"] is None


def test_sync_pulls_invoice_email_activity(admin_client, fake_qbo):
    fake_qbo.invoices = [{
        "Id": "9001",
        "DocNumber": "VNG-9001",
        "CustomerRef": {"value": "55", "name": "Remote Co"},
        "EmailStatus": "EmailSent",
        "TxnDate": "2026-05-02",
    }]
    body = admin_client.post("/api/v1/sync/quickbooks").json()
    assert body["invoice_activity_rows"] == 1

    act = admin_client.get("/api/v1/activity/recent-invoices").json()
    assert act[0]["invoice_number"] == "VNG-9001"
    assert act[0]["email_status"] == "EmailSent"
    assert act[0]["customer_display_name"] == "Remote Co"


# ── Webhook ───────────────────────────────────────────────────────────────────

def test_webhook_creates_customer_as_approved(client, fake_qbo):
    fake_qbo.customers = [{
        "Id": "77",
        "DisplayName": "Hook Inc",
        "SyncToken": "0",
        "MetaData": {"LastUpdatedTime": "2026-04-01T08:00:00+00:00"},
    }]
    r = client.post("/api/v1/webhooks/intuit", json={
        "eventNotifications": [{
            "dataChangeEvent": {
                "entities": [{"name": "Customer", "id": "77", "operation": "Create"}]
            }
        }]
    })
    assert r.status_code == 200
    assert r.json()["processed"] == 1

    from app.db.session import SessionLocal
    from app.models.customer import Customer, CustomerStatus
    db = SessionLocal()
    row = db.query(Customer).filter(Customer.qbo_id == "77").first()
    assert row is not None
    assert row.status == CustomerStatus.approved
    db.close()


def test_webhook_invoice_entity_processed(client):
    # Invoice events are now processed (upserted into generated_invoices)
    r = client.post("/api/v1/webhooks/intuit", json={
        "eventNotifications": [{
            "dataChangeEvent": {
                "entities": [{"name": "Invoice", "id": "1", "operation": "Create"}]
            }
        }]
    })
    assert r.status_code == 200
    assert r.json()["processed"] == 1


def test_webhook_unknown_entity_ignored(client):
    r = client.post("/api/v1/webhooks/intuit", json={
        "eventNotifications": [{
            "dataChangeEvent": {
                "entities": [{"name": "Payment", "id": "1", "operation": "Create"}]
            }
        }]
    })
    assert r.status_code == 200
    assert r.json()["processed"] == 0


# ── Extra fields ──────────────────────────────────────────────────────────────

def test_add_attachment_in_mail_defaults_false(admin_client):
    r = admin_client.post("/api/v1/customers", json={"display_name": "Simple Co"})
    assert r.status_code == 200
    assert r.json()["add_attachment_in_mail"] is False


def test_add_attachment_in_mail_true_persisted(admin_client):
    r = admin_client.post("/api/v1/customers", json={
        "display_name": "Attach Co", "add_attachment_in_mail": True
    })
    assert r.status_code == 200
    assert r.json()["add_attachment_in_mail"] is True


# ── Customer file attachments (local + QBO) ───────────────────────────────────

def test_upload_attachment_persists_lists_and_downloads(admin_client, fake_qbo):
    cid = admin_client.post("/api/v1/customers", json=_BASE).json()["id"]
    files = [("files", ("doc.pdf", b"%PDF-1.4 hello", "application/pdf"))]
    up = admin_client.post(f"/api/v1/customers/{cid}/attachments", files=files)
    assert up.status_code == 200, up.text
    data = up.json()
    assert len(data["attachments"]) == 1
    assert data["attachments"][0]["original_filename"] == "doc.pdf"
    assert data["attachments"][0]["qbo_attachable_id"] == "att-1"
    assert data["errors"] == []

    lst = admin_client.get(f"/api/v1/customers/{cid}/attachments")
    assert lst.status_code == 200
    assert len(lst.json()) == 1
    aid = lst.json()[0]["id"]

    dl = admin_client.get(f"/api/v1/customers/{cid}/attachments/{aid}/file")
    assert dl.status_code == 200
    assert dl.content == b"%PDF-1.4 hello"


def test_supervisor_can_upload_own_customer_attachment(supervisor_client, admin_client, fake_qbo):
    cid = supervisor_client.post("/api/v1/customers", json=_BASE).json()["id"]
    admin_client.post(f"/api/v1/customers/{cid}/approve", json={"action": "approve"})
    files = [("files", ("a.txt", b"hi", "text/plain"))]
    r = supervisor_client.post(f"/api/v1/customers/{cid}/attachments", files=files)
    assert r.status_code == 200
    assert len(r.json()["attachments"]) == 1


def test_supervisor_cannot_access_others_customer_attachments(admin_client, supervisor_client, fake_qbo):
    cid = admin_client.post("/api/v1/customers", json={**_BASE, "display_name": "Admin Only Co"}).json()["id"]
    assert supervisor_client.get(f"/api/v1/customers/{cid}/attachments").status_code == 403


def test_sync_prunes_local_attachments_when_removed_from_quickbooks(admin_client, fake_qbo):
    cid = admin_client.post("/api/v1/customers", json=_BASE).json()["id"]
    qbo_id = admin_client.get(f"/api/v1/customers/{cid}").json()["qbo_id"]
    assert qbo_id
    files = [("files", ("gone.pdf", b"x", "application/pdf"))]
    assert admin_client.post(f"/api/v1/customers/{cid}/attachments", files=files).status_code == 200
    assert len(admin_client.get(f"/api/v1/customers/{cid}/attachments").json()) == 1

    # Simulate user deleting the attachment in QuickBooks only
    fake_qbo.attachables_by_customer[str(qbo_id)] = []

    body = admin_client.post("/api/v1/sync/quickbooks").json()
    assert body.get("attachments_pruned") == 1
    assert admin_client.get(f"/api/v1/customers/{cid}/attachments").json() == []


def test_sync_upserts_and_prunes_qbo_items(admin_client, fake_qbo):
    fake_qbo.items = [
        {"Id": "1", "Name": "Alpha", "Type": "Service", "Active": True, "SyncToken": "0"},
        {"Id": "2", "Name": "Beta", "Type": "Service", "Active": True, "SyncToken": "0"},
    ]
    r1 = admin_client.post("/api/v1/sync/quickbooks")
    assert r1.status_code == 200
    b1 = r1.json()
    assert b1["items_upserted"] == 2
    assert b1["items_removed_local"] == 0

    products = admin_client.get("/api/v1/product-and-services").json()
    assert len(products) == 2
    names = {p["name"] for p in products}
    assert names == {"Alpha", "Beta"}

    fake_qbo.items = [
        {"Id": "1", "Name": "Alpha Renamed", "Type": "Service", "Active": True, "SyncToken": "1"},
    ]
    r2 = admin_client.post("/api/v1/sync/quickbooks")
    assert r2.status_code == 200
    b2 = r2.json()
    assert b2["items_upserted"] == 1
    assert b2["items_removed_local"] == 1

    products2 = admin_client.get("/api/v1/product-and-services").json()
    assert len(products2) == 1
    assert products2[0]["name"] == "Alpha Renamed"


def test_customer_create_with_services(admin_client, db_session, fake_qbo):
    from app.models.service_code import ServiceCode
    sc = ServiceCode(code="TEST-SC", status=True)
    db_session.add(sc)
    db_session.commit()
    db_session.refresh(sc)

    fake_qbo.items = [{"Id": "10", "Name": "Widget", "Type": "Service", "Active": True, "SyncToken": "0"}]
    admin_client.post("/api/v1/sync/quickbooks")
    pid = admin_client.get("/api/v1/product-and-services").json()[0]["id"]

    r = admin_client.post(
        "/api/v1/customers",
        json={**_BASE, "display_name": "Linked Co", "customer_services": [
            {"product_and_service_id": pid, "service_code_id": sc.id, "rate": "25.00"}
        ]},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["customer_services"]) == 1
    assert data["customer_services"][0]["product_and_service_id"] == pid
    assert float(data["customer_services"][0]["rate"]) == 25.0


def test_customer_invalid_service_code_rejected(admin_client, fake_qbo):
    fake_qbo.items = [{"Id": "11", "Name": "Gadget", "Type": "Service", "Active": True, "SyncToken": "0"}]
    admin_client.post("/api/v1/sync/quickbooks")
    pid = admin_client.get("/api/v1/product-and-services").json()[0]["id"]

    r = admin_client.post(
        "/api/v1/customers",
        json={**_BASE, "display_name": "Bad SC Co", "customer_services": [
            {"product_and_service_id": pid, "service_code_id": 99999, "rate": "10.00"}
        ]},
    )
    assert r.status_code == 422


def test_qbo_customer_payload_excludes_app_service_links():
    from app.models.customer import Customer
    from app.services.qbo_client import customer_model_to_qbo_payload

    row = Customer(display_name="X Co", add_attachment_in_mail=False)
    payload = customer_model_to_qbo_payload(row)
    assert "customer_services" not in payload
    assert "Item" not in payload
