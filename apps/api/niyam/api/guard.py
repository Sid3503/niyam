"""Live Guard: should this DRAFT reply be sent? Tier A only (deterministic, no network) inside a latency budget.

approve   no applicable rule failed or was uncertain
fix       at least one rule clearly failed: do not send; show the reason
escalate  nothing failed outright but a rule could not be decided: hand to a human (safe handoff)
Tier B is deliberately not in this path; it is slow and probabilistic.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from niyam.api.deps import require_key
from niyam.config import get_settings
from niyam.db import audit
from niyam.db.session import tx
from niyam.rules import loader

router = APIRouter(prefix="/guard", tags=["guard"], dependencies=[Depends(require_key)])


class GuardRequest(BaseModel):
    draft_reply: str = Field(default="")
    facts: dict = Field(default_factory=dict)
    rule_ids: list[str] | None = None
    as_of: dt.date | None = None


@router.post("/check")
def guard_check(req: GuardRequest) -> dict:
    st = get_settings()
    if len(req.draft_reply) > st.max_check_chars:
        raise HTTPException(422, detail={"code": "text_too_long", "message": f"draft exceeds {st.max_check_chars} characters"})
    try:
        from niyam import engine
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, detail={"code": "engine_unavailable", "message": str(e)})
    t0 = time.perf_counter()
    as_of = req.as_of or loader.as_of_date()
    with tx() as c:
        rows = [r for r in loader.latest_cards(c) if r.status not in ("retired", "rejected", "superseded")]
        cards = [r.card for r in rows]
        verdicts = engine.run_checks(req.draft_reply, req.facts, cards, as_of=as_of, rule_ids=req.rule_ids)
        fails = [v for v in verdicts if v["verdict"] == "fail"]
        unsure = [v for v in verdicts if v["verdict"] == "review"]
        if not req.draft_reply.strip():
            decision, why = "escalate", "empty draft: nothing to verify"
        elif fails:
            decision, why = "fix", f"{len(fails)} rule(s) clearly failed"
        elif unsure:
            decision, why = "escalate", f"{len(unsure)} rule(s) could not be decided; a human should decide"
        else:
            decision, why = "approve", "no applicable rule failed or was uncertain"
        ms = round((time.perf_counter() - t0) * 1000)
        audit.append(c, actor="api", action="guard.check", object_type="draft", object_id=hashlib.sha256(req.draft_reply.encode()).hexdigest()[:16],
                     payload={"decision": decision, "latency_ms": ms, "fails": [v["rule_id"] for v in fails], "unsure": [v["rule_id"] for v in unsure]})
    return {"decision": decision, "safe_to_send": decision == "approve", "why": why, "latency_ms": ms, "budget_ms": st.guard_budget_ms,
            "within_budget": ms <= st.guard_budget_ms, "as_of": as_of.isoformat(),
            "findings": [{"rule_id": v["rule_id"], "verdict": v["verdict"], "quote": v.get("quote"), "span": v.get("span"), "reason": v["reason"]} for v in fails + unsure],
            "checked_rules": len(verdicts), "rule_status_note": "all rule cards are draft unless a named human has approved them; this is decision support"}
