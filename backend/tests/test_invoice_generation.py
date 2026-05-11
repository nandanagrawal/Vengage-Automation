"""Tests for RAW Data-Imaging upload and invoice generation flow."""

import csv
import io
from datetime import date
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


# ── CSV / XLSX helpers ────────────────────────────────────────────────────────

def _make_raw_csv(
    centers: list[tuple[str, dict]],
    col_names: list[str],
) -> bytes:
    """Create a RAW Data-Imaging style CSV.

    Headers: S.No., Center Name, Center Prefix, <col_names...>
    centers: [(center_name, {col_name: value})]
    Col 0 = center_name (used for DB matching), Col 2 = center_name (description prefix).
    """
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["S.No.", "Center Name", "Center Prefix"] + col_names)
    for name, metrics in centers:
        row = [name, "X", name] + [metrics.get(c, 0) for c in col_names]
        w.writerow(row)
    return buf.getvalue().encode()


def _make_raw_xlsx(
    centers: list[tuple[str, dict]],
    col_names: list[str],
    sheet_name: str = "RAW Data-Imaging",
) -> bytes:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.append(["S.No.", "Center Name", "Center Prefix"] + col_names)
    for name, metrics in centers:
        ws.append([name, "X", name] + [metrics.get(c, 0) for c in col_names])
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
    ps = ProductAndService(qbo_id=qbo_id, name=name, active=True)
    db.add(ps)
    db.commit()
    db.refresh(ps)
    return ps


def _link_service(db, customer, ps, sc, rate: float) -> CustomerProductAndService:
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
    content = _make_raw_csv(
        [("ac", {"Gardening": 5, "Cleaning": 3}),
         ("acc", {"Gardening": 2, "Cleaning": 1})],
        ["Gardening", "Cleaning"],
    )
    pf = parse_csv(content)
    assert set(pf.rows.keys()) == {"ac", "acc"}
    assert pf.rows["ac"]["gardening"] == Decimal("5")
    assert pf.rows["ac"]["cleaning"] == Decimal("3")
    assert pf.rows["acc"]["gardening"] == Decimal("2")
    assert pf.metric_columns == ["Gardening", "Cleaning"]


def test_parse_csv_empty_quantity_treated_as_zero():
    content = _make_raw_csv(
        [("ac", {"Gardening": ""}), ("acc", {"Gardening": 0})],
        ["Gardening"],
    )
    pf = parse_csv(content)
    assert pf.rows["ac"]["gardening"] == Decimal("0")
    assert pf.rows["acc"]["gardening"] == Decimal("0")


def test_parse_csv_non_numeric_quantity_becomes_zero():
    content = _make_raw_csv([("ac", {"Gardening": "abc"})], ["Gardening"])
    pf = parse_csv(content)
    assert pf.rows["ac"]["gardening"] == Decimal("0")


def test_parse_csv_duplicate_center_prefix_rows_summed():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["S.No.", "Center Name", "Center Prefix", "Gardening"])
    w.writerow(["ac", "X", "ac", "3"])
    w.writerow(["ac", "X", "ac", "2"])  # duplicate col-0 name → accumulated
    content = buf.getvalue().encode()
    pf = parse_csv(content)
    assert pf.rows["ac"]["gardening"] == Decimal("5")


