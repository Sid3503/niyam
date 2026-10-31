"""Content-addressed blob store for original PDF / audio bytes. Stand-in for the object store in docs/NIYAM-PRODUCTION-ARCHITECTURE.md.
Blobs are immutable: the key is the sha256 of the bytes, so a version can never be silently rewritten."""
from __future__ import annotations

import hashlib

from niyam.config import get_settings


def put(data: bytes) -> tuple[str, str]:
    h = hashlib.sha256(data).hexdigest()
    p = get_settings().blob_path / h[:2] / h
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(p)
    return h, h


def get(key: str) -> bytes:
    return (get_settings().blob_path / key[:2] / key).read_bytes()
