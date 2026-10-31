"""PDF workbench: apply approved/suggested wording onto a COPY, preview, and commit as version N+1.

Fail-closed gate (docs/NIYAM-PDF-WORKBENCH.md section 4): after the edit the new PDF is re-extracted; if any edited finding's old quote is still a
substring of the extracted text the commit is rejected (stale_text_remains). The engine, not this module, decides which findings are resolved.
The original version's bytes are never touched: a commit always inserts a new version row.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

from niyam.db import audit
from niyam.review import blobs, pdfio, pipeline, service
from niyam.rules import loader

_PREVIEWS: dict[str, tuple[str, bytes, float]] = {}
TTL = 600


def _gc():
    now = time.time()
    for k in [k for k, v in _PREVIEWS.items() if now - v[2] > TTL]:
        _PREVIEWS.pop(k, None)
    while len(_PREVIEWS) > 20:
        _PREVIEWS.pop(next(iter(_PREVIEWS)))


def preview_bytes(doc_id: str, token: str) -> bytes | None:
    _gc()
    x = _PREVIEWS.get(token)
    return x[1] if x and x[0] == doc_id else None


class NotPdf(Exception):
    pass


class BadEdit(Exception):
    def __init__(self, msg: str):
        super().__init__(msg)
        self.msg = msg


class WordingTooLong(Exception):
    def __init__(self, finding_id: str, locator: str, page, new_len: int, old_len: int):
        super().__init__(finding_id)
        self.finding_id, self.locator, self.page, self.new_len, self.old_len = finding_id, locator, page, new_len, old_len


@dataclass
class _Ns:
    content: str
    doc_type: str
    merchant: str | None
    doc_id: uuid.UUID
    title: str


def apply(conn: Connection, did: uuid.UUID, edits: list[dict], commit: bool, actor: str) -> dict:
    v = conn.execute(text("""SELECT v.*, d.title, d.doc_type, d.merchant FROM document_versions v JOIN sales_documents d ON d.id=v.document_id
                             WHERE v.document_id=:d ORDER BY v.version DESC LIMIT 1"""), {"d": did}).first()
    if not v:
        return None
    if v.content_type != "application/pdf" or not v.blob_key:
        raise NotPdf()
    if not edits:
        raise BadEdit("no edits supplied")
    rev = conn.execute(text("SELECT id FROM doc_reviews WHERE version_id=:v ORDER BY reviewed_at DESC LIMIT 1"), {"v": v.id}).scalar()
    if rev is None:
        pipeline.review_version(conn, v.id, "workbench", actor=actor)
        rev = conn.execute(text("SELECT id FROM doc_reviews WHERE version_id=:v ORDER BY reviewed_at DESC LIMIT 1"), {"v": v.id}).scalar()
    before = service.findings_for_review(conn, rev)
    by_id = {f["id"]: f for f in before}
    data = blobs.get(v.blob_key)
    ex = pdfio.Extracted(v.content, v.page_map or [], (v.media or {}).get("page_sizes", []), (v.media or {}).get("pages", 0))
    pe: list[pdfio.Edit] = []
    for e in edits:
        f = by_id.get(str(e.get("finding_id")))
        w = str(e.get("wording") or "").strip()
        if not f:
            raise BadEdit(f"finding {e.get('finding_id')} is not in the latest review of this version")
        if not w or len(w) > 2000:
            raise BadEdit("wording must be 1-2000 characters")
        if f["status"] == "current":
            raise BadEdit("a finding with status 'current' needs no edit")
        pe.append(pdfio.Edit(f["id"], w, f["quote"], f["page"], f["bbox"], tuple(f["span"]) if f["span"] else None))
    try:
        new_bytes, strategy = pdfio.apply_edits(data, ex, pe)
    except pdfio.WordingDoesNotFit as e:
        f = by_id.get(e.finding_id) or {}
        w = next((x for x in pe if x.finding_id == e.finding_id), None)
        raise WordingTooLong(e.finding_id, f.get("locator", ""), f.get("page"), len(w.wording) if w else 0, len(f.get("quote") or "")) from e
    new = pdfio.extract(new_bytes)
    stale = [{"finding_id": p.finding_id, "quote": p.quote} for p in pe if p.quote and pdfio.stale(p.quote, new.content)]
    sha_before = v.sha256
    import hashlib
    sha_after = hashlib.sha256(new_bytes).hexdigest()

    rows = pipeline.active_cards(conn)
    ns = _Ns(new.content, v.doc_type, v.merchant, did, v.title)
    after_f, _ = pipeline.compute_findings(conn, ns, rows, loader.as_of_date())
    bsig = {service._sig(f): f for f in before if f["status"] != "current"}
    asig = {service._sig(f) for f in after_f if f["status"] != "current"}
    resolved = [bsig[k]["id"] for k in bsig if k not in asig]
    remaining = [bsig[k]["id"] for k in bsig if k in asig]
    n_new = [f"preview:{i}" for i, k in enumerate([service._sig(f) for f in after_f if f["status"] != "current"]) if k not in bsig]
    cmp_ = {"before": service._summ(before), "after": service._summ(after_f), "resolved": resolved, "remaining": remaining, "new": n_new}
    out = {"committed": False, "strategy": strategy, "stale_text_remains": stale, "sha256_before": sha_before, "sha256_after": sha_after,
           "comparison": cmp_, "preview_url": None, "document": None}
    if not commit:
        token = uuid.uuid4().hex
        _gc()
        _PREVIEWS[token] = (str(did), new_bytes, time.time())
        out["preview_url"] = f"/api/v1/documents/{did}/preview.pdf?token={token}"
        return out
    if stale:
        return out                                             # the API turns this into 409 stale_text_remains
    vid, num, _ = service.add_pdf_version(conn, did, new_bytes, "workbench", actor, None, new)
    pipeline.review_version(conn, vid, "workbench", actor=actor)
    after_rev = conn.execute(text("SELECT id FROM doc_reviews WHERE version_id=:v ORDER BY reviewed_at DESC LIMIT 1"), {"v": vid}).scalar()
    after_real = service.findings_for_review(conn, after_rev)
    asig_real = {service._sig(f): f for f in after_real if f["status"] != "current"}
    cmp_ = {"before": service._summ(before), "after": service._summ(after_real),
            "resolved": [bsig[k]["id"] for k in bsig if k not in asig_real], "remaining": [asig_real[k]["id"] for k in asig_real if k in bsig],
            "new": [asig_real[k]["id"] for k in asig_real if k not in bsig]}
    passed = cmp_["after"]["open"] == 0
    conn.execute(text("INSERT INTO retests (id, tenant_id, document_id, from_version, to_version, passed, before, after, actor) VALUES (:i,:t,:d,:f,:to,:p,CAST(:b AS jsonb),CAST(:a AS jsonb),:ac)"),
                 dict(i=uuid.uuid4(), t=service._t(), d=did, f=v.id, to=vid, p=passed, b=json.dumps(cmp_["before"]), a=json.dumps(cmp_["after"]), ac=actor))
    audit.append(conn, actor=actor, action="document.workbench_commit", object_type="document", object_id=str(did),
                 payload={"document_id": str(did), "from_version": v.version, "to_version": num, "sha256_before": sha_before, "sha256_after": sha_after,
                          "applied_finding_ids": [p.finding_id for p in pe], "strategy": strategy, "passed": passed, "before": cmp_["before"], "after": cmp_["after"]})
    out.update(committed=True, comparison=cmp_, document=service.document_detail(conn, did, vid))
    return out
