"""Persist QuickBooks OAuth tokens (sandbox or prod) and refresh access tokens — POC-compatible."""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from app.core.config import settings

TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _default_token_path() -> Path:
    """Same layout as vengage-poc/backend/tokens.py: ../tokens.json from the backend folder."""
    return (_BACKEND_ROOT.parent / "tokens.json").resolve()


def token_file_path() -> Path:
    raw = settings.TOKEN_FILE_PATH
    if raw:
        p = Path(raw).expanduser()
        # Relative paths resolve from backend package root (…/backend/), not process cwd
        if not p.is_absolute():
            p = (_BACKEND_ROOT / p).resolve()
        else:
            p = p.resolve()
        return p
    return _default_token_path()


@dataclass
class Tokens:
    access_token: str
    refresh_token: str
    access_token_expiry: int  # ms since epoch
    realm_id: str


def save_tokens(tokens: Tokens) -> None:
    path = token_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "accessToken": tokens.access_token,
                "refreshToken": tokens.refresh_token,
                "accessTokenExpiry": tokens.access_token_expiry,
                "realmId": tokens.realm_id,
            },
            f,
            indent=2,
        )
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_tokens() -> Optional[Tokens]:
    path = token_file_path()
    try:
        if not path.is_file():
            return None
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return Tokens(
            access_token=data["accessToken"],
            refresh_token=data["refreshToken"],
            access_token_expiry=data["accessTokenExpiry"],
            realm_id=data["realmId"],
        )
    except Exception:
        return None


def clear_tokens() -> None:
    path = token_file_path()
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        pass


def is_token_expired(tokens: Tokens) -> bool:
    return (time.time() * 1000) > (tokens.access_token_expiry - 60_000)


def refresh_tokens_sync(tokens: Tokens) -> Tokens:
    client_id = settings.QBO_CLIENT_ID or ""
    client_secret = settings.QBO_CLIENT_SECRET or ""
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    with httpx.Client(timeout=60.0) as client:
        res = client.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": tokens.refresh_token,
            },
        )
        res.raise_for_status()
        data = res.json()
    new_tokens = Tokens(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        access_token_expiry=int(time.time() * 1000) + data["expires_in"] * 1000,
        realm_id=tokens.realm_id,
    )
    save_tokens(new_tokens)
    return new_tokens


def get_valid_tokens_sync() -> Optional[Tokens]:
    tokens = load_tokens()
    if not tokens:
        return None
    if is_token_expired(tokens):
        try:
            return refresh_tokens_sync(tokens)
        except Exception:
            clear_tokens()
            return None
    return tokens
