"""QuickBooks OAuth — Intuit App Center (sandbox or production company same URLs)."""

from __future__ import annotations

import logging
import base64
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.services.qbo_tokens import Tokens, clear_tokens, load_tokens, save_tokens, token_file_path

router = APIRouter()
logger = logging.getLogger(__name__)

AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"


@router.get("/connect")
def qbo_connect() -> RedirectResponse:
    if not settings.QBO_CLIENT_ID or not settings.QBO_REDIRECT_URI:
        raise HTTPException(
            status_code=503,
            detail="OAuth not configured: set QBO_CLIENT_ID and QBO_REDIRECT_URI in .env",
        )
    params = {
        "client_id": settings.QBO_CLIENT_ID,
        "redirect_uri": settings.QBO_REDIRECT_URI,
        "response_type": "code",
        "scope": "com.intuit.quickbooks.accounting",
        "state": "vengage",
    }
    return RedirectResponse(url=f"{AUTH_URL}?{urlencode(params)}")


@router.get("/callback")
async def qbo_callback(code: str, realmId: str = "", state: str = "") -> RedirectResponse:
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
    dest = token_file_path()
    logger.info("QuickBooks OAuth tokens saved to %s", dest)
    base = settings.FRONTEND_URL.rstrip("/")
    return RedirectResponse(url=f"{base}/dashboard?connected=true")


@router.get("/status")
def qbo_status() -> dict:
    tokens = load_tokens()
    return {
        "connected": tokens is not None,
        "realmId": tokens.realm_id if tokens else None,
        "tokenExpiry": tokens.access_token_expiry if tokens else None,
        "environment": settings.QBO_ENVIRONMENT,
        "token_file_path": str(token_file_path()),
    }


@router.delete("/disconnect")
def qbo_disconnect() -> dict:
    clear_tokens()
    return {"disconnected": True}


@router.get("/oauth-check")
def oauth_check() -> dict:
    """Non-secret view of what /connect sends — compare redirect_uri to Intuit Developer app (exact match)."""
    cid = settings.QBO_CLIENT_ID or ""
    redir = settings.QBO_REDIRECT_URI or ""
    dest = token_file_path()
    return {
        "authorization_url_template": f"{AUTH_URL}?client_id=…&redirect_uri=…&response_type=code&scope=com.intuit.quickbooks.accounting&state=vengage",
        "client_id": cid,
        "client_id_length": len(cid),
        "redirect_uri": redir,
        "redirect_uri_intuit_must_list_exactly": redir,
        "redirect_uri_has_trailing_slash": redir.endswith("/") if redir else False,
        "client_secret_configured": bool(settings.QBO_CLIENT_SECRET),
        "qbo_environment": settings.QBO_ENVIRONMENT,
        "token_file_path": str(dest),
        "token_file_note": "tokens.json is created only after Intuit redirects successfully to /api/auth/callback (OAuth completes).",
        "hints": [
            "Intuit → Your app → Keys & OAuth → Redirect URIs: add EXACTLY the redirect_uri value above (localhost vs 127.0.0.1 are different).",
            "For QuickBooks Sandbox companies, use the Development / Sandbox Client ID and Client Secret from that same Keys page — not Production.",
            "After changing Redirect URIs in Intuit, wait a minute and hard-refresh; open Intuit's “View error details” on the error page for codes like redirect_uri_mismatch.",
            "Default token path matches vengage-poc: repo-root tokens.json (or TOKEN_FILE_PATH).",
        ],
    }
