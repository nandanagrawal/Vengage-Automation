"""TOTP 2FA: enrollment, verification, backup codes, trusted devices.

Business logic lives here (not in the endpoint file) so it's directly
unit-testable and the endpoints stay thin, matching this codebase's usual
app/services/* split.
"""

from __future__ import annotations

import base64
import hashlib
import io
import secrets
from datetime import datetime, timedelta, timezone

import pyotp
import qrcode
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User, UserBackupCode, UserTrustedDevice
from app.services.auth_service import hash_password, verify_password
from app.services.totp_crypto import decrypt_secret, encrypt_secret

_ISSUER = "Vengage"
_BACKUP_CODE_COUNT = 10


def start_enrollment(db: Session, user: User) -> tuple[str, str]:
    """Generates a fresh secret, saves it (encrypted, inactive until
    confirm_enrollment is called), and returns (qr_code_data_uri,
    manual_entry_key). Safe to call again on a retry — a regenerated,
    not-yet-confirmed secret replacing an old unconfirmed one is harmless."""
    secret = pyotp.random_base32()
    user.totp_secret = encrypt_secret(secret)
    db.add(user)
    db.commit()

    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=_ISSUER)
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    return qr_data_uri, secret


def verify_totp_code(user: User, code: str) -> bool:
    if not user.totp_secret:
        return False
    secret = decrypt_secret(user.totp_secret)
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def _generate_backup_codes(db: Session, user: User) -> list[str]:
    # Regenerating replaces the set outright — old codes stop working.
    db.query(UserBackupCode).filter(UserBackupCode.user_id == user.id).delete()
    codes = [secrets.token_hex(4) for _ in range(_BACKUP_CODE_COUNT)]
    for code in codes:
        db.add(UserBackupCode(user_id=user.id, code_hash=hash_password(code)))
    db.commit()
    return codes


def confirm_enrollment(db: Session, user: User, code: str) -> list[str]:
    """Verifies the first code and activates 2FA. Raises ValueError on a
    wrong code — the caller maps that to a 400."""
    if not verify_totp_code(user, code):
        raise ValueError("Invalid code")
    user.totp_enabled = True
    db.add(user)
    db.commit()
    return _generate_backup_codes(db, user)


def regenerate_backup_codes(db: Session, user: User, code: str) -> list[str]:
    if not verify_totp_code(user, code):
        raise ValueError("Invalid code")
    return _generate_backup_codes(db, user)


def verify_login_code(db: Session, user: User, code: str) -> bool:
    """Tries `code` as a TOTP code first, then as an unused backup code
    (consuming it on a match so it can't be reused). True on success."""
    if verify_totp_code(user, code):
        return True

    rows = (
        db.query(UserBackupCode)
        .filter(UserBackupCode.user_id == user.id, UserBackupCode.used_at.is_(None))
        .all()
    )
    for row in rows:
        if verify_password(code, row.code_hash):
            row.used_at = datetime.now(timezone.utc)
            db.add(row)
            db.commit()
            return True
    return False


def reset_2fa(db: Session, user: User) -> None:
    """Admin-assisted recovery for a lost device + lost backup codes:
    clears everything so the user is forced through enrollment again on
    their next login."""
    user.totp_secret = None
    user.totp_enabled = False
    db.add(user)
    db.query(UserBackupCode).filter(UserBackupCode.user_id == user.id).delete()
    db.query(UserTrustedDevice).filter(UserTrustedDevice.user_id == user.id).delete()
    db.commit()


# ── Trusted devices ("remember this browser for N days") ───────────────────

def _hash_device_token(token: str) -> str:
    # SHA-256, not bcrypt: the token is already a 32-byte random secret with
    # ample entropy, and this needs a fast indexed exact-match lookup on
    # every login — bcrypt's per-row salt makes that impossible.
    return hashlib.sha256(token.encode()).hexdigest()


def issue_trusted_device_token(db: Session, user: User, user_agent: str | None) -> str:
    token = secrets.token_urlsafe(32)
    db.add(
        UserTrustedDevice(
            user_id=user.id,
            token_hash=_hash_device_token(token),
            user_agent=user_agent[:500] if user_agent else None,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.TRUSTED_DEVICE_DAYS),
        )
    )
    db.commit()
    return token


def is_trusted_device(db: Session, user_id: int, token: str | None) -> bool:
    if not token:
        return False
    row = (
        db.query(UserTrustedDevice)
        .filter(
            UserTrustedDevice.user_id == user_id,
            UserTrustedDevice.token_hash == _hash_device_token(token),
        )
        .first()
    )
    if not row:
        return False
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at > datetime.now(timezone.utc)
