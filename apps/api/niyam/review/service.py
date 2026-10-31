"""Library, scan, document detail, re-test, approvals and impact. The original document is never modified: edits become new versions."""
from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import json
import re
import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection

from niyam import engine
from niyam.config import get_settings
from niyam.db import audit
from niyam.review import blobs, claims, pdfio, pipeline
from niyam.review.segment import parse_front_matter, segment
from niyam.rules import loader

NS = uuid.UUID("6f1c0e0e-0b0a-4b8e-9c55-6e1a4b1f0a11")
STATUSES = ("current", "outdated", "missing", "contradiction", "review")
SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _t() -> str:
    return get_settings().tenant_id


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def doc_id_for(path: str) -> uuid.UUID:
    return uuid.uuid5(NS, path)


def _iso(x):
    return x.isoformat(timespec="seconds") if x else None


# ------------------------------------------------------------------ library files
def library_files() -> list[dict]:
    root = get_settings().library_path
    out = []
    if not root.exists():
        return out
    for p in sorted(root.iterdir()):
        if p.name.startswith("_") or p.name.endswith(".meta.json"):
            continue
        mtime = dt.datetime.fromtimestamp(p.stat().st_mtime, dt.timezone.utc)
        if p.suffix == ".md":
            raw = p.read_text(encoding="utf-8")
            meta, body = parse_front_matter(raw)
            out.append({"path": f"library/{p.name}", "meta": meta, "body": body, "sha": sha(body), "mtime": mtime, "format": "markdown"})
        elif p.suffix == ".pdf":
            data = p.read_bytes()
            side = p.with_name(p.name + ".meta.json")
            meta = json.loads(side.read_text(encoding="utf-8")) if side.exists() else {}
            ex = pdfio.extract(data)
            out.append({"path": f"library/{p.name}", "meta": meta, "body": ex.content, "sha": hashlib.sha256(data).hexdigest(), "mtime": mtime,
                        "format": "pdf", "pdf": data, "extracted": ex})
    return out


def _upsert_document(conn: Connection, path: str, meta: dict, fmt: str = "markdown") -> uuid.UUID:
    did = doc_id_for(path)
    conn.execute(text("""INSERT INTO sales_documents (id, tenant_id, source_path, title, doc_type, product, owner, merchant, channel, format)
        VALUES (:i,:t,:p,:ti,:dt,:pr,:ow,:me,:ch,:fm)
        ON CONFLICT (tenant_id, source_path) DO UPDATE SET title=EXCLUDED.title, doc_type=EXCLUDED.doc_type, product=EXCLUDED.product,
          owner=EXCLUDED.owner, merchant=EXCLUDED.merchant, channel=EXCLUDED.channel"""),
                 dict(i=did, t=_t(), p=path, ti=meta.get("title") or Path(path).stem, dt=meta.get("doc_type", "proposal"),
                      pr=meta.get("product", "Payment Gateway"), ow=meta.get("owner", "unassigned"), me=meta.get("merchant") or None,
                      ch=meta.get("channel") or None, fm=fmt))
    return did


def _add_version(conn: Connection, did: uuid.UUID, body: str, trigger: str, mtime=None, actor: str = "agent", *, file_sha: str | None = None,
                 content_type: str = "text/markdown", blob: bytes | None = None, page_map: list | None = None, media: dict | None = None) -> tuple[uuid.UUID, int, bool]:
    """New version only when the content (or, for files, the bytes) differs from the latest one. Returns (version_id, number, created)."""
    last = conn.execute(text("SELECT id, version, sha256 FROM document_versions WHERE document_id=:d ORDER BY version DESC LIMIT 1"), {"d": did}).first()
    h = file_sha or sha(body)
    if last and last.sha256 == h:
        return last.id, last.version, False
    n = (last.version + 1) if last else 1
    key = blobs.put(blob)[0] if blob is not None else None
    vid = uuid.uuid4()
    conn.execute(text("""INSERT INTO document_versions (id, tenant_id, document_id, version, sha256, content, trigger, source_mtime, content_type, blob_key, blob_sha256, page_map, media)
                         VALUES (:i,:t,:d,:n,:h,:c,:tr,:m,:ct,:bk,:bh,CAST(:pm AS jsonb),CAST(:me AS jsonb))"""),
                 dict(i=vid, t=_t(), d=did, n=n, h=h, c=body, tr=trigger, m=mtime, ct=content_type, bk=key, bh=key,
                      pm=json.dumps(page_map) if page_map is not None else None, me=json.dumps(media) if media is not None else None))
    audit.append(conn, actor=actor, action="document.version", object_type="document", object_id=str(did),
                 payload={"version": n, "sha256": h, "trigger": trigger, "document_id": str(did), "content_type": content_type})
    return vid, n, True


