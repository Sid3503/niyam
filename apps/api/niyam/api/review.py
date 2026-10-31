from __future__ import annotations

import datetime as dt
import json
import uuid

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from niyam.api.deps import require_key
from niyam.config import get_settings
from niyam.db import audit
from niyam.db.session import tx
from niyam.review import blobs, circulars, claims, pdfio, pipeline, service, voice, workbench
from niyam.review.segment import parse_front_matter
from niyam.rules import loader

router = APIRouter(tags=["review"], dependencies=[Depends(require_key)])
DEFAULT_ACTOR = "compliance.reviewer"


def actor_of(x_actor: str | None) -> str:
    a = (x_actor or DEFAULT_ACTOR).strip()
    return a[:80] if a else DEFAULT_ACTOR


def _404(msg="not found"):
    return HTTPException(404, detail={"code": "not_found", "message": msg})


def _uuid(s: str) -> uuid.UUID:
    try:
        return uuid.UUID(s)
    except ValueError:
        raise _404()


# ---------------------------------------------------------------- overview
@router.get("/overview")
def overview() -> dict:
    t = get_settings().tenant_id
    with tx() as c:
        service.ensure_rule_approvals(c)
        docs = service.list_library(c)
        row = c.execute(text(service._LATEST + f"""SELECT count(*) FILTER (WHERE {service._open_clause()}) AS open_n, count(*) AS total_n,
            count(*) FILTER (WHERE (f.rule_id IS NOT NULL OR f.fact_id IS NOT NULL) AND coalesce(f.source->>'quote', f.source->>'statement', '') <> '') AS cited
            FROM lv JOIN lr ON lr.version_id=lv.id JOIN findings f ON f.review_id=lr.id"""), {"t": t}).one()
        fixes = c.execute(text("SELECT count(*) FROM approvals WHERE tenant_id=:t AND kind='fix' AND status='pending'"), {"t": t}).scalar()
        rules_p = c.execute(text("SELECT count(*) FROM approvals WHERE tenant_id=:t AND kind='rule' AND status IN ('pending','deferred')"), {"t": t}).scalar()
        rc = c.execute(text("SELECT status, count(*) n FROM (SELECT DISTINCT ON (id) id, status FROM rule_cards WHERE tenant_id=:t ORDER BY id, version DESC) x GROUP BY status"), {"t": t}).all()
        rcm = {r.status: r.n for r in rc}
    scanned = sum(1 for d in docs if d["last_reviewed_at"])
    unscanned = sum(1 for d in docs if d["status"] in ("new", "changed"))
    if rules_p and not rcm.get("active"):
        nxt = {"label": f"Review {rules_p} draft rule(s)", "route": "/approvals", "kind": "approve_rules"}
    elif unscanned:
        nxt = {"label": "Scan now", "route": "/library", "kind": "scan"}
    elif fixes:
        nxt = {"label": f"Review {fixes} approval(s)", "route": "/approvals", "kind": "approve_fixes"}
    elif rules_p:
        nxt = {"label": f"Review {rules_p} draft rule(s)", "route": "/approvals", "kind": "approve_rules"}
    else:
        nxt = {"label": "Add a circular", "route": "/rules", "kind": "add_circular"}
    steps, pack = _loop(t, docs, row.open_n, rcm.get("active", 0), rules_p, fixes)
    cur = next(x for x in steps if x["state"] == "current")
    cta = {"circular": ("Add a circular", "add_circular"), "rules": (f"Review {rules_p} draft rule(s)" if rules_p else "Approve a rule", "approve_rules"),
           "scan": ("Scan library", "scan"), "fixes": (f"Review {fixes} approval(s)" if fixes else "Open a flagged document and send a fix", "approve_fixes"),
           "retest": ("Re-test a corrected document", "retest"), "evidence": ("Export the evidence pack", "evidence")}[cur["key"]]
    nxt = {"label": cta[0], "route": cur["route"], "kind": cta[1]}
    return {"documents_scanned": scanned, "documents_total": len(docs), "open_findings": row.open_n, "fixes_awaiting_approval": fixes,
            "rules_pending_approval": rules_p, "citation_coverage": round(row.cited / row.total_n, 3) if row.total_n else 1.0,
            "rules": {"active": rcm.get("active", 0), "draft": rcm.get("draft", 0) + rcm.get("in_review", 0)}, "next_action": nxt,
            "steps": steps, "pack": pack}


