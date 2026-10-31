"""Append-only, hash-chained audit log. The database also forbids UPDATE/DELETE/TRUNCATE (migration 0001)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection

from niyam.config import get_settings

GENESIS = "0" * 64
_LOCK_KEY = 727001  # advisory lock: serialises appends so the chain has no forks


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(prev: str, tenant: str, ts: str, actor: str, action: str, otype: str, oid: str, payload: dict) -> str:
    body = _canonical([tenant, ts, actor, action, otype, oid, payload])
    return hashlib.sha256((prev + body).encode("utf-8")).hexdigest()


def append(conn: Connection, *, actor: str, action: str, object_type: str, object_id: str, payload: dict | None = None) -> str:
    tenant = get_settings().tenant_id
    payload = payload or {}
    conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _LOCK_KEY})
    prev = conn.execute(
        text("SELECT hash FROM audit_events WHERE tenant_id=:t ORDER BY seq DESC LIMIT 1"), {"t": tenant}
    ).scalar() or GENESIS
    ts = datetime.now(timezone.utc).replace(microsecond=0)
    h = _digest(prev, tenant, ts.isoformat(), actor, action, object_type, object_id, payload)
    conn.execute(
        text(
            "INSERT INTO audit_events (tenant_id, ts, actor, action, object_type, object_id, payload, prev_hash, hash) "
            "VALUES (:t, :ts, :a, :ac, :ot, :oid, CAST(:p AS jsonb), :prev, :h)"
        ),
        {"t": tenant, "ts": ts, "a": actor, "ac": action, "ot": object_type, "oid": object_id, "p": _canonical(payload), "prev": prev, "h": h},
    )
    return h


def verify_chain(conn: Connection) -> dict:
    tenant = get_settings().tenant_id
    rows = conn.execute(
        text("SELECT seq, ts, actor, action, object_type, object_id, payload, prev_hash, hash FROM audit_events "
             "WHERE tenant_id=:t ORDER BY seq"), {"t": tenant}).all()
    prev = GENESIS
    for r in rows:
        ts = r.ts.astimezone(timezone.utc).replace(microsecond=0).isoformat()
        if r.prev_hash != prev or _digest(prev, tenant, ts, r.actor, r.action, r.object_type, r.object_id, r.payload) != r.hash:
            return {"ok": False, "events": len(rows), "broken_at_seq": r.seq}
        prev = r.hash
    return {"ok": True, "events": len(rows), "head": prev}
