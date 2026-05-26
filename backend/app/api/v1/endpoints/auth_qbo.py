"""QuickBooks OAuth - Intuit App Center (sandbox or production company same URLs)."""

from __future__ import annotations

import logging
import base64
import secrets
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.user import User
from app.services.qbo_tokens import Tokens, clear_tokens, load_tokens, save_tokens

router = APIRouter()
logger = logging.getLogger(__name__)

AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

# In-memory state store: {state_token: expiry_epoch_seconds}
# Single-instance only — sufficient for this app; replace with Redis for multi-instance.
_pending_states: dict[str, float] = {}
_STATE_TTL = 300  # 5 minutes


def _store_state(state: str) -> None:
    _pending_states[state] = time.time() + _STATE_TTL
    # Purge expired entries to prevent unbounded growth
    expired = [k for k, exp in _pending_states.items() if time.time() > exp]
    for k in expired:
        del _pending_states[k]


def _consume_state(state: str) -> bool:
    """Return True and remove the state if it is valid and unexpired."""
    exp = _pending_states.pop(state, None)
    return exp is not None and time.time() <= exp


@router.get("/connect")
def qbo_connect() -> RedirectResponse:
    if not settings.QBO_CLIENT_ID or not settings.QBO_REDIRECT_URI:
        raise HTTPException(
            status_code=503,
            detail="OAuth not configured: set QBO_CLIENT_ID and QBO_REDIRECT_URI in .env",
        )
    state = secrets.token_urlsafe(32)
    _store_state(state)
    params = {
        "client_id": settings.QBO_CLIENT_ID,
        "redirect_uri": settings.QBO_REDIRECT_URI,
        "response_type": "code",
        "scope": "com.intuit.quickbooks.accounting",
        "state": state,
    }
    return RedirectResponse(url=f"{AUTH_URL}?{urlencode(params)}")


@router.get("/callback")
async def qbo_callback(code: str, realmId: str = "", state: str = "") -> RedirectResponse:
    if not state or not _consume_state(state):
        raise HTTPException(status_code=400, detail="OAuth state mismatch - possible CSRF attack.")

    client_id = settings.QBO_CLIENT_ID or ""
    client_secret = settings.QBO_CLIENT_SECRET or ""
    redirect_uri = settings.QBO_REDIRECT_URI or ""
    if not client_id or not client_secret or not redirect_uri:
        raise HTTPException(status_code=503, detail="OAuth client not fully configured.")
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        res.raise_for_status()
        token_data = res.json()

    realm_id = realmId or settings.QBO_REALM_ID or ""
    if not realm_id:
        raise HTTPException(status_code=400, detail="Missing realmId from Intuit redirect.")

    save_tokens(
        Tokens(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            access_token_expiry=int(time.time() * 1000) + token_data["expires_in"] * 1000,
            realm_id=realm_id,
        )
    )
    logger.info("QuickBooks OAuth tokens saved (encrypted)")
    base = settings.FRONTEND_URL.rstrip("/")
    return RedirectResponse(url=f"{base}/dashboard?connected=true")


@router.get("/status")
def qbo_status(
    _user: User = Depends(get_current_user),
    _db: Session = Depends(get_db),
) -> dict:
    tokens = load_tokens()
    return {
        "connected": tokens is not None,
        "realmId": tokens.realm_id if tokens else None,
        "tokenExpiry": tokens.access_token_expiry if tokens else None,
        "environment": settings.QBO_ENVIRONMENT,
    }


@router.delete("/disconnect")
def qbo_disconnect(
    _user: User = Depends(get_current_user),
    _db: Session = Depends(get_db),
) -> dict:
    clear_tokens()
    return {"disconnected": True}


@router.get("/oauth-check")
def oauth_check(
    _user: User = Depends(get_current_user),
    _db: Session = Depends(get_db),
) -> dict:
    """Diagnostic view of OAuth config - compare redirect_uri to Intuit Developer app (exact match)."""
    cid = settings.QBO_CLIENT_ID or ""
    redir = settings.QBO_REDIRECT_URI or ""
    return {
        "authorization_url_template": (
            f"{AUTH_URL}?client_id=...&redirect_uri=...&response_type=code"
            "&scope=com.intuit.quickbooks.accounting&state=<random>"
        ),
        "client_id": cid,
        "client_id_length": len(cid),
        "redirect_uri": redir,
        "redirect_uri_intuit_must_list_exactly": redir,
        "redirect_uri_has_trailing_slash": redir.endswith("/") if redir else False,
        "client_secret_configured": bool(settings.QBO_CLIENT_SECRET),
        "qbo_environment": settings.QBO_ENVIRONMENT,
        "hints": [
            "Intuit -> Your app -> Keys & OAuth -> Redirect URIs: add EXACTLY the redirect_uri value above (localhost vs 127.0.0.1 are different).",
            "For QuickBooks Sandbox companies, use the Development / Sandbox Client ID and Client Secret from that same Keys page - not Production.",
            "After changing Redirect URIs in Intuit, wait a minute and hard-refresh; open Intuit's 'View error details' on the error page for codes like redirect_uri_mismatch.",
        ],
    }
