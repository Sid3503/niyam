"""Review one document version: clauses -> findings. Idempotent per (version, rule fingerprint).

Order of evidence for every clause:
  1. Tier A product-fact checks (claims.py)  -> findings against Paytm-controlled facts
  2. Tier A rule-card engine, ACTIVE cards only -> findings against approved regulatory rules
  3. Optional Tier B (Sarvam) on engine `review` verdicts
Then: missing required disclosures (whole document) and cross-document consistency for the same merchant.
Nothing here edits a document. Missing evidence is never `current` (also enforced by a DB CHECK).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
import uuid

from sqlalchemy import text
from sqlalchemy.engine import Connection

from niyam import engine
from niyam.config import get_settings
from niyam.db import audit
from niyam.review import claims
from niyam.review.segment import Clause, segment
from niyam.rules import loader

PIPELINE_VERSION = "p5"
# Cards that make sense on a proposal/contract clause. The rest govern live customer interactions (checkout screen ordering, support-chat
# identifier masking, complaint-reply escalation) and would only produce false positives on contract text.
DOC_APPLICABLE = {"RBI-TAT-UPI-MERCHANT", "RBI-TAT-UPI-TRANSFER", "RBI-TAT-COMP-100", "SEBI-NO-ASSURED-RETURNS", "RBI-KFS-LOAN", "RBI-COOLING-OFF", "DPDP-CONSENT-PURPOSE"}


def doc_applicable(card: dict) -> bool:
    return card["id"] in DOC_APPLICABLE or card["source"].get("file") is None   # circular-derived cards are reviewed by keyword + Tier B
SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


# ---------------------------------------------------------------- rules in force
def active_cards(conn: Connection) -> list:
    return conn.execute(
        text("""SELECT DISTINCT ON (id) id, version, status, severity, card, card_sha256 FROM rule_cards
                WHERE tenant_id=:t AND status='active' ORDER BY id, version DESC"""), {"t": get_settings().tenant_id}).all()


def fingerprint(conn: Connection, as_of: dt.date | None = None, rows: list | None = None) -> tuple[str, list[dict]]:
    rows = rows if rows is not None else active_cards(conn)
    as_of = as_of or loader.as_of_date()
    rules = [{"id": r.id, "version": r.version, "sha": r.card_sha256} for r in rows]
    body = json.dumps({"rules": rules, "facts": claims.facts_fingerprint(), "as_of": as_of.isoformat(), "pipeline": PIPELINE_VERSION},
                      sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest(), rules


# ---------------------------------------------------------------- per-clause rule engine
def _clause_facts(t: str) -> dict:
    low = t.lower()
    f: dict = {}
    if "upi" in low or "refund" in low or "merchant payment" in low:
        f["product"] = "UPI"
    elif any(w in low for w in ("loan", "emi", "pay later", "lending")):
        f["product"] = "digital lending"
    elif any(w in low for w in ("mutual fund", "invest", "returns", "sip ", "equity")):
        f["product"] = "investment advice"
    return f


def rule_hits(clause: Clause, cards: list[dict], as_of: dt.date, *, llm: bool = False, tier_b_budget: list[int] | None = None) -> tuple[list[dict], list[dict]]:
    """Findings (as dicts) from approved rule cards for one clause. Returns (findings, model_call_rows)."""
    facts = _clause_facts(clause.text)
    cards = [c for c in cards if doc_applicable(c)]
    if not facts or not cards:
        return [], []
    verdicts = engine.run_checks(clause.text, facts, cards, as_of=as_of)
    calls: list[dict] = []
    if llm and (tier_b_budget is None or tier_b_budget[0] > 0):
        from niyam.judge import tier_b
        verdicts, calls = tier_b.apply(verdicts, {c["id"]: c for c in cards}, clause.text, facts, enabled=True)
        if tier_b_budget is not None:
            tier_b_budget[0] -= len(calls)
    by_id = {c["id"]: c for c in cards}
    out = []
    for v in verdicts:
        card = by_id[v["rule_id"]]
        if v["verdict"] not in ("fail", "review"):
            continue
        span = v.get("span")
        quote = v.get("quote")
        if quote and span and clause.text[span[0]:span[1]] == quote:
            start, end = clause.start + span[0], clause.start + span[1]
        elif v["verdict"] == "fail":
            quote, start, end = clause.text, clause.start, clause.end     # a fail must still carry a verbatim quote
        else:
            continue                                                      # a review without a quote is noise, not evidence
        src = v.get("source") or card["source"]
        out.append({
            "status": "contradiction" if v["verdict"] == "fail" else "review", "severity": card["severity"],
            "confidence": float(v.get("confidence", 0.0)), "reason": v["reason"], "rule_id": card["id"], "rule_version": card["version"],
            "rule_status": card["status"], "fact_id": None, "tier": str(v.get("tier", "A")), "quote": quote, "span": (start, end),
            "clause_idx": clause.idx, "locator": clause.locator,
            "source": {"document": card["source"].get("document"), "reference": card["source"].get("reference"),
                       "locator": card["source"].get("locator"), "quote": (card["source"].get("quotes") or [""])[0],
                       "regulator": card["source"].get("regulator"), "provenance": card["source"].get("provenance")},
            "suggested_fix": None,
        })
    return out, calls


# ---------------------------------------------------------------- fact-based findings
def _fix_for(fid: str, quote: str) -> dict | None:
    f = claims.load_facts()["by_id"].get(fid)
    if not f:
        return None
    w = f["approved_wording"]
    return {"wording": w, "rationale": f"Compliance-approved wording from {f['title']} ({claims.load_facts()['label']}). Replaces: \"{quote[:120]}\"",
            "validated": claims.validate_wording(fid, w), "source": "approved_wording"}


def _hit_to_finding(h: claims.Hit) -> dict:
    return {"status": h.status, "severity": h.severity, "confidence": h.confidence, "reason": h.reason, "rule_id": None, "rule_version": None,
            "rule_status": None, "fact_id": h.fact_id, "tier": "A", "quote": h.quote, "span": h.span, "clause_idx": h.clause_idx,
            "locator": h.locator, "source": claims.source_for_fact(h.fact_id),
            "suggested_fix": _fix_for(h.fact_id, h.quote) if h.status in ("contradiction", "outdated", "review") else None}


def _missing_findings(doc_type: str, content: str) -> list[dict]:
    out = []
    for d in claims.missing_disclosures(doc_type, content):
        wording = d["approved_wording"]
        out.append({"status": "missing", "severity": d["severity"], "confidence": 0.9,
                    "reason": f"This {doc_type.replace('_', ' ')} has no statement covering: {d['title'].lower()}.",
                    "rule_id": None, "rule_version": None, "rule_status": None, "fact_id": d["id"], "tier": "A", "quote": None, "span": None,
                    "clause_idx": None, "locator": "document",
                    "source": {"fact_id": d["id"], "title": d["title"], "statement": f"Required disclosure for {doc_type.replace('_', ' ')} documents.",
                               "label": claims.load_facts()["label"]},
                    "suggested_fix": {"wording": wording, "rationale": "Compliance-approved wording to add as a new clause.",
                                      "validated": claims.disclosure_present(d, wording), "source": "approved_wording"}})
    return out


def _fmt(kind: str, v: float) -> str:
    return f"T+{v / 24:g}" if kind == "settlement_hours" else f"{v:g}%"


def _cross_findings(conn: Connection, doc, clauses: list[Clause], existing: list[dict]) -> list[dict]:
    if not doc.merchant or doc.doc_type not in ("agreement", "order_form"):
        return []                              # only the binding document is held to the merchant-facing proposal
    mine = claims.extract_terms(clauses)
    others = conn.execute(text("""SELECT d.id, d.title, v.content FROM sales_documents d
        JOIN document_versions v ON v.id=(SELECT id FROM document_versions WHERE document_id=d.id ORDER BY version DESC LIMIT 1)
        WHERE d.tenant_id=:t AND d.merchant=:m AND d.id<>:i"""), {"t": get_settings().tenant_id, "m": doc.merchant, "i": doc.doc_id}).all()
    out = []
    flagged = {(f["clause_idx"], f["fact_id"]) for f in existing if f["status"] != "current"}
    for o in others:
        theirs = claims.extract_terms(segment(o.content))
        for kind, fid, label in (("settlement_hours", "PF-PG-SETTLEMENT", "settlement time"), ("card_mdr", "PF-PG-FEE-CARD", "card MDR")):
            if not mine[kind] or not theirs[kind]:
                continue
            mv = {round(x["value"], 2) for x in mine[kind]}
            tv = {round(x["value"], 2) for x in theirs[kind]}
            if mv & tv:
                continue
            m0, t0 = mine[kind][0], theirs[kind][0]
            if (m0["clause_idx"], fid) in flagged:
                continue                      # already judged against the approved fact; no duplicate noise
            out.append({"status": "contradiction", "severity": "high", "confidence": 0.8,
                        "reason": f"The {label} here ({_fmt(kind, m0['value'])}) differs from \"{o.title}\" ({_fmt(kind, t0['value'])}) for the same merchant.",
                        "rule_id": None, "rule_version": None, "rule_status": None, "fact_id": fid, "tier": "A", "quote": m0["quote"],
                        "span": tuple(m0["span"]), "clause_idx": m0["clause_idx"], "locator": m0["locator"],
                        "source": {**claims.source_for_fact(fid), "other_document": {"title": o.title, "locator": t0["locator"], "quote": t0["quote"]}},
                        "suggested_fix": _fix_for(fid, m0["quote"])})
    return out


# ---------------------------------------------------------------- the review itself
def compute_findings(conn: Connection, v, rows: list, as_of: dt.date, *, llm: bool = False) -> tuple[list[dict], list[dict]]:
    """All findings for `v` (needs .content .doc_type .merchant .doc_id .title). Pure computation: nothing is written."""
    clauses = segment(v.content)
    cards = [r.card for r in rows]
    findings: list[dict] = []
    all_calls: list[dict] = []
    budget = [get_settings().tier_b_max_calls_per_check]
    for c in clauses:
        for h in claims.check_clause(c):
            findings.append(_hit_to_finding(h))
        fs, calls = rule_hits(c, cards, as_of, llm=llm, tier_b_budget=budget)
        findings += fs
        all_calls += calls
    findings += _missing_findings(v.doc_type, v.content)
    findings += _cross_findings(conn, v, clauses, findings)
    findings.sort(key=lambda f: (SEV_RANK[f["severity"]], f["clause_idx"] if f["clause_idx"] is not None else 10**6))
    return findings, all_calls


def annotate_geometry(findings: list[dict], *, pdf: bytes | None, page_map: list | None, media: dict | None) -> None:
    """Attach page + bbox (PDF) or audio time (voice) to each finding that has a span."""
    from niyam.review import pdfio
    for f in findings:
        f.setdefault("page", None)
        f.setdefault("bbox", None)
        f.setdefault("audio", None)
        sp = f.get("span")
        if not sp:
            continue
        if pdf and page_map:
            loc = pdfio.locate(pdf, page_map, sp[0], sp[1], f.get("quote") or "")
            if loc:
                f["page"], f["bbox"] = loc
        if media and media.get("sentences"):
            hit = next((s for s in media["sentences"] if s["start_char"] <= sp[0] < s["end_char"]), None)
            if hit:
                f["audio"] = (hit["start"], hit["end"])


def review_version(conn: Connection, version_id: uuid.UUID, trigger: str, *, actor: str = "agent", llm: bool = False, force: bool = False) -> dict:
    st = get_settings()
    v = conn.execute(text("""SELECT v.id, v.content, v.version, v.content_type, v.blob_key, v.page_map, v.media, d.id AS doc_id, d.title, d.doc_type, d.owner, d.merchant, d.product
                             FROM document_versions v JOIN sales_documents d ON d.id=v.document_id WHERE v.id=:i"""), {"i": version_id}).one()
    rows = active_cards(conn)
    as_of = loader.as_of_date()
    fp, rules = fingerprint(conn, as_of, rows)
    have = conn.execute(text("SELECT id FROM doc_reviews WHERE version_id=:v AND fingerprint=:f"), {"v": version_id, "f": fp}).first()
    if have and not force:
        return {"review_id": have.id, "created": False, "fingerprint": fp}
    t0 = time.perf_counter()
    findings, all_calls = compute_findings(conn, v, rows, as_of, llm=llm)
    pdf = None
    if v.content_type == "application/pdf" and v.blob_key:
        from niyam.review import blobs
        pdf = blobs.get(v.blob_key)
    annotate_geometry(findings, pdf=pdf, page_map=v.page_map, media=v.media)

    if have and force:
        conn.execute(text("DELETE FROM doc_reviews WHERE id=:i"), {"i": have.id})
    review_id = uuid.uuid4()
    conn.execute(text("""INSERT INTO doc_reviews (id, tenant_id, version_id, fingerprint, trigger, engine_version, rules, duration_ms)
                         VALUES (:i,:t,:v,:f,:tr,:ev,CAST(:r AS jsonb),:d)"""),
                 dict(i=review_id, t=st.tenant_id, v=version_id, f=fp, tr=trigger, ev=f"{PIPELINE_VERSION}/{getattr(engine, '__version__', '0')}",
                      r=json.dumps(rules), d=round((time.perf_counter() - t0) * 1000)))
    for f in findings:
        sp = f["span"]
        au = f.get("audio")
        conn.execute(text("""INSERT INTO findings (id, tenant_id, review_id, version_id, clause_idx, locator, quote, span_start, span_end, status, severity,
                             confidence, reason, rule_id, rule_version, rule_status, fact_id, source, tier, suggested_fix, needs_human, page, bbox, audio_start, audio_end)
                             VALUES (:i,:t,:rv,:v,:ci,:lo,:q,:s0,:s1,:st,:sv,:cf,:rs,:ri,:rver,:rst,:fi,CAST(:src AS jsonb),:tier,CAST(:fx AS jsonb),:nh,:pg,CAST(:bb AS jsonb),:a0,:a1)"""),
                     dict(i=uuid.uuid4(), t=st.tenant_id, rv=review_id, v=version_id, ci=f["clause_idx"], lo=f["locator"], q=f["quote"],
                          s0=sp[0] if sp else None, s1=sp[1] if sp else None, st=f["status"], sv=f["severity"], cf=f["confidence"], rs=f["reason"],
                          ri=f["rule_id"], rver=f["rule_version"], rst=f["rule_status"], fi=f["fact_id"], src=json.dumps(f["source"]), tier=f["tier"],
                          fx=json.dumps(f["suggested_fix"]) if f["suggested_fix"] else None,
                          nh=f["status"] == "review" or f["severity"] in ("high", "critical") or f["confidence"] < 0.8,
                          pg=f.get("page"), bb=json.dumps(f["bbox"]) if f.get("bbox") else None, a0=au[0] if au else None, a1=au[1] if au else None))
    if all_calls:
        from niyam.api.fix import log_calls
        log_calls(conn, all_calls)
    counts = {k: sum(1 for f in findings if f["status"] == k) for k in ("current", "outdated", "missing", "contradiction", "review")}
    audit.append(conn, actor=actor, action="document.reviewed", object_type="document", object_id=str(v.doc_id),
                 payload={"version": v.version, "version_id": str(version_id), "trigger": trigger, "fingerprint": fp, "findings": counts,
                          "document_id": str(v.doc_id), "active_rules": [f"{r['id']}.v{r['version']}" for r in rules]})
    attention = sum(n for k, n in counts.items() if k != "current")
    if attention and trigger in ("scan", "upload", "rule_change", "workbench"):
        conn.execute(text("""INSERT INTO notifications (id, tenant_id, document_id, recipient, subject, payload) VALUES (:i,:t,:d,:r,:s,CAST(:p AS jsonb))"""),
                     dict(i=uuid.uuid4(), t=st.tenant_id, d=v.doc_id, r=v.owner,
                          s=f"{attention} finding(s) need attention in \"{v.title}\" (v{v.version})", p=json.dumps({"counts": counts, "trigger": trigger})))
    return {"review_id": review_id, "created": True, "fingerprint": fp, "counts": counts}
