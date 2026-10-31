from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from niyam.api.deps import require_key
from niyam.db.session import tx
from niyam.rules import loader

router = APIRouter(prefix="/rules", tags=["rules"], dependencies=[Depends(require_key)])


@router.get("")
def list_rules(as_of: dt.date | None = None) -> list[dict]:
    d = as_of or loader.as_of_date()
    with tx() as c:
        pend = {(a.rule_id, a.rule_version): str(a.id) for a in c.execute(text("SELECT id, rule_id, rule_version FROM approvals WHERE kind='rule' AND status IN ('pending','deferred')")).all()}
        out = []
        for r in loader.latest_cards(c):
            x = loader.summarize(r, d)
            x.update(approval_id=pend.get((r.id, r.version)), approved_by=r.card.get("approved_by"), approved_at=r.card.get("approved_at"),
                     scan_active=r.status == "active" and x["enforceability"] == "live")
            out.append(x)
        return out


@router.get("/{rule_id}")
def get_rule(rule_id: str, as_of: dt.date | None = None) -> dict:
    d = as_of or loader.as_of_date()
    with tx() as c:
        rows = [r for r in loader.latest_cards(c) if r.id == rule_id]
    if not rows:
        raise HTTPException(404, detail={"code": "not_found", "message": f"no rule card {rule_id}"})
    r = rows[0]
    with tx() as c:
        vers = [{"version": v.version, "status": v.status, "effective_from": v.effective_from.isoformat()} for v in c.execute(
            text("SELECT version, status, effective_from FROM rule_cards WHERE id=:i ORDER BY version DESC"), {"i": rule_id}).all()]
    return {**r.card, "status": r.status, "versions": vers, "enforceability": loader.enforceability(r.card, d), "card_sha256": r.card_sha256,
            "validation": {k: r.validation.get(k) for k in ("ok", "errors", "warnings", "quotes_verified", "validated_at")}}
