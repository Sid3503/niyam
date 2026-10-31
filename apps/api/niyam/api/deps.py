from __future__ import annotations

import secrets

from fastapi import Header, HTTPException

from niyam.config import get_settings


def require_key(x_api_key: str | None = Header(default=None)) -> None:
    """Enforced only when NIYAM_API_KEY is set. In prod the app refuses to start without one (see main.py)."""
    key = get_settings().api_key
    if not key:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, key):
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "missing or invalid X-API-Key"})