def add_pdf_version(conn: Connection, did: uuid.UUID, data: bytes, trigger: str, actor: str, mtime=None, ex: "pdfio.Extracted | None" = None) -> tuple[uuid.UUID, int, bool]:
    ex = ex or pdfio.extract(data)
    return _add_version(conn, did, ex.content, trigger, mtime, actor, file_sha=hashlib.sha256(data).hexdigest(), content_type="application/pdf", blob=data,
                        page_map=ex.page_map, media={"pages": ex.pages, "page_sizes": ex.page_sizes})


# ------------------------------------------------------------------ listing
_LATEST = """
WITH lv AS (SELECT DISTINCT ON (document_id) id, document_id, version, sha256, created_at, trigger FROM document_versions WHERE tenant_id=:t ORDER BY document_id, version DESC),
     lr AS (SELECT DISTINCT ON (r.version_id) r.id, r.version_id, r.fingerprint, r.reviewed_at FROM doc_reviews r JOIN lv ON lv.id=r.version_id ORDER BY r.version_id, r.reviewed_at DESC)
"""


def _open_clause() -> str:
    return "f.status<>'current' AND NOT EXISTS (SELECT 1 FROM approvals a WHERE a.finding_id=f.id AND a.kind='fix' AND a.status IN ('approved','rejected'))"


def _counts_for(conn: Connection) -> dict[uuid.UUID, dict]:
    rows = conn.execute(text(_LATEST + f"""SELECT lv.document_id, f.status, count(*) n, count(*) FILTER (WHERE {_open_clause()}) open_n
        FROM lv JOIN lr ON lr.version_id=lv.id JOIN findings f ON f.review_id=lr.id GROUP BY lv.document_id, f.status"""), {"t": _t()}).all()
    out: dict = {}
    for r in rows:
        d = out.setdefault(r.document_id, {"by_status": {s: 0 for s in STATUSES}, "open": 0})
        d["by_status"][r.status] = r.n
        d["open"] += r.open_n
    return out


def _doc_json(row, files_by_path: dict, counts: dict, cur_fp: str, last_scan: dict) -> dict:
    media = getattr(row, "media", None) or {}
    return {"id": str(row.id), "title": row.title, "doc_type": row.doc_type, "product": row.product, "owner": row.owner, "merchant": row.merchant,
            "channel": row.channel, "version": row.version, "format": getattr(row, "format", "markdown"), "pages": media.get("pages"),
            "duration_seconds": media.get("duration_seconds"), "last_modified": _iso(row.last_modified), "status": row.status,
            "demo_data": True, "open_findings": counts.get(row.id, {}).get("open", 0),
            "by_status": counts.get(row.id, {}).get("by_status", {s: 0 for s in STATUSES}), "last_reviewed_at": _iso(row.reviewed_at),
            "source_path": row.source_path}


def list_library(conn: Connection) -> list[dict]:
    fp, _ = pipeline.fingerprint(conn)
    files = {f["path"]: f for f in library_files()}
    counts = _counts_for(conn)
    rows = conn.execute(text(_LATEST + """
        SELECT d.id, d.title, d.doc_type, d.product, d.owner, d.merchant, d.channel, d.source_path, d.format, lv.version, lv.created_at, lv.sha256,
               (SELECT media FROM document_versions mv WHERE mv.id=lv.id) AS media,
               lr.fingerprint, lr.reviewed_at,
               (SELECT sha256 FROM document_versions v WHERE v.document_id=d.id AND v.trigger IN ('scan','upload') ORDER BY version DESC LIMIT 1) AS origin_sha
        FROM sales_documents d LEFT JOIN lv ON lv.document_id=d.id LEFT JOIN lr ON lr.version_id=lv.id WHERE d.tenant_id=:t"""), {"t": _t()}).all()
    scan = conn.execute(text("SELECT detail FROM scans WHERE tenant_id=:t ORDER BY started_at DESC LIMIT 1"), {"t": _t()}).scalar() or []
    last_out = {x["document_id"]: x["outcome"] for x in scan}
    out, seen = [], set()
    for r in rows:
        seen.add(r.source_path)
        f = files.get(r.source_path)
        if r.reviewed_at is None:
            status = "changed" if r.version and r.version > 1 else "new"
        elif f and f["sha"] != r.origin_sha:
            status = "changed"
        elif r.fingerprint != fp:
            status = "changed"                              # rules changed since the last review
        elif last_out.get(str(r.id)) == "skipped_unchanged":
            status = "unchanged"
        else:
            status = "reviewed"
        out.append(_doc_json(type("R", (), {**r._mapping, "status": status, "last_modified": f["mtime"] if f else r.created_at})(), files, counts, fp, last_out))
    for path, f in files.items():
        if path in seen:
            continue
        m = f["meta"]
        did = doc_id_for(path)
        out.append({"id": str(did), "title": m.get("title") or Path(path).stem, "doc_type": m.get("doc_type", "proposal"), "product": m.get("product", "Payment Gateway"),
                    "owner": m.get("owner", "unassigned"), "merchant": m.get("merchant") or None, "channel": m.get("channel") or None, "version": 0, "format": f["format"], "pages": None, "duration_seconds": None,
                    "last_modified": _iso(f["mtime"]), "status": "new", "demo_data": True, "open_findings": 0,
                    "by_status": {s: 0 for s in STATUSES}, "last_reviewed_at": None, "source_path": path})
    out.sort(key=lambda d: (d["title"]))
    return out