def _loop(t: str, docs: list[dict], open_n: int, active_rules: int, rules_p: int, fixes_pending: int) -> tuple[list[dict], dict]:
    """The six-step loop the Overview draws, and the circular-to-pack clock."""
    with tx() as c:
        circ = c.execute(text("SELECT title, retrieved_at FROM circular_sources WHERE tenant_id=:t ORDER BY retrieved_at DESC LIMIT 1"), {"t": t}).first()
        fixes_ok = c.execute(text("SELECT count(*), max(decided_at) FROM approvals WHERE tenant_id=:t AND kind='fix' AND status='approved'"), {"t": t}).first()
        rt = c.execute(text("SELECT count(*) FILTER (WHERE passed), max(ts) FILTER (WHERE passed) FROM retests r JOIN sales_documents d ON d.id=r.document_id WHERE d.tenant_id=:t"), {"t": t}).first()
    scanned = [d for d in docs if d["last_reviewed_at"]]
    affected = [d for d in scanned if d["open_findings"] > 0]
    done = [bool(circ) or active_rules > 0, active_rules > 0, bool(scanned), fixes_ok[0] > 0, rt[0] > 0, rt[0] > 0]
    spec = [("circular", "Circular added", "/rules", (f"{circ.title}" if circ else ("Using the seeded rule set; no new circular added yet" if active_rules else "Add the RBI or NPCI circular that just landed"))),
            ("rules", "Rule approved", "/approvals", f"{active_rules} active rule(s)" + (f", {rules_p} waiting for approval" if rules_p else "")),
            ("scan", "Library scanned", "/library", f"{len(scanned)} of {len(docs)} documents reviewed, {open_n} open finding(s)"),
            ("fixes", "Fixes approved", "/approvals", f"{fixes_ok[0]} approved, {fixes_pending} waiting for approval"),
            ("retest", "Re-tested", "/library", f"{rt[0]} passing re-test(s)"),
            ("evidence", "Evidence filed", "/evidence", "Export the pack for audit" if rt[0] else "Available once a document passes re-test")]
    cur = next((i for i, d in enumerate(done) if not d), len(spec) - 1)
    steps = [{"key": k, "label": lab, "state": "done" if done[i] else ("current" if i == cur else "todo"), "detail": det, "route": rte} for i, (k, lab, rte, det) in enumerate(spec)]
    now = dt.datetime.now(dt.timezone.utc)
    approved_at = None
    if circ and fixes_ok[0] > 0 and open_n == 0 and scanned:
        approved_at = max(x for x in (fixes_ok[1], rt[1]) if x)
    started = circ.retrieved_at if circ else None
    elapsed = None if not started else max(0, int(((approved_at or now) - started).total_seconds()))
    pack = {"circular_title": circ.title if circ else None, "started_at": started.isoformat(timespec="seconds") if started else None,
            "approved_at": approved_at.isoformat(timespec="seconds") if approved_at else None, "elapsed_seconds": elapsed, "documents_total": len(docs),
            "documents_affected": len(affected), "documents_clear": len(scanned) - len(affected)}
    return steps, pack


# ---------------------------------------------------------------- library
@router.get("/library")
def library() -> list[dict]:
    with tx() as c:
        return service.list_library(c)


class ScanReq(BaseModel):
    llm: bool = False


@router.post("/library/scan")
def library_scan(req: ScanReq | None = None, x_actor: str | None = Header(default=None)) -> dict:
    with tx() as c:
        service.ensure_rule_approvals(c)
        return service.scan(c, actor=actor_of(x_actor), llm=bool(req and req.llm))


@router.get("/library/scans")
def library_scans(limit: int = 20) -> list[dict]:
    with tx() as c:
        rows = c.execute(text("SELECT * FROM scans WHERE tenant_id=:t ORDER BY started_at DESC LIMIT :l"), {"t": get_settings().tenant_id, "l": max(1, min(limit, 100))}).all()
    return [{"scan_id": str(r.id), "trigger": r.trigger, "started_at": r.started_at.isoformat(timespec="seconds"), "discovered": r.discovered, "reviewed": r.reviewed, "skipped": r.skipped} for r in rows]


class UploadReq(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    doc_type: str = Field(pattern="^(proposal|agreement|order_form|brochure|pitch_deck|onboarding)$")
    product: str = "Payment Gateway"
    owner: str = "unassigned"
    merchant: str | None = None
    content: str = Field(min_length=10, max_length=200_000)


@router.post("/library/upload")
def library_upload(req: UploadReq, x_actor: str | None = Header(default=None)) -> dict:
    actor = actor_of(x_actor)
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in req.title).strip("-")[:60] or "document"
    path = f"upload/{slug}.md"
    _, body = parse_front_matter(req.content)
    with tx() as c:
        did = service._upsert_document(c, path, {"title": req.title, "doc_type": req.doc_type, "product": req.product, "owner": req.owner, "merchant": req.merchant or "", "channel": "upload"})
        vid, _, _ = service._add_version(c, did, body, "upload", None, actor)
        pipeline.review_version(c, vid, "upload", actor=actor)
        return service.document_detail(c, did)


# ---------------------------------------------------------------- documents and findings
@router.get("/documents/{doc_id}")
def get_document(doc_id: str, version_id: str | None = None) -> dict:
    with tx() as c:
        d = service.document_detail(c, _uuid(doc_id), _uuid(version_id) if version_id else None)
    if not d:
        raise _404("document not found (run Scan now to ingest new library files)")
    return d


class RetestReq(BaseModel):
    content: str | None = Field(default=None, max_length=200_000)
    llm: bool = False


