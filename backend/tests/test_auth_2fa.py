"""Two-factor auth: setup enrollment, verify login, backup codes, trusted
devices, admin reset, and the token-type bypass fix."""

from datetime import datetime, timedelta, timezone

import pyotp

from app.models.user import UserBackupCode, UserTrustedDevice
from app.services.auth_service import create_pending_2fa_token


def _login(client, email, password="password123"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


# ── First login: forced enrollment ──────────────────────────────────────────

def test_login_for_new_user_requires_setup(client, admin_user):
    r = _login(client, admin_user.email)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "setup_required"
    assert body["access_token"] is None
    assert body["pending_token"]
    assert body["qr_code_data_uri"].startswith("data:image/png;base64,")
    assert body["manual_entry_key"]


def test_setup_confirm_with_correct_code_issues_token_and_backup_codes(client, admin_user, db_session):
    r = _login(client, admin_user.email)
    body = r.json()
    secret = body["manual_entry_key"]
    code = pyotp.TOTP(secret).now()

    r2 = client.post("/api/v1/auth/2fa/setup/confirm", json={
        "pending_token": body["pending_token"],
        "code": code,
    })
    assert r2.status_code == 200, r2.text
    out = r2.json()
    assert out["status"] == "success"
    assert out["access_token"]
    assert len(out["backup_codes"]) == 10

    db_session.refresh(admin_user)
    assert admin_user.totp_enabled is True

    # New access token actually works against a protected endpoint.
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {out['access_token']}"})
    assert me.status_code == 200
    assert me.json()["totp_enabled"] is True


def test_setup_confirm_with_wrong_code_rejected(client, admin_user):
    r = _login(client, admin_user.email)
    pending = r.json()["pending_token"]
    r2 = client.post("/api/v1/auth/2fa/setup/confirm", json={"pending_token": pending, "code": "000000"})
    assert r2.status_code == 400


# ── Subsequent login: already enrolled ──────────────────────────────────────

def _enroll(client, user, email=None):
    r = _login(client, email or user.email)
    body = r.json()
    secret = body["manual_entry_key"]
    code = pyotp.TOTP(secret).now()
    r2 = client.post("/api/v1/auth/2fa/setup/confirm", json={"pending_token": body["pending_token"], "code": code})
    return secret, r2.json()


def test_login_for_enrolled_user_requires_verify(client, admin_user):
    secret, _ = _enroll(client, admin_user)
    r = _login(client, admin_user.email)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "verify_required"
    assert body["pending_token"]
    assert body["access_token"] is None


def test_verify_with_correct_totp_issues_token(client, admin_user):
    secret, _ = _enroll(client, admin_user)
    r = _login(client, admin_user.email)
    pending = r.json()["pending_token"]
    code = pyotp.TOTP(secret).now()
    r2 = client.post("/api/v1/auth/2fa/verify", json={"pending_token": pending, "code": code})
    assert r2.status_code == 200, r2.text
    assert r2.json()["access_token"]


def test_verify_with_wrong_code_rejected(client, admin_user):
    _enroll(client, admin_user)
    r = _login(client, admin_user.email)
    pending = r.json()["pending_token"]
    r2 = client.post("/api/v1/auth/2fa/verify", json={"pending_token": pending, "code": "000000"})
    assert r2.status_code == 400


def test_backup_code_works_once_then_rejected(client, admin_user):
    secret, setup_out = _enroll(client, admin_user)
    backup_code = setup_out["backup_codes"][0]

    r = _login(client, admin_user.email)
    pending = r.json()["pending_token"]
    r2 = client.post("/api/v1/auth/2fa/verify", json={"pending_token": pending, "code": backup_code})
    assert r2.status_code == 200, r2.text

    r3 = _login(client, admin_user.email)
    pending2 = r3.json()["pending_token"]
    r4 = client.post("/api/v1/auth/2fa/verify", json={"pending_token": pending2, "code": backup_code})
    assert r4.status_code == 400


# ── Trusted device cookie ───────────────────────────────────────────────────

def test_remember_device_skips_challenge_within_window(client, admin_user):
    secret, _ = _enroll(client, admin_user)
    r = _login(client, admin_user.email)
    pending = r.json()["pending_token"]
    code = pyotp.TOTP(secret).now()
    r2 = client.post("/api/v1/auth/2fa/verify", json={
        "pending_token": pending, "code": code, "remember_device": True,
    })
    assert r2.status_code == 200
    assert "vengage_trusted_device" in client.cookies

    r3 = _login(client, admin_user.email)
    assert r3.status_code == 200
    assert r3.json()["status"] == "success"
    assert r3.json()["access_token"]


def test_expired_trusted_device_requires_verify_again(client, admin_user, db_session):
    secret, _ = _enroll(client, admin_user)
    r = _login(client, admin_user.email)
    pending = r.json()["pending_token"]
    code = pyotp.TOTP(secret).now()
    client.post("/api/v1/auth/2fa/verify", json={
        "pending_token": pending, "code": code, "remember_device": True,
    })
    assert "vengage_trusted_device" in client.cookies

    row = db_session.query(UserTrustedDevice).filter(UserTrustedDevice.user_id == admin_user.id).first()
    row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.add(row)
    db_session.commit()

    r2 = _login(client, admin_user.email)
    assert r2.json()["status"] == "verify_required"


# ── Admin reset / recovery ──────────────────────────────────────────────────

def test_admin_reset_2fa_forces_setup_again(client, admin_client, admin_user, db_session):
    _enroll(client, admin_user)
    db_session.refresh(admin_user)
    assert admin_user.totp_enabled is True

    r = admin_client.post(f"/api/v1/auth/users/{admin_user.id}/reset-2fa")
    assert r.status_code == 200, r.text
    assert r.json()["totp_enabled"] is False

    db_session.refresh(admin_user)
    assert db_session.query(UserBackupCode).filter(UserBackupCode.user_id == admin_user.id).count() == 0

    r2 = _login(client, admin_user.email)
    assert r2.json()["status"] == "setup_required"


def test_non_admin_cannot_reset_2fa(supervisor_client, supervisor_user):
    r = supervisor_client.post(f"/api/v1/auth/users/{supervisor_user.id}/reset-2fa")
    assert r.status_code == 403


# ── Backup code regeneration ────────────────────────────────────────────────

def test_regenerate_backup_codes_requires_current_code(client, admin_user):
    secret, _ = _enroll(client, admin_user)
    tok = None
    r = _login(client, admin_user.email)
    pending = r.json()["pending_token"]
    code = pyotp.TOTP(secret).now()
    r2 = client.post("/api/v1/auth/2fa/verify", json={"pending_token": pending, "code": code})
    tok = r2.json()["access_token"]

    bad = client.post("/api/v1/auth/2fa/backup-codes/regenerate", json={"code": "000000"},
                       headers={"Authorization": f"Bearer {tok}"})
    assert bad.status_code == 400

    good_code = pyotp.TOTP(secret).now()
    ok = client.post("/api/v1/auth/2fa/backup-codes/regenerate", json={"code": good_code},
                      headers={"Authorization": f"Bearer {tok}"})
    assert ok.status_code == 200, ok.text
    assert len(ok.json()["backup_codes"]) == 10


# ── Token-type bypass fix ────────────────────────────────────────────────────

def test_pending_2fa_token_rejected_as_access_token(client, admin_user):
    pending = create_pending_2fa_token(admin_user.id)
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {pending}"})
    assert r.status_code == 401