# ------------------------------------------------------------------ scan
def scan(conn: Connection, *, actor: str, trigger: str = "scan_now", llm: bool = False) -> dict:
    sid = uuid.uuid4()
    started = dt.datetime.now(dt.timezone.utc)
    files = library_files()
    detail, reviewed, skipped = [], 0, 0
    for f in files:
        meta = f["meta"]
        did = _upsert_document(conn, f["path"], meta, f["format"])
        origin = conn.execute(text("SELECT sha256, version FROM document_versions WHERE document_id=:d AND trigger IN ('scan','upload') ORDER BY version DESC LIMIT 1"), {"d": did}).first()
        outcome = "new" if origin is None else ("changed" if origin.sha256 != f["sha"] else "unchanged")
        if outcome == "unchanged":
            vid = conn.execute(text("SELECT id FROM document_versions WHERE document_id=:d AND sha256=:h ORDER BY version DESC LIMIT 1"), {"d": did, "h": f["sha"]}).scalar()
        else:
            if f["format"] == "pdf":
                vid, _, _ = add_pdf_version(conn, did, f["pdf"], "scan", actor, f["mtime"], f["extracted"])
            else:
                vid, _, _ = _add_version(conn, did, f["body"], "scan", f["mtime"], actor)
        r = pipeline.review_version(conn, vid, "scan", actor=actor, llm=llm)
        n_find = conn.execute(text("SELECT count(*) FROM findings WHERE review_id=:r AND status<>'current'"), {"r": r["review_id"]}).scalar()
        if r["created"]:
            reviewed += 1
            res = outcome if outcome != "unchanged" else "reviewed"
        else:
            skipped += 1
            res = "skipped_unchanged"
        detail.append({"document_id": str(did), "title": meta.get("title") or f["path"], "outcome": res, "findings": n_find})
    conn.execute(text("INSERT INTO scans (id, tenant_id, trigger, started_at, finished_at, discovered, reviewed, skipped, detail, actor) VALUES (:i,:t,:tr,:s,now(),:d,:r,:k,CAST(:x AS jsonb),:a)"),
                 dict(i=sid, t=_t(), tr=trigger, s=started, d=len(files), r=reviewed, k=skipped, x=json.dumps(detail), a=actor))
    audit.append(conn, actor=actor, action="library.scan", object_type="scan", object_id=str(sid),
                 payload={"trigger": trigger, "discovered": len(files), "reviewed": reviewed, "skipped": skipped})
    return {"scan_id": str(sid), "trigger": trigger, "started_at": _iso(started), "discovered": len(files), "reviewed": reviewed, "skipped": skipped, "documents": detail}


# ------------------------------------------------------------------ detail
def finding_json(r) -> dict:
    sp = [r.span_start, r.span_end] if r.span_start is not None else None
    appr = {"id": str(r.appr_id), "status": r.appr_status} if getattr(r, "appr_id", None) else None
    dec = r.appr_status if appr and r.appr_status in ("approved", "rejected", "deferred") else None
    return {"id": str(r.id), "version_id": str(r.version_id), "clause_idx": r.clause_idx, "locator": r.locator, "quote": r.quote, "span": sp,
            "status": r.status, "severity": r.severity, "confidence": float(r.confidence), "reason": r.reason, "rule_id": r.rule_id,
            "rule_version": r.rule_version, "rule_status": r.rule_status, "fact_id": r.fact_id, "source": r.source, "tier": r.tier,
            "suggested_fix": r.suggested_fix, "approval": appr, "decision": dec, "needs_human": r.needs_human,
            "page": r.page, "bbox": r.bbox, "audio_time": [r.audio_start, r.audio_end] if r.audio_start is not None else None}


_FIND_SQL = """SELECT f.*, a.id AS appr_id, a.status AS appr_status FROM findings f
   LEFT JOIN LATERAL (SELECT id, status FROM approvals WHERE finding_id=f.id AND kind='fix' ORDER BY created_at DESC LIMIT 1) a ON true"""