@router.post("/documents/{doc_id}/retest")
def retest(doc_id: str, req: RetestReq | None = None, x_actor: str | None = Header(default=None)) -> dict:
    req = req or RetestReq()
    did = _uuid(doc_id)
    with tx() as c:
        try:
            r = service.retest(c, did, req.content, actor_of(x_actor), llm=req.llm)
        except ValueError:
            raise HTTPException(422, detail={"code": "not_text_document", "message": "this document is a PDF or voice note; pasted text cannot replace it. Use the PDF workbench to apply wording, or upload a new file."})
        if r is None:
            raise _404("document not found")
        detail = service.document_detail(c, did, r.pop("version_id"))
    return {"document": detail, **r}


class SuggestReq(BaseModel):
    pass


def _ensure_fix(c, fid: uuid.UUID, actor: str) -> None:
    f = c.execute(text("SELECT f.*, v.content FROM findings f JOIN document_versions v ON v.id=f.version_id WHERE f.id=:i"), {"i": fid}).first()
    if not f:
        raise _404("finding not found")
    if f.suggested_fix or not f.rule_id or not f.quote:
        return
    from niyam.judge import fixer
    from niyam.llm import router as llm
    if not llm.configured():
        return
    card = c.execute(text("SELECT card FROM rule_cards WHERE tenant_id=:t AND id=:i AND version=:v"), {"t": get_settings().tenant_id, "i": f.rule_id, "v": f.rule_version}).scalar()
    try:
        out = fixer.suggest(f.quote, card, pipeline._clause_facts(f.quote), f.quote, loader.as_of_date())
    except llm.LLMUnavailable as e:
        raise HTTPException(503, detail={"code": e.code, "message": f"the language model could not draft wording ({e.code}); try again or write the wording by hand"})
    from niyam.api.fix import log_calls
    log_calls(c, out.pop("calls", []))
    if out.get("proposed"):
        fx = {"wording": out["suggestion"], "rationale": out["rationale"], "validated": True, "source": "llm+tier_a_recheck"}
        c.execute(text("UPDATE findings SET suggested_fix=CAST(:x AS jsonb) WHERE id=:i"), {"x": json.dumps(fx), "i": fid})
        audit.append(c, actor=actor, action="fix.drafted", object_type="finding", object_id=str(fid), payload={"rule_id": f.rule_id, "validated": True})


@router.post("/findings/{finding_id}/suggest-fix")
def suggest_fix_for_finding(finding_id: str, x_actor: str | None = Header(default=None)) -> dict:
    fid = _uuid(finding_id)
    with tx() as c:
        _ensure_fix(c, fid, actor_of(x_actor))
        r = c.execute(text(service._FIND_SQL + " WHERE f.id=:i"), {"i": fid}).first()
        if not r:
            raise _404("finding not found")
        return service.finding_json(r)


@router.post("/findings/{finding_id}/send-for-approval")
def send_for_approval(finding_id: str, x_actor: str | None = Header(default=None)) -> dict:
    fid = _uuid(finding_id)
    actor = actor_of(x_actor)
    with tx() as c:
        _ensure_fix(c, fid, actor)
        try:
            a = service.create_fix_approval(c, fid, actor)
        except ValueError:
            raise HTTPException(409, detail={"code": "no_suggested_fix", "message": "this finding has no drafted wording yet (the AI model is not configured or could not produce a compliant fix); a reviewer must write one"})
    if a is None:
        raise _404("finding not found")
    return a


# ---------------------------------------------------------------- rules (extra), product facts
@router.get("/product-facts")
def product_facts() -> list[dict]:
    F = claims.load_facts()
    out = [{"id": f["id"], "category": f["category"], "title": f["title"], "statement": f["statement"], "value": f["value"], "unit": f["unit"], "owner": F["owner"],
            "approved_wording": f["approved_wording"], "superseded": f.get("superseded"), "source_label": F["label"]} for f in F["facts"]]
    out += [{"id": d["id"], "category": "required_disclosure", "title": d["title"], "statement": f"Required in: {', '.join(d['applies_to'])}", "value": {"patterns": d["patterns"]},
             "unit": None, "owner": F["owner"], "approved_wording": d["approved_wording"], "superseded": None, "source_label": F["label"]} for d in F["required_disclosures"]]
    return out


# ---------------------------------------------------------------- circulars
class CircularReq(BaseModel):
    url: str | None = None
    text: str | None = Field(default=None, max_length=400_000)
    kb_document_id: str | None = None
    kb_query: str | None = None
    title: str | None = None
    institution: str = Field(min_length=2, max_length=80)
    product_area: str | None = None
    effective_date: dt.date | None = None


