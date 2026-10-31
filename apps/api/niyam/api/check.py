from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from niyam.api.deps import require_key
from niyam.config import get_settings
from niyam.db import audit
from niyam.db.session import tx
from niyam.rules import loader

router = APIRouter(tags=["check"], dependencies=[Depends(require_key)])


class CheckRequest(BaseModel):
    text: str = Field(default="")
    facts: dict = Field(default_factory=dict)
    rule_ids: list[str] | None = None
    as_of: dt.date | None = None
    llm: str = Field(default="auto", pattern="^(auto|off)$")   # auto: use Tier B (Sarvam) when configured; off: Tier A only


def _engine():
    try:
        from niyam import engine
        return engine
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, detail={"code": "engine_unavailable", "message": f"check engine not available: {e}"})


def _summary(verdicts: list[dict]) -> dict:
    s = {k: 0 for k in ("pass", "fail", "review", "not_applicable", "not_yet_enforceable")}
    for v in verdicts:
        s[v["verdict"]] = s.get(v["verdict"], 0) + 1
    return s


@router.post("/check")
def run_check(req: CheckRequest) -> dict:
    st = get_settings()
    if len(req.text) > st.max_check_chars:
        raise HTTPException(422, detail={"code": "text_too_long", "message": f"text exceeds {st.max_check_chars} characters"})
    eng = _engine()
    as_of = req.as_of or loader.as_of_date()
    t0 = time.perf_counter()
    with tx() as c:
        rows = loader.latest_cards(c)
        usable = [r for r in rows if r.status not in ("retired", "rejected", "superseded")]
        if req.rule_ids:
            unknown = set(req.rule_ids) - {r.id for r in usable}
            if unknown:
                raise HTTPException(422, detail={"code": "unknown_rule", "message": f"unknown rule ids: {sorted(unknown)}"})
        cards = [r.card for r in usable]
        by_id = {r.id: r for r in usable}
        verdicts = eng.run_checks(req.text, req.facts, cards, as_of=as_of, rule_ids=req.rule_ids)
        for v in verdicts:                                   # enrich for the console (rule title, provenance)
            r = by_id.get(v["rule_id"])
            if r:
                v["rule_title"] = r.title
                v.setdefault("source", {})
                v["source"].setdefault("provenance", r.card["source"].get("provenance"))
                v["source"].setdefault("text_basis", r.card["source"].get("text_basis"))
        from niyam.judge import tier_b
        llm_on = req.llm == "auto"
        verdicts, calls = tier_b.apply(verdicts, {r.id: r.card for r in usable}, req.text, req.facts, enabled=llm_on)
        duration = round((time.perf_counter() - t0) * 1000)
        run_id, summary = uuid.uuid4(), _summary(verdicts)
        snapshot = {r.id: {"version": r.version, "sha256": r.card_sha256, "status": r.status} for r in usable if not req.rule_ids or r.id in req.rule_ids}
        c.execute(
            text("INSERT INTO check_runs (id, tenant_id, as_of, text_sha256, text, facts, rule_filter, summary, engine_version, cards_snapshot, duration_ms) "
                 "VALUES (:i,:t,:a,:h,:tx,CAST(:f AS jsonb),CAST(:rf AS jsonb),CAST(:s AS jsonb),:ev,CAST(:cs AS jsonb),:d)"),
            dict(i=run_id, t=st.tenant_id, a=as_of, h=hashlib.sha256(req.text.encode()).hexdigest(), tx=req.text if st.store_check_text else None,
                 f=json.dumps(req.facts), rf=json.dumps(req.rule_ids), s=json.dumps(summary), ev=str(getattr(eng, "__version__", "0")),
                 cs=json.dumps(snapshot), d=duration),
        )
        for v in verdicts:
            span = v.get("span")
            c.execute(
                text("INSERT INTO verdicts (id, tenant_id, run_id, rule_id, rule_version, rule_status, verdict, tier, confidence, quote, span_start, span_end, reason, checks, source) "
                     "VALUES (:i,:t,:r,:ri,:rv,:rs,:vd,:tier,:cf,:q,:s0,:s1,:rsn,CAST(:ck AS jsonb),CAST(:src AS jsonb))"),
                dict(i=uuid.uuid4(), t=st.tenant_id, r=run_id, ri=v["rule_id"], rv=v["rule_version"], rs=v.get("rule_status", "draft"), vd=v["verdict"],
                     tier=str(v.get("tier", "A")), cf=float(v.get("confidence", 0.0)), q=v.get("quote"), s0=span[0] if span else None,
                     s1=span[1] if span else None, rsn=v.get("reason", ""), ck=json.dumps(v.get("checks", [])), src=json.dumps(v.get("source", {}))),
            )
        from niyam.api.fix import log_calls
        log_calls(c, calls, run_id)
        audit.append(c, actor="api", action="check.run", object_type="check_run", object_id=str(run_id),
                     payload={"summary": summary, "text_sha256": hashlib.sha256(req.text.encode()).hexdigest(), "as_of": as_of.isoformat(), "rules": len(snapshot)})
    return {"run_id": str(run_id), "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "as_of": as_of.isoformat(),
            "summary": summary, "verdicts": verdicts, "duration_ms": duration,
            "llm": {"enabled": llm_on, "configured": __import__("niyam.llm.router", fromlist=["x"]).configured(), "calls": len(calls),
                    "cache_hits": sum(1 for x in calls if x.get("cache_hit")), "errors": sum(1 for x in calls if x.get("error_code"))}}