def findings_for_review(conn: Connection, review_id) -> list[dict]:
    rows = conn.execute(text(_FIND_SQL + " WHERE f.review_id=:r"), {"r": review_id}).all()
    out = [finding_json(r) for r in rows]
    out.sort(key=lambda f: (SEV_RANK[f["severity"]], f["clause_idx"] if f["clause_idx"] is not None else 10**6))
    return out


def document_detail(conn: Connection, did: uuid.UUID, version_id: uuid.UUID | None = None) -> dict | None:
    fp, _ = pipeline.fingerprint(conn)
    lib = {d["id"]: d for d in list_library(conn)}
    d = lib.get(str(did))
    if not d or d["version"] == 0:
        return None
    v = (conn.execute(text("SELECT * FROM document_versions WHERE id=:i AND document_id=:d"), {"i": version_id, "d": did}).first() if version_id else
         conn.execute(text("SELECT * FROM document_versions WHERE document_id=:d ORDER BY version DESC LIMIT 1"), {"d": did}).first())
    rev = conn.execute(text("SELECT id, fingerprint FROM doc_reviews WHERE version_id=:v ORDER BY reviewed_at DESC LIMIT 1"), {"v": v.id}).first()
    findings = findings_for_review(conn, rev.id) if rev else []
    versions = conn.execute(text("""SELECT v.id, v.version, v.sha256, v.created_at, v.trigger,
        (SELECT count(*) FROM findings f WHERE f.review_id=(SELECT id FROM doc_reviews WHERE version_id=v.id ORDER BY reviewed_at DESC LIMIT 1) AND f.status<>'current') AS n
        FROM document_versions v WHERE v.document_id=:d ORDER BY v.version DESC"""), {"d": did}).all()
    media = v.media or {}
    workbench = ({"pdf_url": f"/api/v1/documents/{did}/file?version={v.id}", "pages": media.get("pages", 0), "page_sizes": media.get("page_sizes", [])}
                 if v.content_type == "application/pdf" else None)
    voice = None
    if d["format"] == "voice":
        voice = {"audio_url": f"/api/v1/documents/{did}/file?version={v.id}", "duration_seconds": media.get("duration_seconds", 0), "language": media.get("language"),
                 "transcript_original": media.get("transcript_original", ""), "transcript_en": v.content, "sentences": media.get("sentences", []),
                 "stt": media.get("stt", {}), "timing_note": media.get("timing_note", "")}
    return {"document": d, "workbench": workbench, "voice": voice,
            "version": {"id": str(v.id), "version": v.version, "sha256": v.sha256, "content": v.content, "created_at": _iso(v.created_at), "trigger": v.trigger},
            "clauses": [{"idx": c.idx, "locator": c.locator, "text": c.text, "start": c.start, "end": c.end} for c in segment(v.content)],
            "findings": findings, "versions": [{"id": str(x.id), "version": x.version, "sha256": x.sha256, "created_at": _iso(x.created_at), "trigger": x.trigger, "open_findings": x.n} for x in versions],
            "rule_fingerprint": fp, "review_stale": bool(rev and rev.fingerprint != fp), "reviewed": rev is not None}


# ------------------------------------------------------------------ re-test
def _summ(findings: list[dict]) -> dict:
    by = {s: 0 for s in STATUSES}
    for f in findings:
        by[f["status"]] += 1
    return {"open": sum(n for s, n in by.items() if s != "current"), "by_status": by}


def _sig(f: dict) -> tuple:
    return (f["status"], f["rule_id"] or f["fact_id"], f["locator"] if f["status"] == "missing" else (f["quote"] or "")[:80])