def test_parse_csv_col2_first_token_stored_as_description_prefix():
    """Col 2's first comma-token is stored in center_prefixes for use in descriptions."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["S.No.", "Center Name", "Center Prefix", "Confirmed Appointment (4)"])
    w.writerow(["PAR", "X", "PAR, SMI-ALL", "440"])
    pf = parse_csv(buf.getvalue().encode())
    assert "par" in pf.rows  # col 0 is the matching key
    assert pf.center_prefixes.get("par") == "PAR"  # first token of col 2


def test_parse_xlsx_basic():
    content = _make_raw_xlsx(
        [("ac", {"Gardening": 5}), ("ad", {"Gardening": 2})],
        ["Gardening"],
    )
    pf = parse_xlsx(content)
    assert pf.rows["ac"]["gardening"] == Decimal("5")
    assert pf.rows["ad"]["gardening"] == Decimal("2")


def test_parse_spreadsheet_dispatches_by_extension():
    csv_bytes = _make_raw_csv([("x", {"G": 1})], ["G"])
    pf = parse_spreadsheet("data.csv", csv_bytes)
    assert "x" in pf.rows

    xlsx_bytes = _make_raw_xlsx([("y", {"G": 2})], ["G"])
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
    csv_bytes = _make_raw_csv([("unknown", {"Gardening": 5})], ["Gardening"])
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
    csv_bytes = _make_raw_csv([("alpha", {"Gardening": 3})], ["Gardening"])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 0
    assert any("no QBO ID" in e for e in result.errors)


def test_rate_from_customer_service_not_product(db_session):
    """Rate must come from CustomerProductAndService.rate."""
    sc = _make_service_code(db_session, "SC-B")
    customer = _make_customer(db_session, "Rate Co", qbo_id="qbo-c1", email="a@b.com")
    ctr = _make_center(db_session, customer.id, "beta")
    ps = _make_product(db_session, "Gardening", "qbo-g2")
    _link_service(db_session, customer, ps, sc, 7.50)

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv([("beta", {"Gardening": 4})], ["Gardening"])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    inv = qbo.invoices[0]
    line = inv["Line"][0]
    assert line["SalesItemLineDetail"]["UnitPrice"] == 7.50
    assert line["SalesItemLineDetail"]["Qty"] == 4.0
    assert line["Amount"] == 30.0


def test_zero_rate_skips_line_item(db_session):
    sc = _make_service_code(db_session, "SC-C")
    customer = _make_customer(db_session, "Zero Rate Co", qbo_id="qbo-c4", email="z@z.com")
    _make_center(db_session, customer.id, "delta")
    ps = _make_product(db_session, "Gardening", "qbo-g5")
    cps = CustomerProductAndService(
        customer_id=customer.id,
        product_and_service_id=ps.id,
        service_code_id=sc.id,
        rate=Decimal("0"),
    )
    db_session.add(cps)
    db_session.commit()

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv([("delta", {"Gardening": 5})], ["Gardening"])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 0


def test_center_matching_is_case_insensitive(db_session):
    sc = _make_service_code(db_session, "SC-D")
    customer = _make_customer(db_session, "Case Co", qbo_id="qbo-case", email="case@case.com")
    _make_center(db_session, customer.id, "Alpha")  # stored as "Alpha"
    ps = _make_product(db_session, "Gardening", "qbo-g6")
    _link_service(db_session, customer, ps, sc, 5.0)

    qbo = FakeQBO()
    # "alpha" (lowercase) in file should match center "Alpha"
    csv_bytes = _make_raw_csv([("alpha", {"Gardening": 3})], ["Gardening"])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.centers_matched == 1
    assert result.invoices_created == 1


def test_product_column_fallback_matching(db_session):
    """Product name found in column header via fallback (case-insensitive substring)."""
    sc = _make_service_code(db_session, "SC-E")
    customer = _make_customer(db_session, "Upper Co", qbo_id="qbo-upper", email="u@u.com")
    _make_center(db_session, customer.id, "epsilon")
    ps = _make_product(db_session, "Gardening", "qbo-g7")
    _link_service(db_session, customer, ps, sc, 10.0)

    qbo = FakeQBO()
    # Column "Gardening" (exact case) → fallback matches "gardening" in col header
    csv_bytes = _make_raw_csv([("epsilon", {"Gardening": 2})], ["Gardening"])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1


def test_grouped_centers_one_invoice_per_center_line_items(db_session):
    """Grouped centers → one invoice with separate line items per center (NOT summed)."""
    sc = _make_service_code(db_session, "SC-F")
    customer = _make_customer(db_session, "Grouped Co", qbo_id="qbo-grp", email="g@g.com")
    ctr_ac = _make_center(db_session, customer.id, "ac")
    ctr_acc = _make_center(db_session, customer.id, "acc")
    _make_grouping(db_session, customer.id, [ctr_ac, ctr_acc])
    ps = _make_product(db_session, "Gardening", "qbo-g8")
    _link_service(db_session, customer, ps, sc, 2.0)

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv(
        [("ac", {"Gardening": 5}), ("acc", {"Gardening": 3})],
        ["Gardening"],
    )
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    lines = qbo.invoices[0]["Line"]
    assert len(lines) == 2  # one line per center
    qtys = sorted(l["SalesItemLineDetail"]["Qty"] for l in lines)
    assert qtys == [3.0, 5.0]  # NOT summed
    assert sum(l["Amount"] for l in lines) == pytest.approx(16.0)  # total = (5+3)*2


def test_standalone_center_individual_invoice(db_session):
    sc = _make_service_code(db_session, "SC-G")
    customer = _make_customer(db_session, "Standalone Co", qbo_id="qbo-sa", email="s@s.com")
    _make_center(db_session, customer.id, "ad")
    ps = _make_product(db_session, "Gardening", "qbo-g9")
    _link_service(db_session, customer, ps, sc, 3.0)

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv([("ad", {"Gardening": 2})], ["Gardening"])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    line = qbo.invoices[0]["Line"][0]
    assert line["SalesItemLineDetail"]["Qty"] == 2.0
    assert line["Amount"] == 6.0


def test_mixed_grouped_and_standalone(db_session):
    """ac+acc grouped → 1 invoice; ad standalone → 1 invoice."""
    sc = _make_service_code(db_session, "SC-H")
    customer = _make_customer(db_session, "Mixed Co", qbo_id="qbo-mix", email="m@m.com")
    ctr_ac = _make_center(db_session, customer.id, "ac2")
    ctr_acc = _make_center(db_session, customer.id, "acc2")
    ctr_ad = _make_center(db_session, customer.id, "ad2")
    _make_grouping(db_session, customer.id, [ctr_ac, ctr_acc])
    ps = _make_product(db_session, "Gardening", "qbo-g10")
    _link_service(db_session, customer, ps, sc, 1.0)

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv(
        [("ac2", {"Gardening": 5}), ("acc2", {"Gardening": 3}), ("ad2", {"Gardening": 2})],
        ["Gardening"],
    )
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 2
    # One invoice has 2 per-center line items (grouped), the other has 1 (standalone)
    line_counts = sorted(len(inv["Line"]) for inv in qbo.invoices)
    assert line_counts == [1, 2]


def test_product_with_no_column_mapping_skips_line_item(db_session):
    """Product not in PRODUCT_COLUMN_MAP and not matching any column → line item skipped."""
    sc = _make_service_code(db_session, "SC-I")
    customer = _make_customer(db_session, "No Match Co", qbo_id="qbo-nm", email="nm@nm.com")
    _make_center(db_session, customer.id, "eta")
    ps = _make_product(db_session, "Plumbing", "qbo-p1")
    _link_service(db_session, customer, ps, sc, 20.0)

    qbo = FakeQBO()
    # CSV has "Gardening" column only — no "Plumbing" column and "Plumbing" not in PRODUCT_COLUMN_MAP
    csv_bytes = _make_raw_csv([("eta", {"Gardening": 5})], ["Gardening"])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 0
    assert any("no line items" in e for e in result.errors)


def test_zero_quantity_creates_invoice(db_session):
    """0-quantity items are included (matching invoice data behaviour)."""
    sc = _make_service_code(db_session, "SC-L")
    customer = _make_customer(db_session, "Zero Qty Co", qbo_id="qbo-zq", email="zq@zq.com")
    _make_center(db_session, customer.id, "iota")
    ps = _make_product(db_session, "Gardening", "qbo-g13")
    _link_service(db_session, customer, ps, sc, 10.0)

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv([("iota", {"Gardening": 0})], ["Gardening"])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    line = qbo.invoices[0]["Line"][0]
    assert line["SalesItemLineDetail"]["Qty"] == 0.0
    assert line["Amount"] == 0.0


def test_invoice_sent_after_creation(db_session):
    sc = _make_service_code(db_session, "SC-K")
    customer = _make_customer(db_session, "Send Co", qbo_id="qbo-send", email="send@send.com")
    _make_center(db_session, customer.id, "theta")
    ps = _make_product(db_session, "Gardening", "qbo-g12")
    _link_service(db_session, customer, ps, sc, 5.0)

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv([("theta", {"Gardening": 1})], ["Gardening"])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    assert result.invoice_details[0].sent is True
    assert qbo.invoices[0]["EmailStatus"] == "EmailSent"


def test_multiple_products_per_customer(db_session):
    """Customer with two products → two line items per center."""
    sc = _make_service_code(db_session, "SC-M")
    customer = _make_customer(db_session, "Multi PS Co", qbo_id="qbo-mps", email="mps@mps.com")
    _make_center(db_session, customer.id, "kappa")
    ps1 = _make_product(db_session, "Gardening", "qbo-g14")
    ps2 = _make_product(db_session, "Cleaning", "qbo-c14")
    _link_service(db_session, customer, ps1, sc, 2.0)
    _link_service(db_session, customer, ps2, sc, 3.0)

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv([("kappa", {"Gardening": 4, "Cleaning": 6})], ["Gardening", "Cleaning"])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    lines = qbo.invoices[0]["Line"]
    assert len(lines) == 2
    amounts = sorted(l["Amount"] for l in lines)
    assert amounts == [8.0, 18.0]


def test_skipped_center_does_not_block_others(db_session):
    sc = _make_service_code(db_session, "SC-N")
    customer = _make_customer(db_session, "Mixed Skip Co", qbo_id="qbo-ms", email="ms@ms.com")
    _make_center(db_session, customer.id, "lambda")
    ps = _make_product(db_session, "Gardening", "qbo-g15")
    _link_service(db_session, customer, ps, sc, 4.0)

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv(
        [("lambda", {"Gardening": 3}), ("nonexistent", {"Gardening": 5})],
        ["Gardening"],
    )
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.centers_matched == 1
    assert result.centers_skipped == 1
    assert result.invoices_created == 1


def test_amount_calculation(db_session):
    sc = _make_service_code(db_session, "SC-O")
    customer = _make_customer(db_session, "Calc Co", qbo_id="qbo-calc", email="c@c.com")
    _make_center(db_session, customer.id, "mu")
    ps = _make_product(db_session, "Gardening", "qbo-g16")
    _link_service(db_session, customer, ps, sc, 1.50)

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv([("mu", {"Gardening": 7})], ["Gardening"])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    assert qbo.invoices[0]["Line"][0]["Amount"] == pytest.approx(10.50)


def test_invoice_description_format(db_session):
    """Line item description: {center_prefix} - {MMMYY} Invoice month {service_code}"""
    sc = _make_service_code(db_session, "SC-DESC")
    customer = _make_customer(db_session, "Desc Co", qbo_id="qbo-desc", email="d@d.com")
    _make_center(db_session, customer.id, "PAR")
    ps = _make_product(db_session, "Gardening", "qbo-gdesc")
    _link_service(db_session, customer, ps, sc, 5.0)

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv([("PAR", {"Gardening": 1})], ["Gardening"])
    generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    today = date.today()
    month_label = today.strftime("%b%y").upper()
    line = qbo.invoices[0]["Line"][0]
    assert line["Description"] == f"PAR - {month_label} Invoice month SC-DESC"


def test_invoice_dates_and_memo(db_session):
    """TxnDate = last day of month, DueDate = TxnDate + 15, Memo = MMMYY Invoice."""
    import calendar
    from datetime import timedelta

    sc = _make_service_code(db_session, "SC-DATE")
    customer = _make_customer(db_session, "Date Co", qbo_id="qbo-date", email="dt@dt.com")
    _make_center(db_session, customer.id, "datectr")
    ps = _make_product(db_session, "Gardening", "qbo-gdate")
    _link_service(db_session, customer, ps, sc, 1.0)

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv([("datectr", {"Gardening": 1})], ["Gardening"])
    generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    today = date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    expected_txn = date(today.year, today.month, last_day).isoformat()
    expected_due = (date(today.year, today.month, last_day) + timedelta(days=15)).isoformat()
    expected_memo = today.strftime("%b%y").upper() + " Invoice"

    payload = qbo.invoices[0]
    assert payload["TxnDate"] == expected_txn
    assert payload["DueDate"] == expected_due
    assert payload["CustomerMemo"]["value"] == expected_memo


def test_product_column_map_confirmed_appointment(db_session):
    """Olivia AI Bookings maps to 'Confirmed Appointment (4)' column."""
    sc = _make_service_code(db_session, "B0001")
    customer = _make_customer(db_session, "Imaging Co", qbo_id="qbo-img", email="img@img.com")
    _make_center(db_session, customer.id, "PAR")
    ps = _make_product(db_session, "Olivia AI Bookings for Imaging workflow", "qbo-olivia")
    _link_service(db_session, customer, ps, sc, 0.10)

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv(
        [("PAR", {"Confirmed Appointment (4)": 440})],
        ["Confirmed Appointment (4)"],
    )
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    line = qbo.invoices[0]["Line"][0]
    assert line["SalesItemLineDetail"]["Qty"] == 440.0
    assert line["Amount"] == pytest.approx(44.0)


def test_call_forwarding_sums_bh_and_ooh(db_session):
    """Call Forwarding sums BH mins + OOH mins columns."""
    sc = _make_service_code(db_session, "B0002")
    customer = _make_customer(db_session, "CF Co", qbo_id="qbo-cf", email="cf@cf.com")
    _make_center(db_session, customer.id, "PAR")
    ps = _make_product(db_session, "Call Forwarding - Telephony Charges", "qbo-cf1")
    _link_service(db_session, customer, ps, sc, 0.05)

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv(
        [("PAR", {"Voice call forwarding BH (mins) (9)": 140, "Voice call forwarding OOH (mins) (10)": 57})],
        ["Voice call forwarding BH (mins) (9)", "Voice call forwarding OOH (mins) (10)"],
    )
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    line = qbo.invoices[0]["Line"][0]
    assert line["SalesItemLineDetail"]["Qty"] == 197.0  # 140 + 57


# ── Endpoint tests ────────────────────────────────────────────────────────────

def test_upload_endpoint_rejects_bad_extension(admin_client):
    r = admin_client.post(
        "/api/v1/invoice-uploads",
        files={"file": ("data.pdf", b"fake", "application/pdf")},
    )
    assert r.status_code == 422


def test_upload_endpoint_requires_admin(supervisor_client):
    csv_bytes = _make_raw_csv([("x", {"Gardening": 1})], ["Gardening"])
    r = supervisor_client.post(
        "/api/v1/invoice-uploads",
        files={"file": ("data.csv", csv_bytes, "text/csv")},
    )
    assert r.status_code == 403


def test_upload_endpoint_csv_no_qbo(admin_client):
    csv_bytes = _make_raw_csv([("x", {"Gardening": 1})], ["Gardening"])
    r = admin_client.post(
        "/api/v1/invoice-uploads",
        files={"file": ("data.csv", csv_bytes, "text/csv")},
    )
    assert r.status_code == 503


# ── DB persistence tests ──────────────────────────────────────────────────────

def test_db_records_persisted_when_upload_id_provided(db_session):
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
    csv_bytes = _make_raw_csv([("persist_center", {"Gardening": 3})], ["Gardening"])
    result = generate_invoices(
        db_session, qbo, "tok", "realm", "test.csv", csv_bytes,
        invoice_upload_id=upload.id,
    )
    db_session.commit()

    assert result.invoices_created == 1

    gen_inv = db_session.query(GeneratedInvoice).filter(GeneratedInvoice.invoice_upload_id == upload.id).first()
    assert gen_inv is not None
    assert gen_inv.send_status == "sent"
    assert gen_inv.invoice_number.startswith("INV-")
    assert gen_inv.total_amount == Decimal("30.00")

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
    assert line_items[0].description is not None


def test_no_db_records_without_upload_id(db_session):
    from app.models.generated_invoice import GeneratedInvoice

    sc = _make_service_code(db_session, "SC-R")
    customer = _make_customer(db_session, "NoPersist Co", qbo_id="qbo-np", email="np@np.com")
    _make_center(db_session, customer.id, "np_center")
    ps = _make_product(db_session, "Gardening", "qbo-gnp")
    _link_service(db_session, customer, ps, sc, 5.0)

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv([("np_center", {"Gardening": 1})], ["Gardening"])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    assert db_session.query(GeneratedInvoice).count() == 0


def test_get_upload_detail_404(admin_client):
    r = admin_client.get("/api/v1/invoice-uploads/99999")
    assert r.status_code == 404


def test_get_upload_detail_endpoint(admin_client, db_session, admin_user):
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
    gi = data["generated_invoices"][0]
    assert gi["invoice_number"] == "INV-001"
    assert gi["send_status"] == "sent"
    assert gi["customer_name"] == "Detail Co"


def test_get_upload_list_endpoint(admin_client, db_session, admin_user):
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
    assert data[0]["file_name"] == "file_2.csv"
    assert data[0]["total_invoices"] == 2
