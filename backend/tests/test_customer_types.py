"""Tests for customer type CRUD and customer type assignment."""

import pytest
from fastapi.testclient import TestClient

from conftest import make_user, token_for
from app.db.session import SessionLocal
from app.models.customer import Customer, CustomerStatus
from app.models.customer_type import CustomerType
from app.models.user import UserRole


# ── helpers ───────────────────────────────────────────────────────────────────

def _create_type(client: TestClient, name: str) -> dict:
    r = client.post("/api/v1/customer-types", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


def _make_approved_customer(db, admin_user) -> Customer:
    from app.services.customer_service import create_customer_row
    from app.schemas.customer import CustomerCreate
    row = create_customer_row(
        db,
        CustomerCreate(display_name="Approved Co"),
        created_by_id=admin_user.id,
    )
    row.status = CustomerStatus.approved
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ── list ──────────────────────────────────────────────────────────────────────

def test_list_customer_types_empty(admin_client: TestClient):
    r = admin_client.get("/api/v1/customer-types")
    assert r.status_code == 200
    assert r.json() == []


def test_list_customer_types_sorted(admin_client: TestClient):
    _create_type(admin_client, "Zebra")
    _create_type(admin_client, "Alpha")
    r = admin_client.get("/api/v1/customer-types")
    assert r.status_code == 200
    names = [ct["name"] for ct in r.json()]
    assert names == ["Alpha", "Zebra"]


# ── create ────────────────────────────────────────────────────────────────────

def test_create_customer_type(admin_client: TestClient):
    r = admin_client.post("/api/v1/customer-types", json={"name": "Gold"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Gold"
    assert data["status"] is True
    assert "id" in data
    assert "created_at" in data


def test_create_duplicate_name_rejected(admin_client: TestClient):
    _create_type(admin_client, "Gold")
    r = admin_client.post("/api/v1/customer-types", json={"name": "Gold"})
    assert r.status_code == 409


def test_create_requires_admin(supervisor_client: TestClient):
    r = supervisor_client.post("/api/v1/customer-types", json={"name": "Gold"})
    assert r.status_code == 403


# ── update ────────────────────────────────────────────────────────────────────

def test_patch_name(admin_client: TestClient):
    ct = _create_type(admin_client, "Old Name")
    r = admin_client.patch(f"/api/v1/customer-types/{ct['id']}", json={"name": "New Name"})
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"


def test_patch_status_deactivate(admin_client: TestClient):
    ct = _create_type(admin_client, "Active Type")
    r = admin_client.patch(f"/api/v1/customer-types/{ct['id']}", json={"status": False})
    assert r.status_code == 200
    assert r.json()["status"] is False


def test_patch_duplicate_name_rejected(admin_client: TestClient):
    _create_type(admin_client, "A")
    ct_b = _create_type(admin_client, "B")
    r = admin_client.patch(f"/api/v1/customer-types/{ct_b['id']}", json={"name": "A"})
    assert r.status_code == 409


def test_patch_404(admin_client: TestClient):
    r = admin_client.patch("/api/v1/customer-types/99999", json={"name": "X"})
    assert r.status_code == 404


def test_patch_requires_admin(supervisor_client: TestClient, admin_client: TestClient):
    ct = _create_type(admin_client, "Type")
    r = supervisor_client.patch(f"/api/v1/customer-types/{ct['id']}", json={"name": "Y"})
    assert r.status_code == 403


# ── delete ────────────────────────────────────────────────────────────────────

def test_delete_unassigned_type(admin_client: TestClient):
    ct = _create_type(admin_client, "Unused")
    r = admin_client.delete(f"/api/v1/customer-types/{ct['id']}")
    assert r.status_code == 204
    r2 = admin_client.get("/api/v1/customer-types")
    assert all(c["id"] != ct["id"] for c in r2.json())


def test_delete_type_assigned_to_approved_customer_blocked(
    admin_client: TestClient,
    admin_user,
    db_session,
):
    ct = _create_type(admin_client, "Blocked Type")
    customer = _make_approved_customer(db_session, admin_user)

    # Assign the type via PATCH on customer
    r = admin_client.patch(
        f"/api/v1/customers/{customer.id}",
        json={"customer_type_ids": [ct["id"]]},
    )
    assert r.status_code == 200

    r2 = admin_client.delete(f"/api/v1/customer-types/{ct['id']}")
    assert r2.status_code == 409
    assert "approved" in r2.json()["detail"].lower()


def test_delete_type_assigned_to_pending_customer_allowed(
    admin_client: TestClient,
    admin_user,
    db_session,
):
    ct = _create_type(admin_client, "Pending Type")

    from app.services.customer_service import create_customer_row
    from app.schemas.customer import CustomerCreate
    pending = create_customer_row(
        db_session,
        CustomerCreate(display_name="Pending Co", customer_type_ids=[ct["id"]]),
        created_by_id=admin_user.id,
    )
    assert pending.status == CustomerStatus.pending

    r = admin_client.delete(f"/api/v1/customer-types/{ct['id']}")
    assert r.status_code == 204


def test_delete_404(admin_client: TestClient):
    r = admin_client.delete("/api/v1/customer-types/99999")
    assert r.status_code == 404


def test_delete_requires_admin(supervisor_client: TestClient, admin_client: TestClient):
    ct = _create_type(admin_client, "Type")
    r = supervisor_client.delete(f"/api/v1/customer-types/{ct['id']}")
    assert r.status_code == 403


# ── customer assignment ───────────────────────────────────────────────────────

def test_create_customer_with_type_ids(admin_client: TestClient):
    ct1 = _create_type(admin_client, "Gold")
    ct2 = _create_type(admin_client, "Silver")
    r = admin_client.post(
        "/api/v1/customers",
        json={"display_name": "Widget Corp", "customer_type_ids": [ct1["id"], ct2["id"]]},
    )
    assert r.status_code == 200
    ids = r.json()["customer_type_ids"]
    assert set(ids) == {ct1["id"], ct2["id"]}


def test_customer_type_ids_returned_in_list(admin_client: TestClient):
    ct = _create_type(admin_client, "Platinum")
    admin_client.post(
        "/api/v1/customers",
        json={"display_name": "Listed Co", "customer_type_ids": [ct["id"]]},
    )
    rows = admin_client.get("/api/v1/customers").json()
    target = next(c for c in rows if c["display_name"] == "Listed Co")
    assert ct["id"] in target["customer_type_ids"]


def test_update_customer_type_ids(admin_client: TestClient):
    ct1 = _create_type(admin_client, "Bronze")
    ct2 = _create_type(admin_client, "Diamond")
    r = admin_client.post(
        "/api/v1/customers",
        json={"display_name": "Changeable Co", "customer_type_ids": [ct1["id"]]},
    )
    cid = r.json()["id"]

    r2 = admin_client.patch(
        f"/api/v1/customers/{cid}",
        json={"customer_type_ids": [ct2["id"]]},
    )
    assert r2.status_code == 200
    assert r2.json()["customer_type_ids"] == [ct2["id"]]


def test_clear_customer_type_ids(admin_client: TestClient):
    ct = _create_type(admin_client, "Temp")
    r = admin_client.post(
        "/api/v1/customers",
        json={"display_name": "Clearable Co", "customer_type_ids": [ct["id"]]},
    )
    cid = r.json()["id"]
    r2 = admin_client.patch(f"/api/v1/customers/{cid}", json={"customer_type_ids": []})
    assert r2.status_code == 200
    assert r2.json()["customer_type_ids"] == []


def test_invalid_customer_type_id_rejected(admin_client: TestClient):
    r = admin_client.post(
        "/api/v1/customers",
        json={"display_name": "Bad Co", "customer_type_ids": [99999]},
    )
    assert r.status_code == 422