def retest(conn: Connection, did: uuid.UUID, content: str | None, actor: str, llm: bool = False) -> dict:
    cur = conn.execute(text("SELECT id, version FROM document_versions WHERE document_id=:d ORDER BY version DESC LIMIT 1"), {"d": did}).first()
    if not cur:
        return None
    if content is not None and content.strip():
        ct = conn.execute(text("SELECT content_type FROM document_versions WHERE id=:i"), {"i": cur.id}).scalar()
        if ct != "text/markdown":
            raise ValueError("not_text_document")
    before_rev = conn.execute(text("SELECT id FROM doc_reviews WHERE version_id=:v ORDER BY reviewed_at DESC LIMIT 1"), {"v": cur.id}).scalar()
    if before_rev is None:
        pipeline.review_version(conn, cur.id, "retest", actor=actor, llm=llm)
        before_rev = conn.execute(text("SELECT id FROM doc_reviews WHERE version_id=:v ORDER BY reviewed_at DESC LIMIT 1"), {"v": cur.id}).scalar()
    before = findings_for_review(conn, before_rev)
    if content is not None and content.strip():
        vid, _, _ = _add_version(conn, did, content, "retest", None, actor)
    else:
        vid = cur.id
    pipeline.review_version(conn, vid, "retest", actor=actor, llm=llm, force=content is None)
    after_rev = conn.execute(text("SELECT id FROM doc_reviews WHERE version_id=:v ORDER BY reviewed_at DESC LIMIT 1"), {"v": vid}).scalar()
    after = findings_for_review(conn, after_rev)
    bsig, asig = {_sig(f): f for f in before if f["status"] != "current"}, {_sig(f): f for f in after if f["status"] != "current"}
    resolved = [bsig[k]["id"] for k in bsig if k not in asig]
    remaining = [asig[k]["id"] for k in asig if k in bsig]
    new = [asig[k]["id"] for k in asig if k not in bsig]
    passed = _summ(after)["open"] == 0
    conn.execute(text("INSERT INTO retests (id, tenant_id, document_id, from_version, to_version, passed, before, after, actor) VALUES (:i,:t,:d,:f,:to,:p,CAST(:b AS jsonb),CAST(:a AS jsonb),:ac)"),
                 dict(i=uuid.uuid4(), t=_t(), d=did, f=cur.id, to=vid, p=passed, b=json.dumps(_summ(before)), a=json.dumps(_summ(after)), ac=actor))
    audit.append(conn, actor=actor, action="document.retested", object_type="document", object_id=str(did),
                 payload={"document_id": str(did), "passed": passed, "before": _summ(before), "after": _summ(after), "from_version": cur.version,
                          "resolved": len(resolved), "new": len(new)})
    return {"passed": passed, "comparison": {"before": _summ(before), "after": _summ(after), "resolved": resolved, "remaining": remaining, "new": new}, "version_id": vid}


# ------------------------------------------------------------------ approvals
def ensure_rule_approvals(conn: Connection) -> int:
    n = 0
    for r in loader.latest_cards(conn):
        if r.status not in ("draft", "in_review"):
            continue
        if conn.execute(text("SELECT 1 FROM approvals WHERE tenant_id=:t AND kind='rule' AND rule_id=:i AND rule_version=:v"), {"t": _t(), "i": r.id, "v": r.version}).first():
            continue
        src = r.card["source"]
        payload = {"rule": rule_brief(r.card, r.status),
                   "source": {"document": src.get("document"), "reference": src.get("reference"), "locator": src.get("locator"),
                              "quote": (src.get("quotes") or [""])[0], "provenance": src.get("provenance"), "quote_verified": bool(r.validation.get("quotes_verified"))}}
        conn.execute(text("""INSERT INTO approvals (id, tenant_id, kind, severity, confidence, title, payload, rule_id, rule_version)
                             VALUES (:i,:t,'rule',:s,:c,:ti,CAST(:p AS jsonb),:r,:v)"""),
                     dict(i=uuid.uuid4(), t=_t(), s=r.severity, c=1.0 if r.validation.get("quotes_verified") else 0.6, ti=r.title, p=json.dumps(payload), r=r.id, v=r.version))
        n += 1
    return n


def rule_brief(card: dict, status: str | None = None) -> dict:
    return {"id": card["id"], "version": card["version"], "title": card["title"], "obligation": card["obligation"], "tier": card["check"]["tier"],
            "effective_from": card["effective_from"], "status": status or card["status"]}


def approval_json(r, extra: dict | None = None) -> dict:
    p = r.payload or {}
    out = {"id": str(r.id), "kind": r.kind, "status": r.status, "severity": r.severity, "confidence": float(r.confidence) if r.confidence is not None else None,
           "title": r.title, "created_at": _iso(r.created_at), "decided_at": _iso(r.decided_at), "decided_by": r.decided_by, "reason": r.reason,
           "document": p.get("document"), "clause": p.get("clause"), "finding_id": str(r.finding_id) if r.finding_id else None,
           "current_wording": p.get("current_wording"), "proposed_wording": p.get("proposed_wording"), "rule": p.get("rule"),
           "source": p.get("source") or {}}
    if extra:
        out.update(extra)
    return out


