"""Rule cards: load JSON from disk, validate against the stored sources, sync to Postgres.

Validation reuses rules/validate.py (single source of truth for the card contract) but points its text extraction at
niyam.kb.extract, so a quote is checked against the same text the knowledge base indexes. A card that passes the CLI but fails
here (or vice versa) shows up as a validation error: that is deliberate, it means the two extractions disagree.
Only a human can make a card `active` (DB CHECK + validator); this module never changes a card's status.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import logging
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection

from niyam.config import get_settings
from niyam.db import audit
from niyam.kb.extract import norm, raw_text

log = logging.getLogger("niyam.rules")
_validator = None
_text_cache: dict[str, str] = {}


def _load_validator():
    global _validator
    if _validator is not None:
        return _validator
    s = get_settings()
    path = s.data_root / "rules" / "validate.py"
    spec = importlib.util.spec_from_file_location("niyam_rules_validate", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ROOT = str(s.data_root)

    def source_text(p: str) -> str:
        if p not in _text_cache:
            _text_cache[p] = norm(raw_text(Path(p)))
        return _text_cache[p]

    mod.source_text = source_text
    _validator = mod
    return mod


def as_of_date() -> dt.date:
    o = get_settings().as_of_override
    return dt.date.fromisoformat(o) if o else dt.date.today()


def read_cards(rules_dir: Path | None = None) -> list[tuple[Path, dict, str]]:
    d = rules_dir or get_settings().rules_path
    out = []
    for p in sorted(d.glob("*.json")):
        raw = p.read_bytes()
        out.append((p, json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()))
    return out


def validate_card(path: Path, card: dict, as_of: dt.date) -> dict:
    v = _load_validator()
    try:
        errs, warns, info = v.validate_card(str(path), card, as_of, False, set())
    except Exception as e:  # noqa: BLE001
        errs, warns, info = [f"validator crashed: {type(e).__name__}: {e}"], [], []
    quote_errs = [e for e in errs if "quote" in e or "sha256" in e or "source.file" in e]
    return {"ok": not errs, "errors": errs, "warnings": warns, "info": info, "quotes_verified": not quote_errs and not errs,
            "validated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}


def sync(conn: Connection) -> dict:
    s = get_settings()
    as_of = as_of_date()
    stats = {"cards": 0, "valid": 0, "invalid": 0, "skipped_active_changed": 0}
    shas = {}
    for path, card, sha in read_cards():
        val = validate_card(path, card, as_of)
        stats["cards"] += 1
        stats["valid" if val["ok"] else "invalid"] += 1
        shas[f"{card.get('id')}.v{card.get('version')}"] = sha
        existing = conn.execute(text("SELECT status FROM rule_cards WHERE tenant_id=:t AND id=:i AND version=:v"),
                                {"t": s.tenant_id, "i": card["id"], "v": card["version"]}).scalar()
        if existing and existing != "draft":      # a human decision lives in the database; the file never overrides it
            stats["skipped_active_changed"] += 1
            continue
        try:
            conn.execute(
                text(
                    """INSERT INTO rule_cards (tenant_id, id, version, status, title, severity, tier, check_type, effective_from, regulator,
                                               card, card_sha256, validation)
                       VALUES (:t, :id, :v, :st, :title, :sev, :tier, :ct, :eff, :reg, CAST(:card AS jsonb), :sha, CAST(:val AS jsonb))
                       ON CONFLICT (tenant_id, id, version) DO UPDATE
                       SET status=EXCLUDED.status, title=EXCLUDED.title, severity=EXCLUDED.severity, tier=EXCLUDED.tier,
                           check_type=EXCLUDED.check_type, effective_from=EXCLUDED.effective_from, regulator=EXCLUDED.regulator,
                           card=EXCLUDED.card, card_sha256=EXCLUDED.card_sha256, validation=EXCLUDED.validation, loaded_at=now()"""
                ),
                dict(t=s.tenant_id, id=card["id"], v=card["version"], st=card["status"], title=card["title"], sev=card["severity"],
                     tier=card["check"]["tier"], ct=card["check"]["type"], eff=card["effective_from"],
                     reg=card["source"]["regulator"], card=json.dumps(card, ensure_ascii=False), sha=sha, val=json.dumps(val)),
            )
        except Exception as e:  # noqa: BLE001  (e.g. active-card immutability trigger)
            log.error("card %s not synced: %s", card.get("id"), e)
            stats["skipped_active_changed"] += 1
    audit.append(conn, actor="rules-sync", action="rules.sync", object_type="rule_cards", object_id="*", payload={**stats, "as_of": as_of.isoformat(), "cards": shas})
    return stats


def enforceability(card: dict, as_of: dt.date) -> str:
    return "live" if dt.date.fromisoformat(card["effective_from"]) <= as_of else "not_yet_enforceable"


def summarize(row, as_of: dt.date) -> dict:
    c = row.card
    return {
        "id": row.id, "version": row.version, "title": row.title, "status": row.status, "severity": row.severity, "tier": row.tier,
        "check_type": row.check_type, "effective_from": row.effective_from.isoformat(), "enforceability": enforceability(c, as_of),
        "regulator": row.regulator, "aliases": c.get("aliases", []),
        "source": {"document": c["source"].get("document"), "file": c["source"].get("file"), "provenance": c["source"].get("provenance"),
                   "text_basis": c["source"].get("text_basis"), "reference": c["source"].get("reference"), "locator": c["source"].get("locator")},
        "open_issues_count": len(c.get("open_issues", [])), "validation_ok": row.validation.get("ok"), "quotes_verified": row.validation.get("quotes_verified"),
    }


def latest_cards(conn: Connection) -> list:
    return conn.execute(
        text(
            """SELECT DISTINCT ON (id) id, version, status, title, severity, tier, check_type, effective_from, regulator, card, card_sha256, validation
               FROM rule_cards WHERE tenant_id=:t ORDER BY id, version DESC"""
        ),
        {"t": get_settings().tenant_id},
    ).all()
