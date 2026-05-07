"""Centers per company (customer) and invoice ↔ center grouping."""

import pytest
from sqlalchemy import select

from app.models.center import Center
from app.models.invoice import Invoice, invoice_centers

_MIN_CUSTOMER = {
    "display_name": "Centers Test Co",
    "rate": "10",
    "ship_same_as_billing": True,
}


def _create_customer(client):
    r = client.post("/api/v1/customers", json=_MIN_CUSTOMER)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_add_one_center(admin_client):
    cid = _create_customer(admin_client)
    r = admin_client.post(f"/api/v1/customers/{cid}/centers", json={"name": "  Alpha  "})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["name"] == "Alpha"
    assert data["company_id"] == cid


def test_add_multiple_centers_list_and_display(admin_client):
    cid = _create_customer(admin_client)
    for name in ("A", "B", "C"):
        assert admin_client.post(f"/api/v1/customers/{cid}/centers", json={"name": name}).status_code == 200
    rows = admin_client.get(f"/api/v1/customers/{cid}/centers").json()
    assert [x["name"] for x in rows] == ["A", "B", "C"]


def test_centers_persisted_in_db(admin_client, db_session):
    cid = _create_customer(admin_client)
    admin_client.post(f"/api/v1/customers/{cid}/centers", json={"name": "Store 1"})
    row = db_session.query(Center).filter(Center.company_id == cid).one()
    assert row.name == "Store 1"


def test_invoice_single_center(admin_client, db_session):
    cid = _create_customer(admin_client)
    ca = admin_client.post(f"/api/v1/customers/{cid}/centers", json={"name": "Only"}).json()
    r = admin_client.post(
        "/api/v1/invoices",
        json={"company_id": cid, "center_ids": [ca["id"]], "title": "Solo"},
    )
    assert r.status_code == 200, r.text
    inv = r.json()
    assert inv["center_ids"] == [ca["id"]]
    db_inv = db_session.get(Invoice, inv["id"])
    assert db_inv is not None
    assert [c.id for c in db_inv.centers] == [ca["id"]]


def test_invoice_multiple_centers_combined(admin_client):
    cid = _create_customer(admin_client)
    a = admin_client.post(f"/api/v1/customers/{cid}/centers", json={"name": "A"}).json()
    b = admin_client.post(f"/api/v1/customers/{cid}/centers", json={"name": "B"}).json()
    c = admin_client.post(f"/api/v1/customers/{cid}/centers", json={"name": "C"}).json()
    r = admin_client.post(
        "/api/v1/invoices",
        json={"company_id": cid, "center_ids": [a["id"], c["id"]], "title": "A+C"},
    )
    assert r.status_code == 200, r.text
    ids = sorted(r.json()["center_ids"])
    assert ids == sorted([a["id"], c["id"]])
    assert b["id"] not in r.json()["center_ids"]


def test_after_a_and_b_grouped_a_with_c_rejected_c_alone_ok(admin_client):
    cid = _create_customer(admin_client)
    a = admin_client.post(f"/api/v1/customers/{cid}/centers", json={"name": "A"}).json()
    b = admin_client.post(f"/api/v1/customers/{cid}/centers", json={"name": "B"}).json()
    c_row = admin_client.post(f"/api/v1/customers/{cid}/centers", json={"name": "C"}).json()
    r_ab = admin_client.post(
        "/api/v1/invoices",
        json={"company_id": cid, "center_ids": [a["id"], b["id"]], "title": "A+B"},
    )
    assert r_ab.status_code == 200, r_ab.text
    r_ac = admin_client.post(
        "/api/v1/invoices",
        json={"company_id": cid, "center_ids": [a["id"], c_row["id"]], "title": "A+C"},
    )
    assert r_ac.status_code == 422
    r_c = admin_client.post(
        "/api/v1/invoices",
        json={"company_id": cid, "center_ids": [c_row["id"]], "title": "C only"},
    )
    assert r_c.status_code == 200, r_c.text