def create_fix_approval(conn: Connection, finding_id: uuid.UUID, actor: str) -> dict:
    f = conn.execute(text("""SELECT f.*, d.id AS doc_id, d.title AS doc_title, v.content FROM findings f JOIN document_versions v ON v.id=f.version_id
                             JOIN sales_documents d ON d.id=v.document_id WHERE f.id=:i"""), {"i": finding_id}).first()
    if not f:
        return None
    if not f.suggested_fix:
        raise ValueError("no_suggested_fix")
    ex = conn.execute(text("SELECT * FROM approvals WHERE finding_id=:i AND kind='fix' AND status IN ('pending','deferred') LIMIT 1"), {"i": finding_id}).first()
    if ex:
        return approval_json(ex)
    clause = None
    if f.clause_idx is not None:
        cl = next((c for c in segment(f.content) if c.idx == f.clause_idx), None)
        clause = {"locator": f.locator, "text": cl.text if cl else (f.quote or "")}
    payload = {"document": {"id": str(f.doc_id), "title": f.doc_title}, "clause": clause, "current_wording": f.quote,
               "proposed_wording": f.suggested_fix["wording"], "source": {**(f.source or {}), "quote_verified": True,
               "quote": (f.source or {}).get("quote") or (f.source or {}).get("statement")}, "status": f.status, "validated": f.suggested_fix.get("validated")}
    aid = uuid.uuid4()
    conn.execute(text("""INSERT INTO approvals (id, tenant_id, kind, severity, confidence, title, payload, finding_id, document_id)
                         VALUES (:i,:t,'fix',:s,:c,:ti,CAST(:p AS jsonb),:f,:d)"""),
                 dict(i=aid, t=_t(), s=f.severity, c=float(f.confidence), ti=f"{f.doc_title}: {f.locator}", p=json.dumps(payload), f=finding_id, d=f.doc_id))
    audit.append(conn, actor=actor, action="fix.sent_for_approval", object_type="approval", object_id=str(aid),
                 payload={"document_id": str(f.doc_id), "finding_id": str(finding_id), "status": f.status})
    return approval_json(conn.execute(text("SELECT * FROM approvals WHERE id=:i"), {"i": aid}).one())


def decide(conn: Connection, aid: uuid.UUID, decision: str, reason: str | None, actor: str) -> dict:
    a = conn.execute(text("SELECT * FROM approvals WHERE id=:i AND tenant_id=:t FOR UPDATE"), {"i": aid, "t": _t()}).first()
    if not a:
        return None
    new = {"approve": "approved", "reject": "rejected", "defer": "deferred"}[decision]
    if a.status in ("approved", "rejected"):
        raise ValueError("already_decided")
    now = dt.datetime.now(dt.timezone.utc)
    side = {}
    if a.kind == "rule":
        side = _decide_rule(conn, a, new, actor, now)
    conn.execute(text("UPDATE approvals SET status=:s, decided_at=:n, decided_by=:a, reason=:r WHERE id=:i"), dict(s=new, n=now, a=actor, r=reason, i=aid))
    audit.append(conn, actor=actor, action=f"approval.{new}", object_type="approval", object_id=str(aid),
                 payload={"kind": a.kind, "previous": a.status, "new": new, "reason": reason, "rule_id": a.rule_id, "rule_version": a.rule_version,
                          "document_id": str(a.document_id) if a.document_id else None, "finding_id": str(a.finding_id) if a.finding_id else None,
                          "proposed_wording": (a.payload or {}).get("proposed_wording"), **side})
    return approval_json(conn.execute(text("SELECT * FROM approvals WHERE id=:i"), {"i": aid}).one())


def _decide_rule(conn: Connection, a, new: str, actor: str, now) -> dict:
    row = conn.execute(text("SELECT * FROM rule_cards WHERE tenant_id=:t AND id=:i AND version=:v FOR UPDATE"), {"t": _t(), "i": a.rule_id, "v": a.rule_version}).one()
    if new == "rejected":
        conn.execute(text("UPDATE rule_cards SET status='rejected' WHERE tenant_id=:t AND id=:i AND version=:v"), {"t": _t(), "i": a.rule_id, "v": a.rule_version})
        return {}
    if new == "deferred":
        return {}
    card = dict(row.card)
    card.update(status="active", approved_by=actor, approved_at=now.isoformat(timespec="seconds"))
    body = json.dumps(card, ensure_ascii=False, sort_keys=True)
    prev = conn.execute(text("SELECT version FROM rule_cards WHERE tenant_id=:t AND id=:i AND status='active' AND version<>:v"), {"t": _t(), "i": a.rule_id, "v": a.rule_version}).all()
    for p in prev:
        conn.execute(text("UPDATE rule_cards SET status='superseded' WHERE tenant_id=:t AND id=:i AND version=:v"), {"t": _t(), "i": a.rule_id, "v": p.version})
    conn.execute(text("UPDATE rule_cards SET status='active', card=CAST(:c AS jsonb), card_sha256=:h WHERE tenant_id=:t AND id=:i AND version=:v"),
                 dict(c=body, h=sha(body), t=_t(), i=a.rule_id, v=a.rule_version))
    # Workflow B starts here: re-review every document against the new rule set, then open an owner task per affected document.
    reviewed = 0
    for d in conn.execute(text("SELECT id FROM sales_documents WHERE tenant_id=:t"), {"t": _t()}).all():
        vid = conn.execute(text("SELECT id FROM document_versions WHERE document_id=:d ORDER BY version DESC LIMIT 1"), {"d": d.id}).scalar()
        if vid and pipeline.review_version(conn, vid, "rule_change", actor="agent")["created"]:
            reviewed += 1
    imp = impact(conn, a.rule_id, a.rule_version)
    tasks = 0
    for x in imp["affected"]:
        r = conn.execute(text("""INSERT INTO impact_tasks (id, tenant_id, document_id, rule_id, rule_version, owner, title) VALUES (:i,:t,:d,:r,:v,:o,:ti)
                                 ON CONFLICT (document_id, rule_id, rule_version) DO NOTHING"""),
                         dict(i=uuid.uuid4(), t=_t(), d=uuid.UUID(x["document_id"]), r=a.rule_id, v=a.rule_version, o=x["owner"], ti=x["task"]["title"]))
        if r.rowcount:
            tasks += 1
            conn.execute(text("INSERT INTO notifications (id, tenant_id, document_id, recipient, subject, payload) VALUES (:i,:t,:d,:r,:s,CAST(:p AS jsonb))"),
                         dict(i=uuid.uuid4(), t=_t(), d=uuid.UUID(x["document_id"]), r=x["owner"],
                              s=f"New rule {a.rule_id} v{a.rule_version} may affect \"{x['title']}\" ({x['clause_locator']})", p=json.dumps({"rule_id": a.rule_id})))
    return {"activated_by": actor, "documents_re_reviewed": reviewed, "owner_tasks_created": tasks, "affected_documents": len(imp["affected"])}


