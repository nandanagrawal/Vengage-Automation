"""Tests for XLS/CSV upload and invoice generation flow."""

import csv
import io
from decimal import Decimal

import pytest

from app.models.center import Center
from app.models.customer import Customer, CustomerStatus
from app.models.customer_product_and_service import CustomerProductAndService
from app.models.invoice import Invoice
from app.models.product_and_service import ProductAndService
from app.models.service_code import ServiceCode
from app.models.user import UserRole
from app.services.invoice_generation import (
    GenerationResult,
    generate_invoices,
    parse_csv,
    parse_spreadsheet,
    parse_xlsx,
)
from tests.conftest import FakeQBO, make_user


# ── CSV helpers ───────────────────────────────────────────────────────────────

def _make_csv(rows: list[list]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    for r in rows:
        w.writerow(r)
    return buf.getvalue().encode()


def _make_xlsx(rows: list[list]) -> bytes:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── DB helpers ────────────────────────────────────────────────────────────────

def _make_service_code(db, code: str) -> ServiceCode:
    sc = ServiceCode(code=code, status=True)
    db.add(sc)
    db.commit()
    db.refresh(sc)
    return sc


def _make_customer(db, display_name: str, qbo_id: str | None = None, email: str | None = None) -> Customer:
    c = Customer(
        display_name=display_name,
        status=CustomerStatus.approved,
        qbo_id=qbo_id,
        primary_email=email,
        ship_same_as_billing=True,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _make_center(db, company_id: int, name: str) -> Center:
    c = Center(company_id=company_id, name=name)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _make_product(db, name: str, qbo_id: str) -> ProductAndService:
    ps = ProductAndService(
        qbo_id=qbo_id,
        name=name,
        active=True,
    )
    db.add(ps)
    db.commit()
    db.refresh(ps)
    return ps


def _link_service(db, customer: Customer, ps: ProductAndService, sc: ServiceCode, rate: float) -> CustomerProductAndService:
    cps = CustomerProductAndService(
        customer_id=customer.id,
        product_and_service_id=ps.id,
        service_code_id=sc.id,
        rate=Decimal(str(rate)),
    )
    db.add(cps)
    db.commit()
    db.refresh(cps)
    return cps


def _make_grouping(db, company_id: int, centers: list[Center], title: str = "") -> Invoice:
    inv = Invoice(company_id=company_id, title=title or None)
    inv.centers = centers
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


# ── Parsing tests ─────────────────────────────────────────────────────────────

def test_parse_csv_basic():
    content = _make_csv([
        ["S.No. (1)", "Gardening", "Cleaning"],
        ["ac", "5", "3"],
        ["acc", "2", "1"],
    ])
    pf = parse_csv(content)
    assert set(pf.rows.keys()) == {"ac", "acc"}
    assert pf.rows["ac"]["gardening"] == Decimal("5")
    assert pf.rows["ac"]["cleaning"] == Decimal("3")
    assert pf.rows["acc"]["gardening"] == Decimal("2")
    assert pf.product_columns == ["Gardening", "Cleaning"]


def test_parse_csv_empty_quantity_treated_as_zero():
    content = _make_csv([
        ["Center", "Gardening"],
        ["ac", ""],
        ["acc", "0"],
    ])
    pf = parse_csv(content)
    assert pf.rows["ac"]["gardening"] == Decimal("0")
    assert pf.rows["acc"]["gardening"] == Decimal("0")


def test_parse_csv_non_numeric_quantity_skipped():
    content = _make_csv([
        ["Center", "Gardening"],
        ["ac", "abc"],
    ])
    pf = parse_csv(content)
    # non-numeric cell skipped → key absent
    assert "gardening" not in pf.rows["ac"]


def test_parse_csv_duplicate_center_rows_summed():
    content = _make_csv([
        ["Center", "Gardening"],
        ["ac", "3"],
        ["ac", "2"],
    ])
    pf = parse_csv(content)
    assert pf.rows["ac"]["gardening"] == Decimal("5")


def test_parse_xlsx_basic():
    content = _make_xlsx([
        ["S.No. (1)", "Gardening"],
        ["ac", 5],
        ["ad", 2],
    ])
    pf = parse_xlsx(content)
    assert pf.rows["ac"]["gardening"] == Decimal("5")
    assert pf.rows["ad"]["gardening"] == Decimal("2")


def test_parse_spreadsheet_dispatches_by_extension():
    csv_bytes = _make_csv([["Center", "G"], ["x", "1"]])
    pf = parse_spreadsheet("data.csv", csv_bytes)
    assert "x" in pf.rows

    xlsx_bytes = _make_xlsx([["Center", "G"], ["y", 2]])
    pf2 = parse_spreadsheet("data.xlsx", xlsx_bytes)
    assert "y" in pf2.rows


def test_parse_spreadsheet_rejects_unknown_extension():
    with pytest.raises(ValueError, match="Unsupported file type"):
        parse_spreadsheet("data.txt", b"")


def test_parse_csv_empty_file_raises():
    with pytest.raises(ValueError, match="empty"):
        parse_csv(b"")


# ── Generation tests ──────────────────────────────────────────────────────────

def test_no_matching_centers_returns_errors(db_session):
    qbo = FakeQBO()
    csv_bytes = _make_csv([["Center", "Gardening"], ["unknown", "5"]])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)
    assert result.centers_matched == 0
    assert result.centers_skipped == 1
    assert result.invoices_created == 0
    assert any("not found" in e for e in result.errors)


def test_customer_without_qbo_id_skipped(db_session):
    sc = _make_service_code(db_session, "SC-A")
    customer = _make_customer(db_session, "No QBO", qbo_id=None)
    _make_center(db_session, customer.id, "alpha")
    ps = _make_product(db_session, "Gardening", "qbo-g1")
    _link_service(db_session, customer, ps, sc, 10.0)

    qbo = FakeQBO()
    csv_bytes = _make_csv([["Center", "Gardening"], ["alpha", "3"]])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 0
    assert any("no QBO ID" in e for e in result.errors)


def test_rate_from_customer_service_not_product(db_session):
    """Rate must come from CustomerProductAndService.rate, not ProductAndService.unit_price."""
    sc = _make_service_code(db_session, "SC-B")
    customer = _make_customer(db_session, "Rate Co", qbo_id="qbo-c1", email="a@b.com")
    ctr = _make_center(db_session, customer.id, "beta")
    ps = _make_product(db_session, "Gardening", "qbo-g2")
    _link_service(db_session, customer, ps, sc, 7.50)

    qbo = FakeQBO()
    csv_bytes = _make_csv([["Center", "Gardening"], ["beta", "4"]])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    inv = qbo.invoices[0]
    line = inv["Line"][0]
    assert line["SalesItemLineDetail"]["UnitPrice"] == 7.50
    assert line["SalesItemLineDetail"]["Qty"] == 4.0
    assert line["Amount"] == 30.0


def test_zero_rate_skips_line_item(db_session):
    """A CustomerProductAndService with rate=0 should be skipped (shouldn't happen with validation, but guard it)."""
    sc = _make_service_code(db_session, "SC-C")
    customer = _make_customer(db_session, "Zero Rate Co", qbo_id="qbo-c4", email="z@z.com")
    _make_center(db_session, customer.id, "delta")
    ps = _make_product(db_session, "Gardening", "qbo-g5")
    # Insert directly bypassing schema validation to test the guard
    cps = CustomerProductAndService(
        customer_id=customer.id,
        product_and_service_id=ps.id,
        service_code_id=sc.id,
        rate=Decimal("0"),
    )
    db_session.add(cps)
    db_session.commit()

    qbo = FakeQBO()
    csv_bytes = _make_csv([["Center", "Gardening"], ["delta", "5"]])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 0


def test_center_matching_is_case_insensitive(db_session):
    sc = _make_service_code(db_session, "SC-D")
    customer = _make_customer(db_session, "Case Co", qbo_id="qbo-case", email="case@case.com")
    _make_center(db_session, customer.id, "Alpha")
    ps = _make_product(db_session, "Gardening", "qbo-g6")
    _link_service(db_session, customer, ps, sc, 5.0)

    qbo = FakeQBO()
    # "alpha" (lowercase) should match "Alpha" (case-insensitive)
    csv_bytes = _make_csv([["Center", "Gardening"], ["alpha", "3"]])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.centers_matched == 1
    assert result.centers_skipped == 0
    assert result.invoices_created == 1


def test_product_column_matching_is_case_insensitive(db_session):
    """Column 'GARDENING' in file should match product named 'Gardening'."""
    sc = _make_service_code(db_session, "SC-E")
    customer = _make_customer(db_session, "Upper Co", qbo_id="qbo-upper", email="u@u.com")
    _make_center(db_session, customer.id, "epsilon")
    ps = _make_product(db_session, "Gardening", "qbo-g7")
    _link_service(db_session, customer, ps, sc, 10.0)

    qbo = FakeQBO()
    csv_bytes = _make_csv([["Center", "GARDENING"], ["epsilon", "2"]])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1


def test_grouped_centers_single_invoice(db_session):
    """ac + acc grouped → one invoice with summed quantities."""
    sc = _make_service_code(db_session, "SC-F")
    customer = _make_customer(db_session, "Grouped Co", qbo_id="qbo-grp", email="g@g.com")
    ctr_ac = _make_center(db_session, customer.id, "ac")
    ctr_acc = _make_center(db_session, customer.id, "acc")
    _make_grouping(db_session, customer.id, [ctr_ac, ctr_acc])
    ps = _make_product(db_session, "Gardening", "qbo-g8")
    _link_service(db_session, customer, ps, sc, 2.0)

    qbo = FakeQBO()
    csv_bytes = _make_csv([
        ["Center", "Gardening"],
        ["ac", "5"],
        ["acc", "3"],
    ])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    inv = qbo.invoices[0]
    line = inv["Line"][0]
    assert line["SalesItemLineDetail"]["Qty"] == 8.0   # 5 + 3
    assert line["Amount"] == 16.0                      # 8 * 2.0


def test_standalone_center_individual_invoice(db_session):
    """ad not in any grouping → own invoice."""
    sc = _make_service_code(db_session, "SC-G")
    customer = _make_customer(db_session, "Standalone Co", qbo_id="qbo-sa", email="s@s.com")
    _make_center(db_session, customer.id, "ad")
    ps = _make_product(db_session, "Gardening", "qbo-g9")
    _link_service(db_session, customer, ps, sc, 3.0)

    qbo = FakeQBO()
    csv_bytes = _make_csv([["Center", "Gardening"], ["ad", "2"]])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    line = qbo.invoices[0]["Line"][0]
    assert line["SalesItemLineDetail"]["Qty"] == 2.0
    assert line["Amount"] == 6.0


def test_mixed_grouped_and_standalone(db_session):
    """ac+acc grouped, ad standalone → 2 invoices total."""
    sc = _make_service_code(db_session, "SC-H")
    customer = _make_customer(db_session, "Mixed Co", qbo_id="qbo-mix", email="m@m.com")
    ctr_ac = _make_center(db_session, customer.id, "ac2")
    ctr_acc = _make_center(db_session, customer.id, "acc2")
    ctr_ad = _make_center(db_session, customer.id, "ad2")
    _make_grouping(db_session, customer.id, [ctr_ac, ctr_acc])
    ps = _make_product(db_session, "Gardening", "qbo-g10")
    _link_service(db_session, customer, ps, sc, 1.0)

    qbo = FakeQBO()
    csv_bytes = _make_csv([
        ["Center", "Gardening"],
        ["ac2", "5"],
        ["acc2", "3"],
        ["ad2", "2"],
    ])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 2
    # Verify combined group qty = 8, standalone = 2
    qtys = sorted([inv["Line"][0]["SalesItemLineDetail"]["Qty"] for inv in qbo.invoices])
    assert qtys == [2.0, 8.0]


def test_unmatched_product_column_ignored(db_session):
    """Columns not matching any synced product are silently ignored."""
    sc = _make_service_code(db_session, "SC-I")
    customer = _make_customer(db_session, "Extra Col Co", qbo_id="qbo-ec", email="e@e.com")
    _make_center(db_session, customer.id, "zeta")
    ps = _make_product(db_session, "Gardening", "qbo-g11")
    _link_service(db_session, customer, ps, sc, 5.0)

    qbo = FakeQBO()
    # "Unknown Service" has no matching product — should be ignored
    csv_bytes = _make_csv([["Center", "Gardening", "Unknown Service"], ["zeta", "4", "99"]])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    assert len(qbo.invoices[0]["Line"]) == 1  # only Gardening line


def test_customer_without_matching_products_skipped(db_session):
    """Customer whose products don't match any file column → skipped with error."""
    sc = _make_service_code(db_session, "SC-J")
    customer = _make_customer(db_session, "No Match Co", qbo_id="qbo-nm", email="nm@nm.com")
    _make_center(db_session, customer.id, "eta")
    ps = _make_product(db_session, "Plumbing", "qbo-p1")
    _link_service(db_session, customer, ps, sc, 20.0)

    qbo = FakeQBO()
    csv_bytes = _make_csv([["Center", "Gardening"], ["eta", "5"]])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 0
    assert any("no matching product" in e for e in result.errors)


def test_invoice_sent_after_creation(db_session):
    """Invoice must be created and then sent (EmailStatus = EmailSent in FakeQBO)."""
    sc = _make_service_code(db_session, "SC-K")
    customer = _make_customer(db_session, "Send Co", qbo_id="qbo-send", email="send@send.com")
    _make_center(db_session, customer.id, "theta")
    ps = _make_product(db_session, "Gardening", "qbo-g12")
    _link_service(db_session, customer, ps, sc, 5.0)

    qbo = FakeQBO()
    csv_bytes = _make_csv([["Center", "Gardening"], ["theta", "1"]])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    assert result.invoice_details[0].sent is True
    assert qbo.invoices[0]["EmailStatus"] == "EmailSent"


def test_zero_quantity_produces_no_invoice(db_session):
    sc = _make_service_code(db_session, "SC-L")
    customer = _make_customer(db_session, "Zero Qty Co", qbo_id="qbo-zq", email="zq@zq.com")
    _make_center(db_session, customer.id, "iota")
    ps = _make_product(db_session, "Gardening", "qbo-g13")
    _link_service(db_session, customer, ps, sc, 10.0)

    qbo = FakeQBO()
    csv_bytes = _make_csv([["Center", "Gardening"], ["iota", "0"]])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 0


def test_multiple_products_per_customer(db_session):
    """Customer with two products → two line items in the invoice."""
    sc = _make_service_code(db_session, "SC-M")
    customer = _make_customer(db_session, "Multi PS Co", qbo_id="qbo-mps", email="mps@mps.com")
    _make_center(db_session, customer.id, "kappa")
    ps1 = _make_product(db_session, "Gardening", "qbo-g14")
    ps2 = _make_product(db_session, "Cleaning", "qbo-c14")
    _link_service(db_session, customer, ps1, sc, 2.0)
    _link_service(db_session, customer, ps2, sc, 3.0)

    qbo = FakeQBO()
    csv_bytes = _make_csv([["Center", "Gardening", "Cleaning"], ["kappa", "4", "6"]])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    lines = qbo.invoices[0]["Line"]
    assert len(lines) == 2
    amounts = sorted(l["Amount"] for l in lines)
    assert amounts == [8.0, 18.0]  # 4*2 + 6*3


def test_skipped_center_does_not_block_other_centers(db_session):
    """Unknown center in file is skipped; known centers still generate invoices."""
    sc = _make_service_code(db_session, "SC-N")
    customer = _make_customer(db_session, "Mixed Skip Co", qbo_id="qbo-ms", email="ms@ms.com")
    _make_center(db_session, customer.id, "lambda")
    ps = _make_product(db_session, "Gardening", "qbo-g15")
    _link_service(db_session, customer, ps, sc, 4.0)

    qbo = FakeQBO()
    csv_bytes = _make_csv([
        ["Center", "Gardening"],
        ["lambda", "3"],
        ["nonexistent", "5"],
    ])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.centers_matched == 1
    assert result.centers_skipped == 1
    assert result.invoices_created == 1


def test_amount_calculation(db_session):
    """Amount = Qty × Rate, rounded to 2 decimal places."""
    sc = _make_service_code(db_session, "SC-O")
    customer = _make_customer(db_session, "Calc Co", qbo_id="qbo-calc", email="c@c.com")
    _make_center(db_session, customer.id, "mu")
    ps = _make_product(db_session, "Gardening", "qbo-g16")
    _link_service(db_session, customer, ps, sc, 1.50)

    qbo = FakeQBO()
    csv_bytes = _make_csv([["Center", "Gardening"], ["mu", "7"]])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    assert qbo.invoices[0]["Line"][0]["Amount"] == 10.50  # 7 * 1.50


# ── Endpoint tests ────────────────────────────────────────────────────────────

def test_upload_endpoint_rejects_bad_extension(admin_client):
    r = admin_client.post(
        "/api/v1/invoice-uploads",
        files={"file": ("data.pdf", b"fake", "application/pdf")},
    )
    assert r.status_code == 422


def test_upload_endpoint_requires_admin(supervisor_client):
    csv_bytes = _make_csv([["Center", "Gardening"], ["x", "1"]])
    r = supervisor_client.post(
        "/api/v1/invoice-uploads",
        files={"file": ("data.csv", csv_bytes, "text/csv")},
    )
    assert r.status_code == 403


def test_upload_endpoint_csv_no_qbo(admin_client):
    """Without QBO connected (no tokens file) endpoint returns 503."""
    csv_bytes = _make_csv([["Center", "Gardening"], ["x", "1"]])
    r = admin_client.post(
        "/api/v1/invoice-uploads",
        files={"file": ("data.csv", csv_bytes, "text/csv")},
    )
    # TOKEN_FILE_PATH points to a deleted file → QBO not connected
    assert r.status_code == 503


# ── DB persistence tests ──────────────────────────────────────────────────────

def test_db_records_persisted_when_upload_id_provided(db_session):
    """With invoice_upload_id, GeneratedInvoice + children are created in DB."""
    from app.models.generated_invoice import GeneratedInvoice, GeneratedInvoiceCenter, GeneratedInvoiceLineItem
    from app.models.invoice_upload import InvoiceUpload

    user = make_user(db_session, "admin@db.com", UserRole.admin)
    upload = InvoiceUpload(file_name="test.csv", uploaded_by_id=user.id, status="processing")
    db_session.add(upload)
    db_session.commit()
    db_session.refresh(upload)

    sc = _make_service_code(db_session, "SC-P")
    customer = _make_customer(db_session, "Persist Co", qbo_id="qbo-persist", email="p@p.com")
    _make_center(db_session, customer.id, "persist_center")
    ps = _make_product(db_session, "Gardening", "qbo-gp1")
    _link_service(db_session, customer, ps, sc, 10.0)

    qbo = FakeQBO()
    csv_bytes = _make_csv([["Center", "Gardening"], ["persist_center", "3"]])
    result = generate_invoices(
        db_session, qbo, "tok", "realm", "test.csv", csv_bytes,
        invoice_upload_id=upload.id,
    )
    db_session.commit()

    assert result.invoices_created == 1

    gen_inv = db_session.query(GeneratedInvoice).filter(GeneratedInvoice.invoice_upload_id == upload.id).first()
    assert gen_inv is not None
    assert gen_inv.send_status == "sent"
    assert gen_inv.invoice_number is not None
    assert gen_inv.invoice_number.startswith("INV-")
    assert gen_inv.customer_id == customer.id
    assert gen_inv.total_amount == Decimal("30.00")  # 3 * 10.0

    centers = db_session.query(GeneratedInvoiceCenter).filter(
        GeneratedInvoiceCenter.generated_invoice_id == gen_inv.id
    ).all()
    assert len(centers) == 1
    assert centers[0].center_name == "persist_center"

    line_items = db_session.query(GeneratedInvoiceLineItem).filter(
        GeneratedInvoiceLineItem.generated_invoice_id == gen_inv.id
    ).all()
    assert len(line_items) == 1
    assert line_items[0].product_name == "Gardening"
    assert line_items[0].quantity == Decimal("3")
    assert line_items[0].amount == Decimal("30.00")


def test_invoice_number_from_qbo_docnumber(db_session):
    """DocNumber from QBO response is stored as invoice_number."""
    sc = _make_service_code(db_session, "SC-Q")
    customer = _make_customer(db_session, "DocNum Co", qbo_id="qbo-dn", email="dn@dn.com")
    _make_center(db_session, customer.id, "dn_center")
    ps = _make_product(db_session, "Gardening", "qbo-gdn")
    _link_service(db_session, customer, ps, sc, 5.0)

    qbo = FakeQBO()
    csv_bytes = _make_csv([["Center", "Gardening"], ["dn_center", "2"]])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    assert result.invoice_details[0].invoice_number is not None
    assert result.invoice_details[0].invoice_number.startswith("INV-")
    assert result.invoice_details[0].send_status == "sent"
    assert result.invoice_details[0].sent is True


def test_no_db_records_without_upload_id(db_session):
    """Without invoice_upload_id, no GeneratedInvoice records are created."""
    from app.models.generated_invoice import GeneratedInvoice

    sc = _make_service_code(db_session, "SC-R")
    customer = _make_customer(db_session, "NoPersist Co", qbo_id="qbo-np", email="np@np.com")
    _make_center(db_session, customer.id, "np_center")
    ps = _make_product(db_session, "Gardening", "qbo-gnp")
    _link_service(db_session, customer, ps, sc, 5.0)

    qbo = FakeQBO()
    csv_bytes = _make_csv([["Center", "Gardening"], ["np_center", "1"]])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    count = db_session.query(GeneratedInvoice).count()
    assert count == 0


# ── Upload endpoint tests ─────────────────────────────────────────────────────

def test_get_upload_detail_404(admin_client):
    r = admin_client.get("/api/v1/invoice-uploads/99999")
    assert r.status_code == 404


def test_get_upload_detail_endpoint(admin_client, db_session, admin_user):
    """GET /invoice-uploads/{id} returns upload with generated invoices."""
    from app.models.generated_invoice import GeneratedInvoice
    from app.models.invoice_upload import InvoiceUpload

    upload = InvoiceUpload(
        file_name="detail_test.csv",
        uploaded_by_id=admin_user.id,
        status="completed",
        total_invoices=1,
        success_count=1,
        failed_count=0,
    )
    db_session.add(upload)
    db_session.commit()
    db_session.refresh(upload)

    customer = _make_customer(db_session, "Detail Co", qbo_id="qbo-det")
    gen_inv = GeneratedInvoice(
        invoice_upload_id=upload.id,
        customer_id=customer.id,
        center_group_name="center_a (standalone)",
        total_amount=Decimal("50.00"),
        send_status="sent",
        invoice_number="INV-001",
        quickbooks_invoice_id="qbo-123",
    )
    db_session.add(gen_inv)
    db_session.commit()

    r = admin_client.get(f"/api/v1/invoice-uploads/{upload.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == upload.id
    assert data["file_name"] == "detail_test.csv"
    assert data["status"] == "completed"
    assert data["success_count"] == 1
    assert len(data["generated_invoices"]) == 1
    gi = data["generated_invoices"][0]
    assert gi["invoice_number"] == "INV-001"
    assert gi["send_status"] == "sent"
    assert gi["customer_name"] == "Detail Co"


def test_get_upload_list_endpoint(admin_client, db_session, admin_user):
    """GET /invoice-uploads returns history ordered newest first."""
    from app.models.invoice_upload import InvoiceUpload

    for i in range(3):
        db_session.add(InvoiceUpload(
            file_name=f"file_{i}.csv",
            uploaded_by_id=admin_user.id,
            status="completed",
            total_invoices=i,
            success_count=i,
            failed_count=0,
        ))
    db_session.commit()

    r = admin_client.get("/api/v1/invoice-uploads")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    assert data[0]["file_name"] == "file_2.csv"  # newest first
    assert data[0]["uploaded_by"] is not None
    assert data[0]["total_invoices"] == 2
