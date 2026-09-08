"""Google Drive read-only client — pulls per-center raw-data files from a
shared Drive folder so they can be attached to the matching QBO invoice via
QuickBooksClient.attach_to_invoice (see qbo_client.py).

Auth: a Google service account JSON key, referenced by
settings.GOOGLE_SERVICE_ACCOUNT_KEY_PATH (.env-only, never committed). That
service account must be shared on the target Drive folder as at least
Viewer — it has no access otherwise, "Shared with me" doesn't apply to
service accounts.
"""

from __future__ import annotations

import io
import re
from functools import lru_cache
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from app.core.config import settings

_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
_GOOGLE_SHEET_MIME = "application/vnd.google-apps.spreadsheet"
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Matches ".../folders/<id>" (the standard share-link shape) or a bare "?id=<id>".
_FOLDER_ID_IN_PATH_RE = re.compile(r"/folders/([a-zA-Z0-9_-]+)")
_FOLDER_ID_IN_QUERY_RE = re.compile(r"[?&]id=([a-zA-Z0-9_-]+)")
_BARE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{10,}$")

_SPREADSHEET_EXT_RE = re.compile(r"\.(xlsx|xls)$", re.IGNORECASE)


def ensure_drive_credentials() -> None:
    if not settings.GOOGLE_SERVICE_ACCOUNT_KEY_PATH:
        raise RuntimeError(
            "Google Drive is not configured. Set GOOGLE_SERVICE_ACCOUNT_KEY_PATH "
            "to the service account JSON key file path in .env."
        )


@lru_cache(maxsize=1)
def _build_service() -> Any:
    ensure_drive_credentials()
    creds = service_account.Credentials.from_service_account_file(
        settings.GOOGLE_SERVICE_ACCOUNT_KEY_PATH, scopes=_SCOPES
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def extract_folder_id(url_or_id: str) -> str:
    """Pull a folder ID out of a Drive folder share URL, or pass a bare ID through."""
    s = url_or_id.strip()
    m = _FOLDER_ID_IN_PATH_RE.search(s)
    if m:
        return m.group(1)
    m = _FOLDER_ID_IN_QUERY_RE.search(s)
    if m:
        return m.group(1)
    if _BARE_ID_RE.match(s):
        return s
    raise ValueError(f"Could not find a Drive folder ID in {url_or_id!r}")


def list_folder_files(folder_id: str) -> list[dict]:
    """Spreadsheet-like files (xlsx/xls, or native Google Sheets) directly
    inside the given folder — not recursive into subfolders.

    Passes the Shared Drive support flags unconditionally: harmless no-ops
    for a regular "My Drive" folder, but required (silently returns zero
    results without them) when the folder lives inside a Shared Drive — and
    there's no reliable way to tell which one we're dealing with from the
    folder ID alone."""
    service = _build_service()
    files: list[dict] = []
    page_token: str | None = None
    query = f"'{folder_id}' in parents and trashed = false"
    while True:
        resp = (
            service.files()
            .list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora="allDrives",
            )
            .execute()
        )
        for f in resp.get("files", []):
            name = f.get("name", "")
            if f.get("mimeType") == _GOOGLE_SHEET_MIME or _SPREADSHEET_EXT_RE.search(name):
                files.append(f)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return files


def match_center_files(folder_id: str) -> dict[str, dict]:
    """{center_name_lower: {id, name, mimeType}} — one file per matched center
    name (file name with the .xlsx/.xls extension stripped, lowercased), the
    same case-insensitive convention used for the main sheet's Center ID
    column. On a name collision the file with the latest modifiedTime wins.
    """
    matched: dict[str, dict] = {}
    for f in list_folder_files(folder_id):
        stem = _SPREADSHEET_EXT_RE.sub("", f.get("name", "")).strip().lower()
        if not stem:
            continue
        existing = matched.get(stem)
        if existing is None or f.get("modifiedTime", "") > existing.get("modifiedTime", ""):
            matched[stem] = f
    return matched


def download_file(file_id: str, mime_type: str) -> tuple[bytes, str]:
    """Returns (content_bytes, content_type). Native Google Sheets are
    exported as .xlsx; real .xlsx/.xls files are downloaded as-is."""
    service = _build_service()
    if mime_type == _GOOGLE_SHEET_MIME:
        # export_media doesn't take supportsAllDrives — not needed for a
        # direct file-ID export the way it is for listing a Shared Drive.
        request = service.files().export_media(fileId=file_id, mimeType=_XLSX_MIME)
        content_type = _XLSX_MIME
    else:
        request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
        content_type = mime_type or _XLSX_MIME

    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue(), content_type