# ------------------------------------------------------------------ impact
KEYWORDS = {
    "RBI-TAT-UPI-MERCHANT": ["refund", "reversal", "failed", "debited", "chargeback"], "RBI-TAT-UPI-TRANSFER": ["refund", "reversal", "failed", "debited"],
    "RBI-TAT-COMP-100": ["refund", "compensation", "delay"], "NPCI-UPI-CHARGES-PRE": ["convenience fee", "charge", "fee"],
    "NPCI-UPI-MASK-IDENTIFIERS": ["upi id", "vpa", "mobile number"], "SEBI-NO-ASSURED-RETURNS": ["assured", "guaranteed return", "returns", "mutual fund", "invest"],
    "RBI-KFS-LOAN": ["loan", "emi", "interest"], "RBI-COOLING-OFF": ["loan", "cancel", "prepay"], "RBI-OMB-ESCALATION": ["complaint", "grievance"],
    "DPDP-CONSENT-PURPOSE": ["consent", "personal data", "privacy"],
}


def _rule_keywords(card: dict) -> list[str]:
    cfg = card["check"].get("config", {})
    return [k.lower() for k in (cfg.get("claim_keywords") or KEYWORDS.get(card["id"], []))]


def _changes(old: dict, new: dict) -> list[str]:
    out = []
    for k, label in (("effective_from", "effective date"), ("severity", "severity")):
        if old.get(k) != new.get(k):
            out.append(f"{label}: {old.get(k)} -> {new.get(k)}")
    if old.get("obligation") != new.get("obligation"):
        sm = difflib.SequenceMatcher(None, old["obligation"].split(), new["obligation"].split())
        for tag, a0, a1, b0, b1 in sm.get_opcodes():
            if tag != "equal":
                out.append(f"obligation {tag}: \"{' '.join(old['obligation'].split()[a0:a1])}\" -> \"{' '.join(new['obligation'].split()[b0:b1])}\"")
    return out or ["no textual change"]


def impact_rules(conn: Connection) -> list[dict]:
    rows = conn.execute(text("SELECT id, version, status, title, effective_from, card FROM rule_cards WHERE tenant_id=:t ORDER BY id, version DESC"), {"t": _t()}).all()
    seen, out = set(), []
    for r in rows:
        if r.status in ("rejected", "retired"):
            continue
        prev = next((x.version for x in rows if x.id == r.id and x.version < r.version), None)
        out.append({"rule_id": r.id, "version": r.version, "title": r.title, "status": r.status, "effective_from": r.effective_from.isoformat(), "previous_version": prev,
                    "affected_count": None})
    return out


