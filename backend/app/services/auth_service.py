from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

_PENDING_2FA_EXPIRE_MINUTES = 5


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: int, email: str, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "typ": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def create_pending_2fa_token(user_id: int) -> str:
    """Issued after a correct password but before a 2FA code is verified.
    Deliberately carries no email/role — its only legitimate use is the
    /auth/2fa/* endpoints, which look the user back up by id; it must never
    be usable as a stand-in for a real access token (see decode_token's
    `typ` check in get_current_user)."""
    payload = {
        "sub": str(user_id),
        "typ": "2fa_pending",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=_PENDING_2FA_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc


def decode_pending_2fa_token(token: str) -> int:
    """Returns the user id if `token` is a valid, unexpired 2fa_pending
    token; raises ValueError otherwise (bad signature, expired, or a real
    access token used where a pending one is required)."""
    payload = decode_token(token)
    if payload.get("typ") != "2fa_pending":
        raise ValueError("Not a pending 2FA token")
    return int(payload["sub"])
