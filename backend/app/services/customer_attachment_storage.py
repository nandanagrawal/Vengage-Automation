"""Local filesystem storage for customer attachments + QBO upload response parsing."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import settings


def attachments_base_dir() -> Path:
    p = Path(settings.CUSTOMER_ATTACHMENTS_DIR).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    return p.resolve()


def sanitize_filename(name: str, max_len: int = 180) -> str:
    base = Path(name).name
    base = re.sub(r"[^a-zA-Z0-9._-]", "_", base).strip("._") or "file"
    return base[:max_len]


def new_storage_relpath(customer_id: int, original_filename: str) -> str:
    uid = uuid4().hex[:16]
    safe = sanitize_filename(original_filename)
    return f"{customer_id}/{uid}_{safe}"


def full_path_for_relpath(relpath: str) -> Path:
    return attachments_base_dir() / relpath


def write_bytes_atomic(relpath: str, content: bytes) -> None:
    path = full_path_for_relpath(relpath)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(content)
    tmp.replace(path)


def delete_stored_file(relpath: str) -> None:
    p = full_path_for_relpath(relpath)
    try:
        p.unlink(missing_ok=True)
    except OSError:
        pass
    try:
        parent = p.parent
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
    except OSError:
        pass


def parse_qbo_attachable_id(data: dict[str, Any]) -> str | None:
    """Extract Attachable Id from QBO multipart upload JSON (shape varies slightly)."""
    ar = data.get("AttachableResponse")
    if isinstance(ar, list) and ar:
        first = ar[0]
        if isinstance(first, dict):
            att = first.get("Attachable")
            if isinstance(att, dict) and att.get("Id") is not None:
                return str(att["Id"])
    att = data.get("Attachable")
    if isinstance(att, dict) and att.get("Id") is not None:
        return str(att["Id"])
    return None