def impact(conn: Connection, rule_id: str, version: int | None, *, suggest: bool = False, llm: bool = False) -> dict | None:
    q = "SELECT * FROM rule_cards WHERE tenant_id=:t AND id=:i" + (" AND version=:v" if version else "") + " ORDER BY version DESC LIMIT 1"
    row = conn.execute(text(q), {"t": _t(), "i": rule_id, "v": version}).first()
    if not row:
        return None
    card = row.card
    card = {**card, "status": row.status}
    prev = conn.execute(text("SELECT * FROM rule_cards WHERE tenant_id=:t AND id=:i AND version<:v ORDER BY version DESC LIMIT 1"), {"t": _t(), "i": rule_id, "v": row.version}).first()
    kws = _rule_keywords(card)
    if not pipeline.doc_applicable(card):
        src = card["source"]
        return {"rule": {"id": card["id"], "version": row.version, "title": row.title, "status": row.status, "effective_from": card["effective_from"], "obligation": card["obligation"],
                         "source": {"document": src.get("document"), "reference": src.get("reference"), "quote": (src.get("quotes") or [""])[0]}},
                "previous": None, "dry_run": row.status != "active", "affected": [], "scanned_documents": 0,
                "note": "This rule governs live customer interactions (screens, chat, calls), not proposal or contract text, so it is not applied to the document library."}
    tier_a = card["check"].get("tier") in ("A", "A+B") and card["id"] in engine.runner.PREDICATES
    as_of = loader.as_of_date()
    affected, scanned = [], 0
    owners_tasks = {(str(t.document_id)): t for t in conn.execute(text("SELECT * FROM impact_tasks WHERE tenant_id=:t AND rule_id=:r AND rule_version=:v"), {"t": _t(), "r": rule_id, "v": row.version}).all()}
    for d in conn.execute(text("SELECT id, title, owner FROM sales_documents WHERE tenant_id=:t ORDER BY title"), {"t": _t()}).all():
        v = conn.execute(text("SELECT id, version, content FROM document_versions WHERE document_id=:d ORDER BY version DESC LIMIT 1"), {"d": d.id}).first()
        if not v:
            continue
        scanned += 1
        for c in segment(v.content):
            low = c.text.lower()
            matched = [k for k in kws if k in low]
            verdict = None
            if tier_a:
                facts = pipeline._clause_facts(c.text)
                vs = engine.run_checks(c.text, facts, [card], as_of=as_of, rule_ids=[card["id"]]) if facts else []
                verdict = vs[0] if vs else None
                hit = bool(verdict and (verdict["verdict"] == "fail" or (verdict["verdict"] == "review" and verdict.get("quote"))))
            else:
                need = 2 if len(kws) >= 3 else 1          # a lone generic keyword is not enough to call a clause affected
                hit = len(matched) >= need
            if not hit:
                continue
            quote = (verdict or {}).get("quote") or c.text
            if verdict and verdict["verdict"] == "fail":
                status, reason = "contradiction", f"Clause breaches this rule: {verdict['reason']}"
            elif verdict:
                status, reason = "review", f"Clause touches this rule and needs a reviewer: {verdict['reason']}"
            else:
                status, reason = "review", f"Clause mentions {', '.join(repr(m) for m in matched)}, which this rule governs. Compare it with the requirement below."
            old_ver = _old_verdict(prev, c, as_of) if prev else None
            note = f"{c.locator} in \"{d.title}\": check against {card['id']} v{row.version}. Requirement: {card['obligation'][:240]}"
            if old_ver and old_ver != (verdict or {}).get("verdict"):
                note += f" (under v{prev.version} this clause was '{old_ver}')"
            t = owners_tasks.get(str(d.id))
            affected.append({"document_id": str(d.id), "title": d.title, "owner": d.owner, "version": v.version, "clause_locator": c.locator, "quote": quote, "status": status,
                             "reason": reason, "matched_on": matched or [card["check"]["type"]], "change_note": note, "proposed_wording": None,
                             "task": {"owner": d.owner, "title": f"Update {c.locator} of \"{d.title}\" for {card['id']} v{row.version}", "state": t.state if t else "open", "persisted": bool(t)}})
    if suggest and affected:
        from niyam.judge import fixer
        from niyam.llm import router as llm
        if llm.configured():
            for x in affected[:3]:
                try:
                    r = fixer.suggest(x["quote"], card, pipeline._clause_facts(x["quote"]), x["quote"], as_of)
                    if r.get("proposed"):
                        x["proposed_wording"] = r["suggestion"]
                except llm.LLMUnavailable:
                    break
    src = card["source"]
    return {"rule": {"id": card["id"], "version": row.version, "title": row.title, "status": row.status, "effective_from": card["effective_from"], "obligation": card["obligation"],
                     "source": {"document": src.get("document"), "reference": src.get("reference"), "quote": (src.get("quotes") or [""])[0]}},
            "previous": ({"version": prev.version, "status": prev.status, "effective_from": prev.effective_from.isoformat(), "obligation": prev.card["obligation"],
                          "changes": _changes(prev.card, card)} if prev else None),
            "dry_run": row.status != "active", "affected": affected, "scanned_documents": scanned}


def _old_verdict(prev, c, as_of):
    if prev.card["id"] not in engine.runner.PREDICATES:
        return None
    facts = pipeline._clause_facts(c.text)
    vs = engine.run_checks(c.text, facts, [prev.card], as_of=as_of, rule_ids=[prev.card["id"]]) if facts else []
    return vs[0]["verdict"] if vs else None
