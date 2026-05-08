"""Tests for service codes CRUD."""

from app.models.customer import Customer, CustomerStatus
from app.models.customer_product_and_service import CustomerProductAndService
from app.models.product_and_service import ProductAndService
from app.models.service_code import ServiceCode


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_service_code(db, code: str, status: bool = True) -> ServiceCode:
    sc = ServiceCode(code=code, status=status)
    db.add(sc)
    db.commit()
    db.refresh(sc)
    return sc


def _make_product(db, name: str) -> ProductAndService:
    ps = ProductAndService(qbo_id=f"qbo-{name}", name=name, active=True)
    db.add(ps)
    db.commit()
    db.refresh(ps)
    return ps


def _make_customer(db, display_name: str) -> Customer:
    from decimal import Decimal
    c = Customer(
        display_name=display_name,
        status=CustomerStatus.approved,
        ship_same_as_billing=True,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _assign_service(db, customer: Customer, ps: ProductAndService, sc: ServiceCode) -> None:
    from decimal import Decimal
    cps = CustomerProductAndService(
        customer_id=customer.id,
        product_and_service_id=ps.id,
        service_code_id=sc.id,
        rate=Decimal("10.00"),
    )
    db.add(cps)
    db.commit()


# ── List ──────────────────────────────────────────────────────────────────────

def test_list_service_codes_empty(admin_client):
    r = admin_client.get("/api/v1/service-codes")
    assert r.status_code == 200
    assert r.json() == []


def test_list_service_codes_sorted_by_code(admin_client, db_session):
    _make_service_code(db_session, "Z-CODE")
    _make_service_code(db_session, "A-CODE")
    _make_service_code(db_session, "M-CODE")

    r = admin_client.get("/api/v1/service-codes")
    assert r.status_code == 200
    codes = [sc["code"] for sc in r.json()]
    assert codes == ["A-CODE", "M-CODE", "Z-CODE"]


# ── Create ────────────────────────────────────────────────────────────────────

def test_create_service_code_success(admin_client):
    r = admin_client.post("/api/v1/service-codes", json={"code": "NEW-001"})
    assert r.status_code == 201
    data = r.json()
    assert data["code"] == "NEW-001"
    assert data["status"] is True
    assert "id" in data


def test_create_service_code_duplicate_rejected(admin_client, db_session):
    _make_service_code(db_session, "DUP-001")
    r = admin_client.post("/api/v1/service-codes", json={"code": "DUP-001"})
    assert r.status_code == 409


def test_create_service_code_requires_admin(supervisor_client):
    r = supervisor_client.post("/api/v1/service-codes", json={"code": "SC-X"})
    assert r.status_code == 403


def test_supervisor_can_list_service_codes(supervisor_client, db_session):
    _make_service_code(db_session, "LIST-001")
    r = supervisor_client.get("/api/v1/service-codes")
    assert r.status_code == 200
    assert len(r.json()) == 1


# ── Patch ─────────────────────────────────────────────────────────────────────

def test_patch_service_code_name(admin_client, db_session):
    sc = _make_service_code(db_session, "OLD-CODE")
    r = admin_client.patch(f"/api/v1/service-codes/{sc.id}", json={"code": "NEW-CODE"})
    assert r.status_code == 200
    assert r.json()["code"] == "NEW-CODE"


def test_patch_service_code_status(admin_client, db_session):
    sc = _make_service_code(db_session, "ACTIVE-CODE", status=True)
    r = admin_client.patch(f"/api/v1/service-codes/{sc.id}", json={"status": False})
    assert r.status_code == 200
    assert r.json()["status"] is False


def test_patch_service_code_duplicate_rejected(admin_client, db_session):
    _make_service_code(db_session, "CODE-A")
    sc_b = _make_service_code(db_session, "CODE-B")
    r = admin_client.patch(f"/api/v1/service-codes/{sc_b.id}", json={"code": "CODE-A"})
    assert r.status_code == 409


def test_patch_service_code_404(admin_client):
    r = admin_client.patch("/api/v1/service-codes/99999", json={"code": "X"})
    assert r.status_code == 404


def test_patch_service_code_requires_admin(supervisor_client, db_session):
    sc = _make_service_code(db_session, "SC-PATCH")
    r = supervisor_client.patch(f"/api/v1/service-codes/{sc.id}", json={"code": "X"})
    assert r.status_code == 403


# ── Delete ────────────────────────────────────────────────────────────────────

def test_delete_service_code_unassigned_allowed(admin_client, db_session):
    sc = _make_service_code(db_session, "UNASSIGNED")
    r = admin_client.delete(f"/api/v1/service-codes/{sc.id}")
    assert r.status_code == 204


def test_delete_service_code_assigned_blocked(admin_client, db_session):
    sc = _make_service_code(db_session, "ASSIGNED")
    ps = _make_product(db_session, "Gardening")
    customer = _make_customer(db_session, "Test Customer")
    _assign_service(db_session, customer, ps, sc)

    r = admin_client.delete(f"/api/v1/service-codes/{sc.id}")
    assert r.status_code == 409
    assert "assigned" in r.json()["detail"].lower()


def test_delete_service_code_404(admin_client):
    r = admin_client.delete("/api/v1/service-codes/99999")
    assert r.status_code == 404


def test_delete_service_code_requires_admin(supervisor_client, db_session):
    sc = _make_service_code(db_session, "SC-DEL")
    r = supervisor_client.delete(f"/api/v1/service-codes/{sc.id}")
    assert r.status_code == 403


# ── Customer integration ──────────────────────────────────────────────────────

def test_create_customer_with_services(admin_client, db_session):
    sc = _make_service_code(db_session, "SVC-001")
    ps = _make_product(db_session, "Gardening")

    r = admin_client.post("/api/v1/customers", json={
        "display_name": "Service Customer",
        "customer_services": [
            {"product_and_service_id": ps.id, "service_code_id": sc.id, "rate": "15.00"}
        ],
    })
    assert r.status_code == 200
    data = r.json()
    assert len(data["customer_services"]) == 1
    svc = data["customer_services"][0]
    assert svc["product_and_service_id"] == ps.id
    assert svc["service_code_id"] == sc.id
    assert float(svc["rate"]) == 15.00


def test_customer_services_returned_in_list(admin_client, db_session):
    sc = _make_service_code(db_session, "SVC-002")
    ps = _make_product(db_session, "Cleaning")
    customer = _make_customer(db_session, "Listed Customer")
    _assign_service(db_session, customer, ps, sc)

    r = admin_client.get("/api/v1/customers")
    assert r.status_code == 200
    customers = r.json()
    target = next(c for c in customers if c["display_name"] == "Listed Customer")
    assert len(target["customer_services"]) == 1
    assert target["customer_services"][0]["service_code_id"] == sc.id


def test_update_customer_services(admin_client, db_session):
    sc1 = _make_service_code(db_session, "SVC-003")
    sc2 = _make_service_code(db_session, "SVC-004")
    ps1 = _make_product(db_session, "Pruning")
    ps2 = _make_product(db_session, "Mowing")
    customer = _make_customer(db_session, "Update Service Customer")
    _assign_service(db_session, customer, ps1, sc1)

    r = admin_client.patch(f"/api/v1/customers/{customer.id}", json={
        "customer_services": [
            {"product_and_service_id": ps2.id, "service_code_id": sc2.id, "rate": "20.00"}
        ]
    })
    assert r.status_code == 200
    data = r.json()
    assert len(data["customer_services"]) == 1
    assert data["customer_services"][0]["product_and_service_id"] == ps2.id


def test_clear_customer_services(admin_client, db_session):
    sc = _make_service_code(db_session, "SVC-005")
    ps = _make_product(db_session, "Fencing")
    customer = _make_customer(db_session, "Clear Service Customer")
    _assign_service(db_session, customer, ps, sc)

    r = admin_client.patch(f"/api/v1/customers/{customer.id}", json={"customer_services": []})
    assert r.status_code == 200
    assert r.json()["customer_services"] == []


def test_duplicate_service_per_customer_rejected(admin_client, db_session):
    sc = _make_service_code(db_session, "SVC-006")
    ps = _make_product(db_session, "Weeding")

    r = admin_client.post("/api/v1/customers", json={
        "display_name": "Dup Service Customer",
        "customer_services": [
            {"product_and_service_id": ps.id, "service_code_id": sc.id, "rate": "10.00"},
            {"product_and_service_id": ps.id, "service_code_id": sc.id, "rate": "20.00"},
        ],
    })
    assert r.status_code == 422


def test_invalid_service_code_id_rejected(admin_client, db_session):
    ps = _make_product(db_session, "Trimming")

    r = admin_client.post("/api/v1/customers", json={
        "display_name": "Bad SC Customer",
        "customer_services": [
            {"product_and_service_id": ps.id, "service_code_id": 99999, "rate": "10.00"}
        ],
    })
    assert r.status_code == 422


def test_invalid_product_id_rejected(admin_client, db_session):
    sc = _make_service_code(db_session, "SVC-007")

    r = admin_client.post("/api/v1/customers", json={
        "display_name": "Bad PS Customer",
        "customer_services": [
            {"product_and_service_id": 99999, "service_code_id": sc.id, "rate": "10.00"}
        ],
    })
    assert r.status_code == 422


def test_zero_rate_rejected(admin_client, db_session):
    sc = _make_service_code(db_session, "SVC-008")
    ps = _make_product(db_session, "Raking")

    r = admin_client.post("/api/v1/customers", json={
        "display_name": "Zero Rate Customer",
        "customer_services": [
            {"product_and_service_id": ps.id, "service_code_id": sc.id, "rate": "0"}
        ],
    })
    assert r.status_code == 422


def test_negative_rate_rejected(admin_client, db_session):
    sc = _make_service_code(db_session, "SVC-009")
    ps = _make_product(db_session, "Planting")

    r = admin_client.post("/api/v1/customers", json={
        "display_name": "Neg Rate Customer",
        "customer_services": [
            {"product_and_service_id": ps.id, "service_code_id": sc.id, "rate": "-5.00"}
        ],
    })
    assert r.status_code == 422
