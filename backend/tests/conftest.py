"""Shared test fixtures — SQLite in-memory DB, FakeQBO, auth helpers."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Configure test DB and QBO env BEFORE importing app
_fd, _TEST_DB_PATH = tempfile.mkstemp(suffix="-vengage-test.db")
os.close(_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
_ATTACH_DIR = tempfile.mkdtemp(prefix="vengage-test-attach-")
os.environ["CUSTOMER_ATTACHMENTS_DIR"] = _ATTACH_DIR
os.environ["QBO_ACCESS_TOKEN"] = "test-token"
os.environ["QBO_REALM_ID"] = "test-realm"
os.environ["JWT_SECRET"] = "test-secret-for-pytest-only"

_tf = tempfile.NamedTemporaryFile(prefix="vengage-test-qbo-", suffix=".json", delete=False)
_tf.close()
os.unlink(_tf.name)
os.environ["TOKEN_FILE_PATH"] = _tf.name

from app.api.deps import get_qbo_client  # noqa: E402
from app.main import app  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402

# Create all tables for the SQLite test DB
init_db()
from app.models.center import Center  # noqa: E402
from app.models.customer import Customer  # noqa: E402
from app.models.customer_attachment import CustomerAttachment  # noqa: E402
from app.models.customer_product_and_service import CustomerProductAndService  # noqa: E402
from app.models.customer_type import CustomerType  # noqa: E402
from app.models.generated_invoice import GeneratedInvoice, GeneratedInvoiceCenter, GeneratedInvoiceLineItem  # noqa: E402
from app.models.invoice import Invoice  # noqa: E402
from app.models.invoice_email_activity import InvoiceEmailActivity  # noqa: E402
from app.models.invoice_upload import InvoiceUpload  # noqa: E402
from app.models.product_and_service import ProductAndService  # noqa: E402
from app.models.service_code import ServiceCode  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.services.auth_service import create_access_token, hash_password  # noqa: E402


# ── Fake QuickBooks client ────────────────────────────────────────────────────

class FakeQBO:
    def __init__(self) -> None:
        self.customers: list[dict] = []
        self.invoices: list[dict] = []
        self.items: list[dict] = []
        self._next_id = 100
        self._next_attach_id = 1
        # customer QBO id -> attachable records (mirrors QBO query by customer)
        self.attachables_by_customer: dict[str, list[dict]] = {}

    def base_url(self) -> str:
        return "https://example.test"

    def query_customers(self, access_token: str, realm_id: str) -> list[dict]:
        return list(self.customers)

    def get_customer(self, access_token: str, realm_id: str, customer_id: str) -> dict:
        for c in self.customers:
            if str(c.get("Id")) == str(customer_id):
                return c
        return {
            "Id": customer_id,
            "DisplayName": "Webhook Customer",
            "SyncToken": "0",
            "MetaData": {"LastUpdatedTime": "2026-01-01T12:00:00+00:00"},
        }

    def create_customer(self, access_token: str, realm_id: str, payload: dict) -> dict:
        self._next_id += 1
        cid = str(self._next_id)
        obj = {
            "Id": cid,
            "SyncToken": "0",
            "DisplayName": payload.get("DisplayName", "X"),
            "MetaData": {"LastUpdatedTime": "2026-01-02T12:00:00+00:00"},
        }
        self.customers.append({**payload, **obj})
        return obj

    def update_customer(self, access_token, realm_id, customer_id, payload, sync_token):
        return {
            "Id": customer_id,
            "SyncToken": str(int(sync_token or "0") + 1),
            "DisplayName": payload.get("DisplayName", "X"),
            "MetaData": {"LastUpdatedTime": "2026-01-03T12:00:00+00:00"},
        }

    def query_invoice_email_rows(self, access_token, realm_id, since) -> list[dict]:
        return list(self.invoices)

    def query_attachables_for_customer(self, access_token, realm_id, customer_qbo_id: str) -> list[dict]:
        return list(self.attachables_by_customer.get(str(customer_qbo_id), []))

    def query_items(self, access_token: str, realm_id: str) -> list[dict]:
        return list(self.items)

    def upload_attachment(self, access_token, realm_id, customer_id, filename, content_type, file_bytes):
        aid = f"att-{self._next_attach_id}"
        self._next_attach_id += 1
        rec = {"Id": aid, "FileName": filename}
        self.attachables_by_customer.setdefault(str(customer_id), []).append(rec)
        return {"Attachable": {"Id": aid, "FileName": filename}}

    def create_invoice(self, access_token: str, realm_id: str, payload: dict) -> dict:
        self._next_id += 1
        inv_id = str(self._next_id)
        obj = {"Id": inv_id, "SyncToken": "0", "EmailStatus": "NotSet", "DocNumber": f"INV-{self._next_id}"}
        self.invoices.append({**payload, **obj})
        return obj

    def send_invoice(self, access_token: str, realm_id: str, invoice_id: str, email=None) -> dict:
        for inv in self.invoices:
            if str(inv.get("Id")) == str(invoice_id):
                inv["EmailStatus"] = "EmailSent"
                return inv
        return {"Id": invoice_id, "EmailStatus": "EmailSent"}

    def attach_to_invoice(self, access_token, realm_id, invoice_id, filename, content_type, file_bytes) -> dict:
        aid = f"inv-att-{self._next_attach_id}"
        self._next_attach_id += 1
        return {"Attachable": {"Id": aid, "FileName": filename}}


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_user(db, email: str, role: UserRole, full_name: str = "") -> User:
    u = User(
        email=email,
        full_name=full_name or role.value.capitalize(),
        password_hash=hash_password("password123"),
        role=role,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def token_for(user: User) -> str:
    return create_access_token(user.id, user.email, user.role.value)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_qbo():
    return FakeQBO()


@pytest.fixture(autouse=True)
def reset_db():
    db = SessionLocal()
    db.query(GeneratedInvoiceLineItem).delete()
    db.query(GeneratedInvoiceCenter).delete()
    db.query(GeneratedInvoice).delete()
    db.query(InvoiceUpload).delete()
    db.query(Invoice).delete()
    db.query(InvoiceEmailActivity).delete()
    db.query(CustomerAttachment).delete()
    db.query(CustomerProductAndService).delete()
    db.query(ProductAndService).delete()
    db.query(ServiceCode).delete()
    db.query(Center).delete()
    db.query(Customer).delete()
    db.query(CustomerType).delete()
    db.query(User).delete()
    db.commit()
    db.close()


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def admin_user(db_session):
    return make_user(db_session, "admin@test.com", UserRole.admin, "Test Admin")


@pytest.fixture
def supervisor_user(db_session):
    return make_user(db_session, "sup@test.com", UserRole.supervisor, "Test Supervisor")


@pytest.fixture
def client(fake_qbo):
    app.dependency_overrides[get_qbo_client] = lambda: fake_qbo
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def admin_client(fake_qbo, admin_user):
    tok = token_for(admin_user)
    app.dependency_overrides[get_qbo_client] = lambda: fake_qbo
    with TestClient(app, headers={"Authorization": f"Bearer {tok}"}) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def supervisor_client(fake_qbo, supervisor_user):
    tok = token_for(supervisor_user)
    app.dependency_overrides[get_qbo_client] = lambda: fake_qbo
    with TestClient(app, headers={"Authorization": f"Bearer {tok}"}) as c:
        yield c
    app.dependency_overrides.clear()
