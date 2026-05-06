"""Auth endpoint tests: register, login, me, role enforcement."""

from tests.conftest import make_user, token_for
from app.models.user import UserRole


# ── Register ──────────────────────────────────────────────────────────────────

def test_bootstrap_creates_first_admin(client):
    r = client.post("/api/v1/auth/register/first", json={
        "email": "admin@example.com",
        "full_name": "First Admin",
        "password": "securepass",
        "role": "admin",
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["role"] == "admin"
    assert data["email"] == "admin@example.com"


def test_bootstrap_blocked_after_first_user(client, admin_user):
    r = client.post("/api/v1/auth/register/first", json={
        "email": "second@example.com",
        "full_name": "Second",
        "password": "password123",
        "role": "admin",
    })
    assert r.status_code == 403


def test_bootstrap_rejects_non_admin_role(client):
    r = client.post("/api/v1/auth/register/first", json={
        "email": "sup@example.com",
        "full_name": "Bad",
        "password": "password123",
        "role": "supervisor",
    })
    assert r.status_code == 400


def test_admin_registers_supervisor(admin_client, admin_user):
    r = admin_client.post("/api/v1/auth/register", json={
        "email": "newsup@example.com",
        "full_name": "New Supervisor",
        "password": "password123",
        "role": "supervisor",
    })
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "supervisor"


def test_supervisor_cannot_register_users(supervisor_client):
    r = supervisor_client.post("/api/v1/auth/register", json={
        "email": "another@example.com",
        "full_name": "Another",
        "password": "password123",
        "role": "supervisor",
    })
    assert r.status_code == 403


def test_duplicate_email_rejected(admin_client, admin_user):
    r = admin_client.post("/api/v1/auth/register", json={
        "email": admin_user.email,
        "full_name": "Dup",
        "password": "password123",
        "role": "supervisor",
    })
    assert r.status_code == 409


# ── Login ─────────────────────────────────────────────────────────────────────

def test_login_success(client, admin_user):
    r = client.post("/api/v1/auth/login", json={"email": admin_user.email, "password": "password123"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password(client, admin_user):
    r = client.post("/api/v1/auth/login", json={"email": admin_user.email, "password": "wrongpass"})
    assert r.status_code == 401


def test_login_unknown_email(client):
    r = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "pass"})
    assert r.status_code == 401


# ── Me ────────────────────────────────────────────────────────────────────────

def test_me_returns_current_user(client, admin_user):
    tok = token_for(admin_user)
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == admin_user.email
    assert data["role"] == "admin"


def test_me_unauthenticated(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_me_invalid_token(client):
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer bad.token.here"})
    assert r.status_code == 401
