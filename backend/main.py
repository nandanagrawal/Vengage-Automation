"""ASGI entry shim — run: uvicorn main:app --reload --port 8000 (from this directory)."""

from app.main import app

__all__ = ["app"]