@router.post("/circulars")
def add_circular(req: CircularReq, x_actor: str | None = Header(default=None)) -> dict:
    if not (req.url or req.text or req.kb_document_id):
        raise HTTPException(422, detail={"code": "no_source", "message": "provide a url, pasted text or a knowledge-base document"})
    if req.url and not req.url.lower().startswith(("http://", "https://")):
        raise HTTPException(422, detail={"code": "bad_url", "message": "url must be http(s)"})
    try:
        with tx() as c:
            return circulars.intake(c, url=req.url if not (req.text or req.kb_document_id) else None, body=req.text, title=req.title, institution=req.institution,
                                    product_area=req.product_area, effective_date=req.effective_date, kb_document_id=req.kb_document_id,
                                    kb_query=req.kb_query, actor=actor_of(x_actor))
    except ValueError as e:
        raise HTTPException(422, detail={"code": str(e), "message": "the source is missing or too short to draft rules from"})
    except circulars.KbNotFound:
        raise _404("knowledge-base document not found")
    except Exception as e:  # noqa: BLE001  (network / parse failures from fetching a URL)
        if e.__class__.__module__.startswith("httpx"):
            raise HTTPException(502, detail={"code": "fetch_failed", "message": f"could not fetch the URL ({e.__class__.__name__}); paste the text or pick a knowledge-base document instead"})
        raise


# ---------------------------------------------------------------- approvals
@router.get("/approvals")
def approvals(status: str | None = None, kind: str | None = None) -> list[dict]:
    with tx() as c:
        service.ensure_rule_approvals(c)
        q = "SELECT * FROM approvals WHERE tenant_id=:t"
        p: dict = {"t": get_settings().tenant_id}
        if status:
            q += " AND status=:s"
            p["s"] = status
        if kind:
            q += " AND kind=:k"
            p["k"] = kind
        rows = c.execute(text(q), p).all()
    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    rows.sort(key=lambda r: ((r.status not in ("pending", "deferred")), rank[r.severity], r.confidence if r.confidence is not None else 1.0, r.created_at))
    return [service.approval_json(r) for r in rows]


class DecisionReq(BaseModel):
    decision: str = Field(pattern="^(approve|reject|defer)$")
    reason: str | None = Field(default=None, max_length=1000)


@router.post("/approvals/{approval_id}/decision")
def decide(approval_id: str, req: DecisionReq, x_actor: str | None = Header(default=None)) -> dict:
    with tx() as c:
        try:
            a = service.decide(c, _uuid(approval_id), req.decision, req.reason, actor_of(x_actor))
        except ValueError:
            raise HTTPException(409, detail={"code": "already_decided", "message": "this item was already approved or rejected"})
    if a is None:
        raise _404("approval not found")
    return a


# ---------------------------------------------------------------- impact
@router.get("/impact")
def impact_list() -> list[dict]:
    with tx() as c:
        return service.impact_rules(c)


@router.get("/impact/{rule_id}")
def impact_for(rule_id: str, version: int | None = None, suggest: bool = False) -> dict:
    with tx() as c:
        r = service.impact(c, rule_id, version, suggest=suggest)
    if r is None:
        raise _404("rule not found")
    return r


# ---------------------------------------------------------------- evidence
def evidence_record(c, did: uuid.UUID) -> dict | None:
    d = service.document_detail(c, did)
    if not d:
        return None
    t = get_settings().tenant_id
    ev = c.execute(text("""SELECT seq, ts, actor, action, payload FROM audit_events WHERE tenant_id=:t AND (object_id=:d OR payload->>'document_id'=:d)
                           ORDER BY seq"""), {"t": t, "d": str(did)}).all()
    summ = {"document.version": "New document version stored", "document.reviewed": "Document reviewed against active rules and product facts",
            "document.retested": "Edited version re-tested", "document.workbench_commit": "Wording applied to a copy of the PDF and committed as a new version", "voice.checked": "Voice note transcribed and checked", "approval.approved": "Reviewer approved", "approval.rejected": "Reviewer rejected",
            "approval.deferred": "Reviewer deferred", "fix.sent_for_approval": "Suggested fix sent for approval", "fix.drafted": "Replacement wording drafted"}
    events = [{"seq": e.seq, "ts": e.ts.isoformat(timespec="seconds"), "actor": e.actor, "action": e.action, "summary": summ.get(e.action, e.action), "payload": e.payload} for e in ev]
    first = c.execute(text("SELECT * FROM document_versions WHERE document_id=:d ORDER BY version LIMIT 1"), {"d": did}).one()
    appr = c.execute(text("SELECT * FROM approvals WHERE tenant_id=:t AND document_id=:d ORDER BY created_at"), {"t": t, "d": did}).all()
    rt = c.execute(text("SELECT * FROM retests WHERE document_id=:d ORDER BY ts"), {"d": did}).all()
    nt = c.execute(text("SELECT * FROM notifications WHERE document_id=:d ORDER BY ts"), {"d": did}).all()
    chain = audit.verify_chain(c)
    cur = c.execute(text("SELECT version, sha256 FROM document_versions WHERE document_id=:d ORDER BY version DESC LIMIT 1"), {"d": did}).one()
    return {"document": d["document"], "format": d["document"]["format"], "hashes": {"original": {"version": first.version, "sha256": first.sha256}, "current": {"version": cur.version, "sha256": cur.sha256}},
            "original": {"version": first.version, "sha256": first.sha256, "content_preview": first.content[:600]},
            "events": events, "findings": d["findings"], "approvals": [service.approval_json(a) for a in appr],
            "retests": [{"ts": r.ts.isoformat(timespec="seconds"), "passed": r.passed, "before": r.before, "after": r.after, "actor": r.actor} for r in rt],
            "notifications": [{"ts": n.ts.isoformat(timespec="seconds"), "to": n.recipient, "channel": n.channel, "subject": n.subject} for n in nt],
            "versions": d["versions"], "chain_ok": chain["ok"]}