def test_cannot_reuse_center_on_second_grouping(admin_client):
    cid = _create_customer(admin_client)
    c = admin_client.post(f"/api/v1/customers/{cid}/centers", json={"name": "Shared"}).json()
    r1 = admin_client.post("/api/v1/invoices", json={"company_id": cid, "center_ids": [c["id"]], "title": "I1"})
    assert r1.status_code == 200
    r2 = admin_client.post("/api/v1/invoices", json={"company_id": cid, "center_ids": [c["id"]], "title": "I2"})
    assert r2.status_code == 422


def test_patch_removing_center_allows_new_grouping_with_that_center(admin_client):
    cid = _create_customer(admin_client)
    a = admin_client.post(f"/api/v1/customers/{cid}/centers", json={"name": "A"}).json()
    b = admin_client.post(f"/api/v1/customers/{cid}/centers", json={"name": "B"}).json()
    c_row = admin_client.post(f"/api/v1/customers/{cid}/centers", json={"name": "C"}).json()
    inv_ab = admin_client.post(
        "/api/v1/invoices",
        json={"company_id": cid, "center_ids": [a["id"], b["id"]]},
    ).json()
    r_patch = admin_client.patch(
        f"/api/v1/invoices/{inv_ab['id']}",
        json={"center_ids": [b["id"]]},
    )
    assert r_patch.status_code == 200, r_patch.text
    r_ac = admin_client.post(
        "/api/v1/invoices",
        json={"company_id": cid, "center_ids": [a["id"], c_row["id"]], "title": "A+C"},
    )
    assert r_ac.status_code == 200, r_ac.text


def test_invoice_center_join_rows(admin_client, db_session):
    cid = _create_customer(admin_client)
    a = admin_client.post(f"/api/v1/customers/{cid}/centers", json={"name": "X"}).json()
    b = admin_client.post(f"/api/v1/customers/{cid}/centers", json={"name": "Y"}).json()
    inv = admin_client.post(
        "/api/v1/invoices",
        json={"company_id": cid, "center_ids": [a["id"], b["id"]], "title": None},
    ).json()
    iid = inv["id"]
    pairs = db_session.execute(
        select(invoice_centers.c.invoice_id, invoice_centers.c.center_id).where(
            invoice_centers.c.invoice_id == iid
        )
    ).all()
    assert sorted(p[1] for p in pairs) == sorted([a["id"], b["id"]])


def test_invoice_rejects_center_from_other_company(admin_client):
    c1 = _create_customer(admin_client)
    c2 = _create_customer(admin_client)
    ca = admin_client.post(f"/api/v1/customers/{c1}/centers", json={"name": "Mine"}).json()
    other = admin_client.post(f"/api/v1/customers/{c2}/centers", json={"name": "Theirs"}).json()
    r = admin_client.post(
        "/api/v1/invoices",
        json={"company_id": c1, "center_ids": [ca["id"], other["id"]], "title": "bad"},
    )
    assert r.status_code == 422


def test_supervisor_cannot_add_center_to_foreign_customer(supervisor_client, admin_client):
    cid = _create_customer(admin_client)
    r = supervisor_client.post(f"/api/v1/customers/{cid}/centers", json={"name": "Nope"})
    assert r.status_code == 403


def test_supervisor_invoice_only_visible_for_own_customer(supervisor_client, admin_client):
    """Supervisor listing excludes invoice groupings for companies they did not create."""
    sup_cid = supervisor_client.post("/api/v1/customers", json={**_MIN_CUSTOMER, "display_name": "Sup Co"}).json()[
        "id"
    ]
    cen = supervisor_client.post(f"/api/v1/customers/{sup_cid}/centers", json={"name": "S1"}).json()
    supervisor_client.post(
        "/api/v1/invoices", json={"company_id": sup_cid, "center_ids": [cen["id"]], "title": "t"}
    )

    adm_cid = _create_customer(admin_client)
    ac = admin_client.post(f"/api/v1/customers/{adm_cid}/centers", json={"name": "A1"}).json()
    admin_client.post("/api/v1/invoices", json={"company_id": adm_cid, "center_ids": [ac["id"]], "title": "adm"})

    rows = supervisor_client.get("/api/v1/invoices").json()
    assert len(rows) == 1
    assert rows[0]["company_id"] == sup_cid
