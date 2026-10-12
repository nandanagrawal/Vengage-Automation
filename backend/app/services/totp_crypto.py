"""Encrypt/decrypt TOTP secrets at rest — mirrors the Fernet/HKDF pattern in
app/services/qbo_tokens.py, but with its own salt/info so a TOTP-secret key
is never the same as the QBO-token key even when both fall back to
deriving from JWT_SECRET (unrelated secret domains, separate keys)."""

from __future__ import annotations

import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import settings

_fernet_instance: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    if settings.TOTP_ENCRYPTION_KEY:
        raw = settings.TOTP_ENCRYPTION_KEY.encode()
        try:
            _fernet_instance = Fernet(raw)
        except Exception:
            key = base64.urlsafe_b64encode(
                HKDF(algorithm=hashes.SHA256(), length=32, salt=b"vengage-totp-v1", info=b"totp-enc").derive(raw)
            )
            _fernet_instance = Fernet(key)
    else:
        key = base64.urlsafe_b64encode(
            HKDF(algorithm=hashes.SHA256(), length=32, salt=b"vengage-totp-v1", info=b"totp-enc").derive(
                settings.JWT_SECRET.encode()
            )
        )
        _fernet_instance = Fernet(key)

    return _fernet_instance


def encrypt_secret(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return _get_fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        raise ValueError("Could not decrypt TOTP secret — wrong or rotated TOTP_ENCRYPTION_KEY")