@router.get("/evidence")
def evidence_list() -> list[dict]:
    t = get_settings().tenant_id
    with tx() as c:
        out = []
        for d in service.list_library(c):
            if not d["last_reviewed_at"]:
                continue
            did = uuid.UUID(d["id"])
            n = c.execute(text("SELECT (SELECT count(*) FROM document_versions WHERE document_id=:d), (SELECT count(*) FROM approvals WHERE document_id=:d), "
                               "(SELECT passed FROM retests WHERE document_id=:d ORDER BY ts DESC LIMIT 1), "
                               "(SELECT max(ts) FROM audit_events WHERE tenant_id=:t AND (object_id=:ds OR payload->>'document_id'=:ds))"),
                          {"d": did, "t": t, "ds": d["id"]}).one()
            out.append({"document_id": d["id"], "title": d["title"], "versions": n[0], "findings": sum(d["by_status"].values()), "open_findings": d["open_findings"],
                        "approvals": n[1], "last_event_at": n[3].isoformat(timespec="seconds") if n[3] else None,
                        "retest": "none" if n[2] is None else ("passed" if n[2] else "failed")})
    return out


@router.get("/evidence/{doc_id}")
def evidence_get(doc_id: str) -> dict:
    with tx() as c:
        r = evidence_record(c, _uuid(doc_id))
    if not r:
        raise _404("document not found")
    return r


@router.get("/evidence/{doc_id}/export", response_class=PlainTextResponse)
def evidence_export(doc_id: str) -> PlainTextResponse:
    with tx() as c:
        r = evidence_record(c, _uuid(doc_id))
    if not r:
        raise _404("document not found")
    d = r["document"]
    L = [f"# Evidence record: {d['title']}", "",
         "_Decision support, not legal advice. Synthetic demo document; Paytm product facts are Paytm-controlled demo data._", "",
         f"- Document: {d['title']} ({d['doc_type']}, product {d['product']}), owner {d['owner']}",
         f"- Original version: v{r['hashes']['original']['version']}, SHA-256 `{r['hashes']['original']['sha256']}`",
         f"- Current version: v{r['hashes']['current']['version']}, SHA-256 `{r['hashes']['current']['sha256']}`",
         f"- Current version: v{d['version']}; audit chain intact: **{'yes' if r['chain_ok'] else 'NO'}**", "", "## Findings (latest review)", ""]
    for f in r["findings"]:
        src = f["rule_id"] and f"{f['rule_id']} v{f['rule_version']} ({f['rule_status']})" or f"{f['fact_id']} (Paytm-controlled demo data)"
        L.append(f"- **{f['status']}** / {f['severity']} at {f['locator']} (confidence {f['confidence']:.2f}, source {src})")
        if f["quote"]:
            L.append(f"  - Quote: \"{f['quote']}\"")
        L.append(f"  - Why: {f['reason']}")
        if f["suggested_fix"]:
            L.append(f"  - Suggested wording: \"{f['suggested_fix']['wording']}\"")
        L.append(f"  - Decision: {f['decision'] or 'none yet'}")
    L += ["", "## Approvals", ""]
    L += [f"- {a['kind']} **{a['status']}** by {a['decided_by'] or 'nobody yet'} at {a['decided_at'] or '-'} (severity {a['severity']}): {a['title']}"
          + (f" - reason: {a['reason']}" if a["reason"] else "") for a in r["approvals"]] or ["- none"]
    L += ["", "## Re-tests", ""]
    L += [f"- {x['ts']}: {'PASSED' if x['passed'] else 'not passed'} (open findings {x['before']['open']} -> {x['after']['open']}) by {x['actor']}" for x in r["retests"]] or ["- none"]
    L += ["", "## Notifications", ""] + ([f"- {n['ts']} to {n['to']}: {n['subject']}" for n in r["notifications"]] or ["- none"])
    L += ["", "## Timeline", ""] + [f"- #{e['seq']} {e['ts']} {e['actor']}: {e['summary']}" for e in r["events"]]
    return PlainTextResponse("\n".join(L) + "\n", media_type="text/markdown; charset=utf-8",
                             headers={"content-disposition": f"attachment; filename=evidence-{doc_id[:8]}.md"})


@router.get("/audit/verify")
def audit_verify() -> dict:
    with tx() as c:
        r = audit.verify_chain(c)
    return {"ok": r["ok"], "events": r["events"], "head_hash": r.get("head")}


