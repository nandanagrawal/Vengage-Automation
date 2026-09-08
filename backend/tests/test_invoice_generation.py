"""Tests for RAW Data-Imaging upload and invoice generation flow."""

import csv
import io
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.center import Center
from app.models.customer import Customer, CustomerStatus
from app.models.customer_product_and_service import (
    CustomerProductAndService,
    CustomerProductAndServiceSlab,
    PricingType,
)
from app.models.invoice import Invoice
from app.models.product_and_service import ProductAndService
from app.models.product_column_mapping import ProductColumnMapping
from app.models.service_code import ServiceCode
from app.models.sheet_column import SheetColumn
from app.models.user import UserRole
from app.services import gdrive_client
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


def _make_customer(
    db, display_name: str, qbo_id: str | None = None, email: str | None = None,
    payment_terms_days: int | None = None, add_attachment_in_mail: bool = False,
) -> Customer:
    c = Customer(
        display_name=display_name,
        status=CustomerStatus.approved,
        qbo_id=qbo_id,
        primary_email=email,
        ship_same_as_billing=True,
        add_attachment_in_mail=add_attachment_in_mail,
        **({"payment_terms_days": payment_terms_days} if payment_terms_days is not None else {}),
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


def _set_column_mapping(db, ps: ProductAndService, column_header: str) -> ProductColumnMapping:
    """Upsert: safe to call more than once for the same product (e.g. to
    override the default mapping _link_service sets up)."""
    sheet_col = db.query(SheetColumn).filter(SheetColumn.name == column_header).first()
    if not sheet_col:
        sheet_col = SheetColumn(name=column_header)
        db.add(sheet_col)
        db.commit()
        db.refresh(sheet_col)
    row = (
        db.query(ProductColumnMapping)
        .filter(ProductColumnMapping.product_and_service_id == ps.id)
        .first()
    )
    if row:
        row.sheet_column_id = sheet_col.id
    else:
        row = ProductColumnMapping(product_and_service_id=ps.id, sheet_column_id=sheet_col.id)
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _link_service(db, customer, ps, sc, rate: float, column: str | bool | None = None) -> CustomerProductAndService:
    # `sc` (ServiceCode) is accepted for call-site compatibility but no longer
    # linked — service_code_id was dropped from CustomerProductAndService.
    #
    # `column`: quantity now resolves solely via ProductColumnMapping, so this
    # helper sets one up too — defaulting to the product's own name (the
    # product-name-equals-column-header convention nearly every test here
    # uses). Pass an explicit name when the CSV column differs from the
    # product name, or `column=False` to leave the product unmapped.
    cps = CustomerProductAndService(
        customer_id=customer.id,
        product_and_service_id=ps.id,
        pricing_type=PricingType.flat,
        rate=Decimal(str(rate)),
    )
    db.add(cps)
    db.commit()
    db.refresh(cps)
    if column is not False:
        _set_column_mapping(db, ps, column or ps.name)
    return cps


def _link_slab_service(
    db, customer, ps, tiers: list[tuple[int, int | None, float]]
) -> CustomerProductAndService:
    """tiers: list of (range_start, range_end_or_None, rate)."""
    cps = CustomerProductAndService(
        customer_id=customer.id,
        product_and_service_id=ps.id,
        pricing_type=PricingType.slab,
    )
    cps.slabs = [
        CustomerProductAndServiceSlab(range_start=start, range_end=end, rate=Decimal(str(rate)))
        for start, end, rate in tiers
    ]
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
        pricing_type=PricingType.flat,
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
    """Dynamic column mapping match is case-insensitive."""
    sc = _make_service_code(db_session, "SC-E")
    customer = _make_customer(db_session, "Upper Co", qbo_id="qbo-upper", email="u@u.com")
    _make_center(db_session, customer.id, "epsilon")
    ps = _make_product(db_session, "Gardening", "qbo-g7")
    _link_service(db_session, customer, ps, sc, 10.0)

    qbo = FakeQBO()
    # Mapped column is "Gardening"; file header is the same text — case-insensitive match.
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
    """Product's mapped column isn't present in this file → line item skipped."""
    sc = _make_service_code(db_session, "SC-I")
    customer = _make_customer(db_session, "No Match Co", qbo_id="qbo-nm", email="nm@nm.com")
    _make_center(db_session, customer.id, "eta")
    ps = _make_product(db_session, "Plumbing", "qbo-p1")
    _link_service(db_session, customer, ps, sc, 20.0)  # mapped to "Plumbing" by default

    qbo = FakeQBO()
    # CSV has "Gardening" column only — no "Plumbing" column present
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


def test_invoice_created_as_draft(db_session):
    sc = _make_service_code(db_session, "SC-K")
    customer = _make_customer(db_session, "Send Co", qbo_id="qbo-send", email="send@send.com")
    _make_center(db_session, customer.id, "theta")
    ps = _make_product(db_session, "Gardening", "qbo-g12")
    _link_service(db_session, customer, ps, sc, 5.0)

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv([("theta", {"Gardening": 1})], ["Gardening"])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    detail = result.invoice_details[0]
    assert detail.sent is False
    assert detail.sent_at is None
    assert detail.send_status == "pending"
    assert qbo.invoices[0]["EmailStatus"] == "NotSet"


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
    """Line item description: "{Center Name} for {Mon} {YY}", e.g. "PAR for Aug 26".

    _make_raw_csv always puts "X" in column 1 (Center Name) — that's what
    ends up in the description, per the same col-1-over-col-0 preference the
    rest of invoice generation already uses (center_col1_name fallback)."""
    sc = _make_service_code(db_session, "SC-DESC")
    customer = _make_customer(db_session, "Desc Co", qbo_id="qbo-desc", email="d@d.com")
    _make_center(db_session, customer.id, "PAR")
    ps = _make_product(db_session, "Gardening", "qbo-gdesc")
    _link_service(db_session, customer, ps, sc, 5.0)

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv([("PAR", {"Gardening": 1})], ["Gardening"])
    generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    today = date.today()
    first_of_current = today.replace(day=1)
    last_month_last_day = first_of_current - timedelta(days=1)
    month_label = last_month_last_day.strftime("%b %y")
    line = qbo.invoices[0]["Line"][0]
    assert line["Description"] == f"X for {month_label}"


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
    """Olivia AI Bookings dynamically mapped to 'Confirmed Appointment (4)' column."""
    sc = _make_service_code(db_session, "B0001")
    customer = _make_customer(db_session, "Imaging Co", qbo_id="qbo-img", email="img@img.com")
    _make_center(db_session, customer.id, "PAR")
    ps = _make_product(db_session, "Olivia AI Bookings for Imaging workflow", "qbo-olivia")
    _link_service(db_session, customer, ps, sc, 0.10, column="Confirmed Appointment (4)")

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


def test_slab_pricing_distributes_quantity_across_tiers(db_session):
    """A slab-priced service splits the metric total across its tiers, one
    line item per tier, each at that tier's own rate, with the range in the
    Description."""
    customer = _make_customer(db_session, "Slab Imaging Co", qbo_id="qbo-slab", email="slab@slab.com")
    _make_center(db_session, customer.id, "PAR")
    ps = _make_product(db_session, "Olivia AI Bookings for Imaging Workflow", "qbo-olivia-slab")
    _link_slab_service(
        db_session, customer, ps,
        [(1, 1000, 5.0), (1001, 2500, 4.0), (2501, None, 3.0)],
    )
    _set_column_mapping(db_session, ps, "Confirmed Appointment (4)")

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv(
        [("PAR", {"Confirmed Appointment (4)": 2755})],
        ["Confirmed Appointment (4)"],
    )
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    lines = qbo.invoices[0]["Line"]
    assert len(lines) == 3

    by_qty = {round(l["SalesItemLineDetail"]["Qty"]): l for l in lines}
    assert set(by_qty) == {1000, 1500, 255}

    tier1 = by_qty[1000]
    assert tier1["SalesItemLineDetail"]["UnitPrice"] == 5.0
    assert tier1["Amount"] == pytest.approx(5000.0)
    assert "1-1000" in tier1["Description"]

    tier2 = by_qty[1500]
    assert tier2["SalesItemLineDetail"]["UnitPrice"] == 4.0
    assert "1001-2500" in tier2["Description"]

    tier3 = by_qty[255]
    assert tier3["SalesItemLineDetail"]["UnitPrice"] == 3.0
    assert "2501+" in tier3["Description"]


def test_slab_pricing_below_first_tier_skips_all_line_items(db_session):
    """Total below the lowest tier's start → every tier gets qty=0 and is dropped."""
    customer = _make_customer(db_session, "Low Slab Co", qbo_id="qbo-lowslab", email="low@low.com")
    _make_center(db_session, customer.id, "PAR")
    ps = _make_product(db_session, "Olivia AI Bookings for Imaging Workflow", "qbo-olivia-low")
    _link_slab_service(db_session, customer, ps, [(1001, 2500, 4.0), (2501, None, 3.0)])
    _set_column_mapping(db_session, ps, "Confirmed Appointment (4)")

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv(
        [("PAR", {"Confirmed Appointment (4)": 500})],
        ["Confirmed Appointment (4)"],
    )
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 0


def test_flat_and_slab_services_coexist_on_same_customer(db_session):
    """A customer can have one flat-priced product and one slab-priced product."""
    sc = _make_service_code(db_session, "B0099")
    customer = _make_customer(db_session, "Mixed Pricing Co", qbo_id="qbo-mixed", email="mixed@mixed.com")
    _make_center(db_session, customer.id, "PAR")
    flat_ps = _make_product(db_session, "Gardening", "qbo-flat-1")
    slab_ps = _make_product(db_session, "Olivia AI Bookings for Imaging Workflow", "qbo-slab-1")
    _link_service(db_session, customer, flat_ps, sc, 2.0)
    _link_slab_service(db_session, customer, slab_ps, [(1, 1000, 5.0), (1001, None, 3.0)])
    _set_column_mapping(db_session, slab_ps, "Confirmed Appointment (4)")

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv(
        [("PAR", {"Gardening": 10, "Confirmed Appointment (4)": 1200})],
        ["Gardening", "Confirmed Appointment (4)"],
    )
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    lines = qbo.invoices[0]["Line"]
    assert len(lines) == 3  # 1 flat + 2 slab tiers
    amounts = sorted(l["Amount"] for l in lines)
    assert amounts == pytest.approx([20.0, 600.0, 5000.0])


# ── Dynamic (admin-configured) column mapping ─────────────────────────────────

def test_dynamic_column_mapping_ignores_other_columns_with_similar_names(db_session):
    """Quantity comes only from the exact mapped column — other columns that
    might look related (old BH/OOH minutes columns) are ignored entirely."""
    sc = _make_service_code(db_session, "B0003")
    customer = _make_customer(db_session, "Dynamic Co", qbo_id="qbo-dyn", email="dyn@dyn.com")
    _make_center(db_session, customer.id, "PAR")
    ps = _make_product(db_session, "Call Forwarding - Telephony Charges", "qbo-dyn1")
    _link_service(db_session, customer, ps, sc, 2.0, column="Call Forwarding Total (17)")

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv(
        [("PAR", {
            "Voice call forwarding BH (mins) (9)": 140,
            "Voice call forwarding OOH (mins) (10)": 57,
            "Call Forwarding Total (17)": 30,
        })],
        ["Voice call forwarding BH (mins) (9)", "Voice call forwarding OOH (mins) (10)", "Call Forwarding Total (17)"],
    )
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    line = qbo.invoices[0]["Line"][0]
    assert line["SalesItemLineDetail"]["Qty"] == 30.0  # not 197 (140+57) — no summing anymore
    assert line["Amount"] == pytest.approx(60.0)


def test_dynamic_column_mapping_missing_column_skips_line_item(db_session):
    """If the mapped column isn't in this file, skip — never guess 0 or match
    a different column."""
    sc = _make_service_code(db_session, "B0004")
    customer = _make_customer(db_session, "Dynamic Missing Co", qbo_id="qbo-dynm", email="dynm@dynm.com")
    _make_center(db_session, customer.id, "PAR")
    ps = _make_product(db_session, "Gardening", "qbo-dynm1")
    _link_service(db_session, customer, ps, sc, 5.0, column="Gardening Total (20)")

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv([("PAR", {"Some Other Column": 10})], ["Some Other Column"])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 0


def test_unmapped_product_produces_no_line_item(db_session):
    """A product with no ProductColumnMapping row at all is skipped — quantity
    resolution is dynamic-mapping-only, no name-based fallback of any kind."""
    sc = _make_service_code(db_session, "B0005")
    customer = _make_customer(db_session, "No Dynamic Co", qbo_id="qbo-nodyn", email="nodyn@nodyn.com")
    _make_center(db_session, customer.id, "PAR")
    ps = _make_product(db_session, "Olivia AI Bookings for Imaging workflow", "qbo-nodyn1")
    _link_service(db_session, customer, ps, sc, 0.10, column=False)  # deliberately unmapped

    qbo = FakeQBO()
    # Column name matches the product name exactly — would have matched under
    # the old name-based fallback, but there is no such fallback anymore.
    csv_bytes = _make_raw_csv(
        [("PAR", {"Olivia AI Bookings for Imaging workflow": 440})],
        ["Olivia AI Bookings for Imaging workflow"],
    )
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 0


# ── Drive attachment ───────────────────────────────────────────────────────────

def _fake_drive_folder(monkeypatch, files: dict[str, dict]):
    """files: {center_name_lower: {"id": ..., "name": ..., "mimeType": ...}}"""
    monkeypatch.setattr(gdrive_client, "extract_folder_id", lambda url: "fake-folder-id")
    monkeypatch.setattr(gdrive_client, "match_center_files", lambda folder_id: files)
    monkeypatch.setattr(
        gdrive_client, "download_file",
        lambda file_id, mime_type: (b"fake xlsx bytes", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    )


def test_drive_attachment_matched_center(db_session, monkeypatch):
    sc = _make_service_code(db_session, "SC-DRV1")
    customer = _make_customer(db_session, "Drive Co", qbo_id="qbo-drive1", email="d1@d1.com", add_attachment_in_mail=True)
    _make_center(db_session, customer.id, "PAR")
    ps = _make_product(db_session, "Gardening", "qbo-drive-g1")
    _link_service(db_session, customer, ps, sc, 5.0)
    _fake_drive_folder(monkeypatch, {"par": {"id": "file-1", "name": "PAR.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}})

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv([("PAR", {"Gardening": 3})], ["Gardening"])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes, drive_folder_url="https://drive.google.com/drive/folders/anything")

    assert result.invoices_created == 1
    assert len(qbo.attachments) == 1
    att = qbo.attachments[0]
    assert att["filename"] == "PAR.xlsx"
    assert att["invoice_id"] == qbo.invoices[0]["Id"]


def test_drive_attachment_no_match_warns_but_invoice_still_created(db_session, monkeypatch):
    sc = _make_service_code(db_session, "SC-DRV2")
    customer = _make_customer(db_session, "Drive No Match Co", qbo_id="qbo-drive2", email="d2@d2.com", add_attachment_in_mail=True)
    _make_center(db_session, customer.id, "PAR")
    ps = _make_product(db_session, "Gardening", "qbo-drive-g2")
    _link_service(db_session, customer, ps, sc, 5.0)
    _fake_drive_folder(monkeypatch, {})  # folder has no file matching "par"

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv([("PAR", {"Gardening": 3})], ["Gardening"])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes, drive_folder_url="https://drive.google.com/drive/folders/anything")

    assert result.invoices_created == 1
    assert len(qbo.attachments) == 0
    assert any("no matching Drive file" in e for e in result.errors)


def test_drive_attachment_grouped_invoice_attaches_every_matched_center(db_session, monkeypatch):
    sc = _make_service_code(db_session, "SC-DRV3")
    customer = _make_customer(db_session, "Drive Grouped Co", qbo_id="qbo-drive3", email="d3@d3.com", add_attachment_in_mail=True)
    ctr_a = _make_center(db_session, customer.id, "grp-a")
    ctr_b = _make_center(db_session, customer.id, "grp-b")
    _make_grouping(db_session, customer.id, [ctr_a, ctr_b])
    ps = _make_product(db_session, "Gardening", "qbo-drive-g3")
    _link_service(db_session, customer, ps, sc, 2.0)
    _fake_drive_folder(monkeypatch, {
        "grp-a": {"id": "file-a", "name": "GRP-A.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        "grp-b": {"id": "file-b", "name": "GRP-B.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    })

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv([("grp-a", {"Gardening": 5}), ("grp-b", {"Gardening": 3})], ["Gardening"])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes, drive_folder_url="https://drive.google.com/drive/folders/anything")

    assert result.invoices_created == 1
    assert len(qbo.attachments) == 2
    filenames = {a["filename"] for a in qbo.attachments}
    assert filenames == {"GRP-A.xlsx", "GRP-B.xlsx"}
    assert all(a["invoice_id"] == qbo.invoices[0]["Id"] for a in qbo.attachments)


def test_no_drive_folder_url_skips_attachment_entirely(db_session, monkeypatch):
    """Without drive_folder_url, gdrive_client is never touched at all."""
    monkeypatch.setattr(
        gdrive_client, "extract_folder_id",
        lambda url: (_ for _ in ()).throw(AssertionError("should not be called")),
    )
    sc = _make_service_code(db_session, "SC-DRV4")
    customer = _make_customer(db_session, "No Drive Co", qbo_id="qbo-drive4", email="d4@d4.com")
    _make_center(db_session, customer.id, "PAR")
    ps = _make_product(db_session, "Gardening", "qbo-drive-g4")
    _link_service(db_session, customer, ps, sc, 5.0)

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv([("PAR", {"Gardening": 3})], ["Gardening"])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 1
    assert len(qbo.attachments) == 0


def test_drive_attachment_skipped_when_customer_opted_out(db_session, monkeypatch):
    """add_attachment_in_mail=False (the default) means Drive is never even
    consulted for that customer, even with a real matching file waiting."""
    sc = _make_service_code(db_session, "SC-DRV5")
    customer = _make_customer(db_session, "Opted Out Co", qbo_id="qbo-drive5", email="d5@d5.com", add_attachment_in_mail=False)
    _make_center(db_session, customer.id, "PAR")
    ps = _make_product(db_session, "Gardening", "qbo-drive-g5")
    _link_service(db_session, customer, ps, sc, 5.0)
    _fake_drive_folder(monkeypatch, {"par": {"id": "file-1", "name": "PAR.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}})

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv([("PAR", {"Gardening": 3})], ["Gardening"])
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes, drive_folder_url="https://drive.google.com/drive/folders/anything")

    assert result.invoices_created == 1
    assert len(qbo.attachments) == 0
    assert not any("Drive" in e for e in result.errors)  # not required, so no warning either


# ── Pre-flight Drive attachment check (Preview stage) ─────────────────────────

def test_check_drive_attachments_warns_when_required_and_missing(db_session, monkeypatch):
    from app.schemas.invoice_validation import ValidatedRow
    from app.services.invoice_validation import check_drive_attachments

    customer = _make_customer(db_session, "Pre-flight Co", qbo_id="qbo-pf1", email="pf1@pf1.com", add_attachment_in_mail=True)
    _make_center(db_session, customer.id, "PAR")
    _fake_drive_folder(monkeypatch, {})  # no files at all

    rows = [ValidatedRow(row_index=0, center_id="PAR", center_name="X", center_prefix="PAR", metrics={}, matched=True)]
    warnings = check_drive_attachments(rows, "https://drive.google.com/drive/folders/anything", db_session)

    assert len(warnings) == 1
    assert "Pre-flight Co" in warnings[0]
    assert "PAR" in warnings[0]


def test_check_drive_attachments_no_warning_when_not_required(db_session, monkeypatch):
    from app.schemas.invoice_validation import ValidatedRow
    from app.services.invoice_validation import check_drive_attachments

    customer = _make_customer(db_session, "No Opt-in Co", qbo_id="qbo-pf2", email="pf2@pf2.com", add_attachment_in_mail=False)
    _make_center(db_session, customer.id, "PAR")
    _fake_drive_folder(monkeypatch, {})  # no files at all — but doesn't matter, not required

    rows = [ValidatedRow(row_index=0, center_id="PAR", center_name="X", center_prefix="PAR", metrics={}, matched=True)]
    warnings = check_drive_attachments(rows, "https://drive.google.com/drive/folders/anything", db_session)

    assert warnings == []


def test_check_drive_attachments_no_warning_when_matched(db_session, monkeypatch):
    from app.schemas.invoice_validation import ValidatedRow
    from app.services.invoice_validation import check_drive_attachments

    customer = _make_customer(db_session, "Matched Co", qbo_id="qbo-pf3", email="pf3@pf3.com", add_attachment_in_mail=True)
    _make_center(db_session, customer.id, "PAR")
    _fake_drive_folder(monkeypatch, {"par": {"id": "file-1", "name": "PAR.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}})

    rows = [ValidatedRow(row_index=0, center_id="PAR", center_name="X", center_prefix="PAR", metrics={}, matched=True)]
    warnings = check_drive_attachments(rows, "https://drive.google.com/drive/folders/anything", db_session)

    assert warnings == []


# ── Per-customer payment terms (invoice due date) ─────────────────────────────

def test_customer_default_payment_terms_is_15_days(db_session):
    sc = _make_service_code(db_session, "SC-TERMS1")
    customer = _make_customer(db_session, "Default Terms Co", qbo_id="qbo-terms1", email="t1@t1.com")
    assert customer.payment_terms_days == 15
    _make_center(db_session, customer.id, "PAR")
    ps = _make_product(db_session, "Gardening", "qbo-terms-g1")
    _link_service(db_session, customer, ps, sc, 5.0)

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv([("PAR", {"Gardening": 1})], ["Gardening"])
    generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    payload = qbo.invoices[0]
    expected_due = (date.fromisoformat(payload["TxnDate"]) + timedelta(days=15)).isoformat()
    assert payload["DueDate"] == expected_due


def test_customer_custom_payment_terms_used_in_qbo_due_date(db_session):
    sc = _make_service_code(db_session, "SC-TERMS2")
    customer = _make_customer(db_session, "Net 45 Co", qbo_id="qbo-terms2", email="t2@t2.com", payment_terms_days=45)
    _make_center(db_session, customer.id, "PAR")
    ps = _make_product(db_session, "Gardening", "qbo-terms-g2")
    _link_service(db_session, customer, ps, sc, 5.0)

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv([("PAR", {"Gardening": 1})], ["Gardening"])
    generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    payload = qbo.invoices[0]
    expected_due = (date.fromisoformat(payload["TxnDate"]) + timedelta(days=45)).isoformat()
    assert payload["DueDate"] == expected_due


def test_different_customers_get_their_own_due_date_in_same_run(db_session):
    sc = _make_service_code(db_session, "SC-TERMS3")
    fast_customer = _make_customer(db_session, "Net 7 Co", qbo_id="qbo-terms3a", email="t3a@t3a.com", payment_terms_days=7)
    slow_customer = _make_customer(db_session, "Net 60 Co", qbo_id="qbo-terms3b", email="t3b@t3b.com", payment_terms_days=60)
    _make_center(db_session, fast_customer.id, "fastctr")
    _make_center(db_session, slow_customer.id, "slowctr")
    ps1 = _make_product(db_session, "Gardening", "qbo-terms-g3a")
    ps2 = _make_product(db_session, "Cleaning", "qbo-terms-g3b")
    _link_service(db_session, fast_customer, ps1, sc, 5.0)
    _link_service(db_session, slow_customer, ps2, sc, 5.0)

    qbo = FakeQBO()
    csv_bytes = _make_raw_csv(
        [("fastctr", {"Gardening": 1, "Cleaning": 0}), ("slowctr", {"Gardening": 0, "Cleaning": 1})],
        ["Gardening", "Cleaning"],
    )
    result = generate_invoices(db_session, qbo, "tok", "realm", "f.csv", csv_bytes)

    assert result.invoices_created == 2
    by_customer_ref = {inv["CustomerRef"]["value"]: inv for inv in qbo.invoices}
    fast_inv = by_customer_ref["qbo-terms3a"]
    slow_inv = by_customer_ref["qbo-terms3b"]
    assert fast_inv["DueDate"] == (date.fromisoformat(fast_inv["TxnDate"]) + timedelta(days=7)).isoformat()
    assert slow_inv["DueDate"] == (date.fromisoformat(slow_inv["TxnDate"]) + timedelta(days=60)).isoformat()


# ── Endpoint tests ────────────────────────────────────────────────────────────

def test_upload_endpoint_rejects_bad_extension(admin_client):
    r = admin_client.post(
        "/api/v1/invoice-uploads",
        files={"file": ("data.pdf", b"fake", "application/pdf")},
    )
    assert r.status_code == 422


def test_upload_endpoint_accessible_by_supervisor(supervisor_client):
    # Supervisors are now allowed to import files; QBO not connected → 503
    csv_bytes = _make_raw_csv([("x", {"Gardening": 1})], ["Gardening"])
    r = supervisor_client.post(
        "/api/v1/invoice-uploads",
        files={"file": ("data.csv", csv_bytes, "text/csv")},
    )
    assert r.status_code == 503  # QBO not connected, not 401/403


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
    assert gen_inv.send_status == "pending"
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
