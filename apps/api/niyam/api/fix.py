from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from niyam.api.deps import require_key
from niyam.config import get_settings
from niyam.db import audit
from niyam.db.session import tx
from niyam.llm import router as llm
from niyam.rules import loader

router = APIRouter(tags=["fix"], dependencies=[Depends(require_key)])


class FixRequest(BaseModel):
    text: str = Field(min_length=1)
    rule_id: str
    quote: str | None = None
    facts: dict = Field(default_factory=dict)
    as_of: dt.date | None = None


def log_calls(conn, calls: list[dict], run_id=None) -> None:
    for c in calls:
        conn.execute(text("INSERT INTO model_calls (id, tenant_id, run_id, stage, rule_id, provider, model, prompt_version, prompt_sha256, request_id, "
                          "tokens_in, tokens_out, reasoning_tokens, latency_ms, cache_hit, error_code) VALUES (:i,:t,:r,:st,:ru,:p,:m,:pv,:ps,:rq,:ti,:to,:rt,:l,:ch,:ec)"),
                     dict(i=uuid.uuid4(), t=get_settings().tenant_id, r=run_id, st=c["stage"], ru=c.get("rule_id"), p=c["provider"], m=c["model"],
                          pv=c["prompt_version"], ps=c["prompt_sha256"], rq=c.get("request_id"), ti=c.get("tokens_in"), to=c.get("tokens_out"),
                          rt=c.get("reasoning_tokens"), l=c.get("latency_ms"), ch=c.get("cache_hit", False), ec=c.get("error_code")))


@router.post("/suggest-fix")
def suggest_fix(req: FixRequest) -> dict:
    st = get_settings()
    if len(req.text) > st.max_check_chars:
        raise HTTPException(422, detail={"code": "text_too_long", "message": f"text exceeds {st.max_check_chars} characters"})
    if not llm.configured():
        raise HTTPException(503, detail={"code": "llm_not_configured", "message": "SARVAM_API_KEY is not set; fixes cannot be drafted"})
    from niyam.judge import fixer
    as_of = req.as_of or loader.as_of_date()
    with tx() as c:
        row = next((r for r in loader.latest_cards(c) if r.id == req.rule_id), None)
        if not row:
            raise HTTPException(404, detail={"code": "not_found", "message": f"no rule card {req.rule_id}"})
        try:
            out = fixer.suggest(req.text, row.card, req.facts, req.quote, as_of)
        except llm.LLMUnavailable as e:
            raise HTTPException(503, detail={"code": e.code, "message": "the language model is unavailable; no fix drafted"})
        log_calls(c, out.pop("calls", []))
        audit.append(c, actor="api", action="fix.suggested", object_type="rule_card", object_id=req.rule_id,
                     payload={"proposed": out["proposed"], "rule_status": row.status, "note": "suggestion only; requires named human approval"})
    return {**out, "rule_id": req.rule_id, "rule_status": row.status, "notice": "A suggestion only. A named human must approve any change; nothing was applied."}