# ---------------------------------------------------------------- file -> text (for the upload boxes)
MAX_UPLOAD = 15 * 1024 * 1024


def _docx_text(data: bytes) -> str:
    import io, re, zipfile
    from xml.etree import ElementTree as ET
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    paras = ["".join(t.text or "" for t in p.iter(ns + "t")) for p in root.iter(ns + "p")]
    return re.sub(r"\n{3,}", "\n\n", "\n\n".join(x for x in paras if x.strip()))


@router.post("/extract-text")
async def extract_text(file: UploadFile = File(...)) -> dict:
    """Read a PDF, DOCX, TXT or MD file and return its text so the console can show and edit it before submitting. Nothing is stored."""
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, detail={"code": "file_too_large", "message": "file is larger than 15 MB"})
    name = (file.filename or "upload").lower()
    pages = None
    try:
        if name.endswith(".pdf") or data[:5] == b"%PDF-":
            import fitz
            doc = fitz.open(stream=data, filetype="pdf")
            pages = doc.page_count
            txt = "\n\n".join(p.get_text() for p in doc)
        elif name.endswith(".docx"):
            txt = _docx_text(data)
        elif name.endswith((".txt", ".md", ".markdown")):
            txt = data.decode("utf-8", errors="replace")
        else:
            raise HTTPException(415, detail={"code": "unsupported_type", "message": "supported files: PDF, DOCX, TXT, MD (old .doc is not supported; save as DOCX)"})
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, detail={"code": "unreadable_file", "message": f"could not read this file ({e.__class__.__name__})"})
    txt = txt.strip()
    if len(txt) < 20:
        raise HTTPException(422, detail={"code": "no_text", "message": "no readable text found; a scanned PDF needs OCR first"})
    return {"filename": file.filename, "chars": len(txt), "pages": pages, "text": txt[:400_000], "truncated": len(txt) > 400_000}


# ---------------------------------------------------------------- uploads: PDF and voice
MAX_FILE = 25 * 1024 * 1024


@router.post("/library/upload-file")
async def upload_file(file: UploadFile = File(...), doc_type: str = Form("proposal"), product: str = Form("Payment Gateway"), owner: str = Form("unassigned"),
                      merchant: str | None = Form(None), title: str | None = Form(None), x_actor: str | None = Header(default=None)) -> dict:
    actor = actor_of(x_actor)
    data = await file.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise HTTPException(413, detail={"code": "file_too_large", "message": "file is larger than 25 MB"})
    name = file.filename or "upload"
    ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
    if doc_type not in ("proposal", "agreement", "order_form", "brochure", "pitch_deck", "onboarding", "voice_note"):
        raise HTTPException(422, detail={"code": "bad_doc_type", "message": "unknown document type"})
    if ext == "pdf" or data[:5] == b"%PDF-":
        try:
            ex = pdfio.extract(data)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(422, detail={"code": "unreadable_file", "message": f"could not read this PDF ({e.__class__.__name__}); it may be encrypted or damaged"})
        if len(ex.content.strip()) < 20:
            raise HTTPException(422, detail={"code": "no_text", "message": "this PDF has no text layer (a scan). OCR is not built yet, so it cannot be reviewed"})
        slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in (title or name.rsplit('.', 1)[0])).strip("-")[:60] or "document"
        with tx() as c:
            did = service._upsert_document(c, f"upload/{slug}.pdf", {"title": title or name.rsplit(".", 1)[0], "doc_type": doc_type if doc_type != "voice_note" else "proposal",
                                                                  "product": product, "owner": owner, "merchant": merchant or "", "channel": "upload"}, "pdf")
            vid, _, _ = service.add_pdf_version(c, did, data, "upload", actor, None, ex)
            pipeline.review_version(c, vid, "upload", actor=actor)
            return service.document_detail(c, did)
    if "." + ext in voice.AUDIO_TYPES:
        from niyam.llm.sarvam import LLMUnavailable
        try:
            with tx() as c:
                did = voice.check_clip(c, data, name, title=title, owner=owner, product=product, merchant=merchant, actor=actor)
                return service.document_detail(c, did)
        except LLMUnavailable as e:
            raise HTTPException(503 if e.code != "speech_bad_audio" else 422, detail={"code": e.code, "message": f"speech-to-text failed: {e}"})
        except ValueError as e:
            raise HTTPException(422, detail={"code": str(e), "message": "no speech could be recognised in this audio" if str(e) == "no_speech" else "unsupported audio type"})
    raise HTTPException(415, detail={"code": "unsupported_type", "message": "supported: PDF, or audio (WAV, MP3, M4A, OGG, WEBM)"})


@router.get("/voice/samples")
def voice_samples() -> list[dict]:
    return voice.list_samples()


@router.get("/voice/samples/{name}/audio")
def voice_sample_audio(name: str):
    if name not in voice.SAMPLES:
        raise _404()
    p = get_settings().library_path / "_voice" / f"{name}.wav"
    if not p.exists():
        raise _404()
    return FileResponse(p, media_type="audio/wav")