@router.get("/runs")
def list_runs(limit: int = 50) -> list[dict]:
    limit = max(1, min(limit, 200))
    with tx() as c:
        rows = c.execute(text("SELECT id, created_at, as_of, summary, left(coalesce(text,''), 140) AS preview, duration_ms FROM check_runs "
                              "WHERE tenant_id=:t ORDER BY created_at DESC LIMIT :l"), {"t": get_settings().tenant_id, "l": limit}).all()
    return [{"run_id": str(r.id), "created_at": r.created_at.isoformat(), "as_of": r.as_of.isoformat(), "summary": r.summary,
             "text_preview": r.preview, "duration_ms": r.duration_ms} for r in rows]


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    try:
        rid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(404, detail={"code": "not_found", "message": "run not found"})
    with tx() as c:
        r = c.execute(text("SELECT * FROM check_runs WHERE id=:i AND tenant_id=:t"), {"i": rid, "t": get_settings().tenant_id}).first()
        if not r:
            raise HTTPException(404, detail={"code": "not_found", "message": "run not found"})
        vs = c.execute(text("SELECT v.*, rc.title FROM verdicts v LEFT JOIN LATERAL (SELECT title FROM rule_cards WHERE tenant_id=v.tenant_id AND id=v.rule_id "
                            "AND version=v.rule_version) rc ON true WHERE v.run_id=:i ORDER BY v.created_at"), {"i": rid}).all()
    verdicts = [{"rule_id": v.rule_id, "rule_version": v.rule_version, "rule_status": v.rule_status, "rule_title": v.title, "verdict": v.verdict,
                 "tier": v.tier, "confidence": v.confidence, "quote": v.quote, "span": [v.span_start, v.span_end] if v.span_start is not None else None,
                 "reason": v.reason, "checks": v.checks, "source": v.source, "human_decision": v.human_decision} for v in vs]
    return {"run_id": str(r.id), "created_at": r.created_at.isoformat(), "as_of": r.as_of.isoformat(), "summary": r.summary, "text": r.text,
            "facts": r.facts, "verdicts": verdicts, "duration_ms": r.duration_ms, "cards_snapshot": r.cards_snapshot}


@router.get("/runs/{run_id}/evidence")
def run_evidence(run_id: str) -> dict:
    """A reproducible bundle for internal audit: verdicts, the exact rule cards and source-file hashes used, and the audit chain state.
    Hash-only (no signing key configured). Supports internal audit; it does NOT prove regulatory compliance."""
    run = get_run(run_id)
    st = get_settings()
    with tx() as c:
        register = []
        for rid, meta in (run.get("cards_snapshot") or {}).items():
            row = c.execute(text("SELECT card, card_sha256, validation FROM rule_cards WHERE tenant_id=:t AND id=:i AND version=:v"),
                            {"t": st.tenant_id, "i": rid, "v": meta["version"]}).first()
            if not row:
                continue
            src = row.card["source"]
            doc = c.execute(text("SELECT sha256, title, provenance, text_basis, status FROM documents WHERE tenant_id=:t AND file_path=:p LIMIT 1"),
                            {"t": st.tenant_id, "p": src["file"]}).first()
            register.append({"rule_id": rid, "version": meta["version"], "status": row.card["status"], "approved_by": row.card.get("approved_by"),
                             "card_sha256": row.card_sha256, "obligation": row.card["obligation"], "regulator_quotes": src["quotes"],
                             "source_file": src["file"], "source_sha256_in_card": src.get("sha256"), "source_sha256_in_kb": doc.sha256 if doc else None,
                             "source_matches_kb": bool(doc and doc.sha256 == src.get("sha256")), "provenance": src.get("provenance"),
                             "text_basis": src.get("text_basis"), "quotes_verified": row.validation.get("quotes_verified")})
        calls = c.execute(text("SELECT stage, rule_id, provider, model, prompt_version, prompt_sha256, tokens_in, tokens_out, latency_ms, cache_hit, error_code FROM model_calls WHERE run_id=:r"),
                          {"r": uuid.UUID(run_id)}).mappings().all()
        chain = audit.verify_chain(c)
    pack = {"pack_version": 1, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "run": {k: run[k] for k in ("run_id", "created_at", "as_of", "summary", "text", "facts", "duration_ms")},
            "verdicts": run["verdicts"], "rule_register": register, "model_calls": [dict(x) for x in calls], "audit_chain": chain,
            "signature": None, "signature_note": "hash only; no signing key is configured",
            "disclaimer": "Supports internal audit. It does not prove regulatory compliance. Rule cards marked draft have not been approved by a named human."}
    pack["pack_sha256"] = hashlib.sha256(json.dumps(pack, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()).hexdigest()
    return pack
