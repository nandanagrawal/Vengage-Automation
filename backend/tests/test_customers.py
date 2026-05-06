"""Customer module tests: creation, approval workflow, QBO sync, webhooks, field validation."""

import pytest

from tests.conftest import token_for
from app.models.user import UserRole

_BASE = {
    "display_name": "Test Labs",
    "primary_email": "billing@testlabs.example",
    "given_name": "Sam",
    "family_name": "Rivera",
    "rate": "125.50",
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
    assert float(data["rate"]) == pytest.approx(125.5)
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


# ── Rate field validation ─────────────────────────────────────────────────────

def test_negative_rate_rejected(admin_client):
    assert admin_client.post("/api/v1/customers", json={**_BASE, "rate": "-1"}).status_code == 422


def test_zero_rate_allowed(admin_client):
    r = admin_client.post("/api/v1/customers", json={**_BASE, "rate": "0"})
    assert r.status_code == 200
    assert float(r.json()["rate"]) == 0.0


def test_high_precision_rate(admin_client):
    r = admin_client.post("/api/v1/customers", json={**_BASE, "rate": "999.9999"})
    assert r.status_code == 200
    assert float(r.json()["rate"]) == pytest.approx(999.9999, rel=1e-4)


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


def test_webhook_non_customer_entity_ignored(client):
    r = client.post("/api/v1/webhooks/intuit", json={
        "eventNotifications": [{
            "dataChangeEvent": {
                "entities": [{"name": "Invoice", "id": "1", "operation": "Create"}]
            }
        }]
    })
    assert r.status_code == 200
    assert r.json()["processed"] == 0


# ── Extra fields ──────────────────────────────────────────────────────────────

def test_add_attachment_in_mail_defaults_false(admin_client):
    r = admin_client.post("/api/v1/customers", json={"display_name": "Simple Co", "rate": "0"})
    assert r.status_code == 200
    assert r.json()["add_attachment_in_mail"] is False


def test_add_attachment_in_mail_true_persisted(admin_client):
    r = admin_client.post("/api/v1/customers", json={
        "display_name": "Attach Co", "rate": "10", "add_attachment_in_mail": True
    })
    assert r.status_code == 200
    assert r.json()["add_attachment_in_mail"] is True