@router.post("/voice/samples/{name}/check")
def voice_sample_check(name: str, x_actor: str | None = Header(default=None)) -> dict:
    if name not in voice.SAMPLES:
        raise _404("no such sample")
    p = get_settings().library_path / "_voice" / f"{name}.wav"
    if not p.exists():
        raise _404("sample audio missing")
    from niyam.llm.sarvam import LLMUnavailable
    title, lang, expected = voice.SAMPLES[name]
    try:
        with tx() as c:
            did = voice.check_clip(c, p.read_bytes(), p.name, title=f"{title} (synthetic voice note)", owner="asha.verma@demo.paytm.example", product="Payment Gateway",
                                   merchant=None, actor=actor_of(x_actor), synthetic=True, expected=expected)
            return service.document_detail(c, did)
    except LLMUnavailable as e:
        raise HTTPException(503, detail={"code": e.code, "message": f"speech-to-text failed: {e}"})


# ---------------------------------------------------------------- file bytes, workbench, compare, pack
def _version_row(c, did: uuid.UUID, ref: str | None):
    if ref:
        try:
            q = c.execute(text("SELECT * FROM document_versions WHERE document_id=:d AND id=:i"), {"d": did, "i": uuid.UUID(ref)}).first()
        except ValueError:
            q = c.execute(text("SELECT * FROM document_versions WHERE document_id=:d AND version=:n"), {"d": did, "n": int(ref) if ref.isdigit() else -1}).first()
    else:
        q = c.execute(text("SELECT * FROM document_versions WHERE document_id=:d ORDER BY version DESC LIMIT 1"), {"d": did}).first()
    if not q:
        raise _404("version not found")
    return q


@router.get("/documents/{doc_id}/file")
def document_file(doc_id: str, version: str | None = None):
    with tx() as c:
        v = _version_row(c, _uuid(doc_id), version)
    if not v.blob_key:
        raise _404("this version has no stored file")
    return Response(content=blobs.get(v.blob_key), media_type=v.content_type, headers={"cache-control": "private, max-age=3600", "x-niyam-sha256": v.sha256})


class ApplyEdit(BaseModel):
    finding_id: str
    wording: str = Field(min_length=1, max_length=2000)


class ApplyReq(BaseModel):
    edits: list[ApplyEdit] = Field(min_length=1, max_length=40)
    commit: bool = False


@router.post("/documents/{doc_id}/apply")
def apply_edits(doc_id: str, req: ApplyReq, x_actor: str | None = Header(default=None)) -> dict:
    did = _uuid(doc_id)
    try:
        with tx() as c:
            out = workbench.apply(c, did, [e.model_dump() for e in req.edits], req.commit, actor_of(x_actor))
    except workbench.NotPdf:
        raise HTTPException(422, detail={"code": "not_pdf", "message": "the workbench edits PDF documents only"})
    except workbench.BadEdit as e:
        raise HTTPException(422, detail={"code": "bad_edit", "message": e.msg})
    except workbench.WordingTooLong as e:
        raise HTTPException(422, detail={"code": "wording_does_not_fit", "finding_id": e.finding_id, "locator": e.locator,
                                         "message": f"The replacement for {e.locator or 'this clause'}{f' (page {e.page})' if e.page else ''} is {e.new_len} characters, but the text it replaces is {e.old_len} and there is no free space below it. "
                                                    "Shorten the wording, or remove this edit and make it by hand. (Niyam will not shrink the text below 8 pt or flatten the page, because that would hide the rest of the page from the checks.)"})
    except pdfio.WordingDoesNotFit as e:
        raise HTTPException(422, detail={"code": "wording_does_not_fit", "finding_id": e.finding_id, "message": "the new wording does not fit in the space of the clause it replaces; shorten it"})
    if out is None:
        raise _404("document not found")
    if req.commit and not out["committed"] and out["stale_text_remains"]:
        raise HTTPException(409, detail={"code": "stale_text_remains", "message": "the old wording is still extractable from the edited PDF, so nothing was saved. Covering words is not a fix.",
                                         "stale_text_remains": out["stale_text_remains"]})
    return out


@router.get("/documents/{doc_id}/preview.pdf")
def preview_pdf(doc_id: str, token: str):
    b = workbench.preview_bytes(str(_uuid(doc_id)), token)
    if b is None:
        raise _404("preview expired; run Preview apply again")
    return Response(content=b, media_type="application/pdf", headers={"cache-control": "no-store", "x-niyam-working-copy": "true"})


@router.get("/documents/{doc_id}/page.png")
def page_png(doc_id: str, page: int = 1, version: str | None = None, dpi: int = 110):
    with tx() as c:
        v = _version_row(c, _uuid(doc_id), version)
    if v.content_type != "application/pdf":
        raise _404("not a PDF version")
    try:
        png = pdfio.render_page(blobs.get(v.blob_key), page, max(40, min(dpi, 200)))
    except IndexError:
        raise _404("page out of range")
    return Response(content=png, media_type="image/png", headers={"cache-control": "private, max-age=3600"})


@router.get("/documents/{doc_id}/compare")
def compare(doc_id: str, from_version: str = Query(alias="from"), to: str = Query()) -> dict:
    did = _uuid(doc_id)
    with tx() as c:
        a, b = _version_row(c, did, from_version), _version_row(c, did, to)
    if a.content_type != "application/pdf" or b.content_type != "application/pdf":
        raise HTTPException(422, detail={"code": "not_pdf", "message": "compare works on PDF versions"})
    da, db = blobs.get(a.blob_key), blobs.get(b.blob_key)
    n = max((a.media or {}).get("pages", 0), (b.media or {}).get("pages", 0))
    pages = []
    for p in range(1, n + 1):
        pages.append({"page": p, "from_url": f"/api/v1/documents/{did}/page.png?version={a.id}&page={p}" if p <= (a.media or {}).get("pages", 0) else None,
                      "to_url": f"/api/v1/documents/{did}/page.png?version={b.id}&page={p}" if p <= (b.media or {}).get("pages", 0) else None,
                      "changed": pdfio.page_hash(da, p) != pdfio.page_hash(db, p)})
    return {"from": {"version_id": str(a.id), "version": a.version, "sha256": a.sha256}, "to": {"version_id": str(b.id), "version": b.version, "sha256": b.sha256}, "pages": pages}


@router.get("/evidence/{doc_id}/pack.pdf")
def evidence_pack(doc_id: str):
    import html as _h
    import pymupdf
    did = _uuid(doc_id)
    with tx() as c:
        r = evidence_record(c, did)
        if not r:
            raise _404("document not found")
        cur = _version_row(c, did, None)
        if cur.content_type != "application/pdf":
            raise HTTPException(422, detail={"code": "not_pdf", "message": "the PDF pack is available for PDF documents"})
        latest = blobs.get(cur.blob_key)
    d = r["document"]
    rows = "".join(f"<tr><td>{_h.escape(f['status'])}</td><td>{_h.escape(f['severity'])}</td><td>{_h.escape(f['locator'])}</td><td>{_h.escape(f['rule_id'] or f['fact_id'] or '')}</td>"
                   f"<td>{_h.escape((f['quote'] or '')[:140])}</td><td>{_h.escape(f['decision'] or '-')}</td></tr>" for f in r["findings"])
    apr = "".join(f"<li>{_h.escape(a['kind'])} <b>{_h.escape(a['status'])}</b> by {_h.escape(a['decided_by'] or 'nobody yet')} {_h.escape(a['decided_at'] or '')}: {_h.escape(a['title'])}</li>" for a in r["approvals"]) or "<li>none</li>"
    rts = "".join(f"<li>{_h.escape(x['ts'])}: {'PASSED' if x['passed'] else 'not passed'} (open {x['before']['open']} to {x['after']['open']}) by {_h.escape(x['actor'])}</li>" for x in r["retests"]) or "<li>none</li>"
    html = f"""<body style='font-family:sans-serif;font-size:9.5pt'><h1 style='font-size:17pt'>Evidence pack: {_h.escape(d['title'])}</h1>
<p style='color:#555'>Decision support, not legal advice. Synthetic demo document; product facts are Paytm-controlled demo data.</p>
<h2>File integrity</h2><p>Original v{r['hashes']['original']['version']} SHA-256:<br><code>{r['hashes']['original']['sha256']}</code></p>
<p>Current v{r['hashes']['current']['version']} SHA-256:<br><code>{r['hashes']['current']['sha256']}</code></p><p>Audit chain intact: <b>{'yes' if r['chain_ok'] else 'NO'}</b></p>
<h2>Findings (latest review)</h2><table border='1' cellpadding='3' style='border-collapse:collapse'><tr><th>Status</th><th>Severity</th><th>Where</th><th>Source</th><th>Quote</th><th>Decision</th></tr>{rows}</table>
<h2>Approvals</h2><ul>{apr}</ul><h2>Re-tests</h2><ul>{rts}</ul><p style='color:#555'>The document that follows is the current version, metadata stripped.</p></body>"""
    story = pymupdf.Story(html)
    buf = pymupdf.DocumentWriter(buf_path := f"/tmp/niyam-pack-{uuid.uuid4().hex}.pdf")
    box = pymupdf.paper_rect("a4")
    more = 1
    while more:
        dev = buf.begin_page(box)
        more, _ = story.place(box + (46, 50, -46, -50))
        story.draw(dev)
        buf.end_page()
    buf.close()
    out = pymupdf.open(buf_path)
    out.insert_pdf(pymupdf.open(stream=latest, filetype="pdf"))
    out.set_metadata({})
    data = out.tobytes(garbage=4, deflate=True)
    import os
    os.unlink(buf_path)
    return Response(content=data, media_type="application/pdf", headers={"content-disposition": f"attachment; filename=evidence-pack-{doc_id[:8]}.pdf"})
