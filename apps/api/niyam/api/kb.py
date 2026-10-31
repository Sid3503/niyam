from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from niyam.api.deps import require_key
from niyam.config import get_settings
from niyam.db.session import tx
from niyam.kb.search import search as kb_search
from niyam.rules.loader import as_of_date

router = APIRouter(prefix="/kb", tags=["knowledge-base"], dependencies=[Depends(require_key)])
KINDS = {"regulation", "surface"}


def _uuid(v: str) -> uuid.UUID:
    try:
        return uuid.UUID(v)
    except ValueError:
        raise HTTPException(404, detail={"code": "not_found", "message": "unknown id"})


def _doc(r) -> dict:
    return {"id": str(r.id), "title": r.title, "regulator": r.regulator, "doc_type": r.doc_type, "reference_no": r.reference_no,
            "issue_date": r.issue_date.isoformat() if r.issue_date else None, "status": r.status, "provenance": r.provenance,
            "text_basis": r.text_basis, "pages": r.pages, "units": r.unit_count, "file": r.file_path, "sha256": r.sha256,
            "corpus_kind": r.corpus_kind, "extraction_status": r.extraction_status, "extraction_note": r.extraction_note,
            "source_url": r.source_url}


@router.get("/stats")
def stats() -> dict:
    t = get_settings().tenant_id
    with tx() as c:
        q = lambda sql: c.execute(text(sql), {"t": t}).all()  # noqa: E731
        docs = q("SELECT corpus_kind, count(*) n, coalesce(sum(unit_count),0) u FROM documents WHERE tenant_id=:t GROUP BY 1")
        reg = q("SELECT regulator, count(*) FROM documents WHERE tenant_id=:t AND corpus_kind='regulation' GROUP BY 1 ORDER BY 2 DESC")
        prov = q("SELECT provenance, count(*) FROM documents WHERE tenant_id=:t AND corpus_kind='regulation' GROUP BY 1 ORDER BY 2 DESC")
        ext = q("SELECT extraction_status, count(*) FROM documents WHERE tenant_id=:t GROUP BY 1")
        last = c.execute(text("SELECT max(finished_at) FROM ingest_runs WHERE tenant_id=:t"), {"t": t}).scalar()
    by = {r.corpus_kind: r for r in docs}
    return {
        "documents": by["regulation"].n if "regulation" in by else 0, "units": int(by["regulation"].u) if "regulation" in by else 0,
        "surface_documents": by["surface"].n if "surface" in by else 0, "surface_units": int(by["surface"].u) if "surface" in by else 0,
        "by_regulator": {r[0]: r[1] for r in reg}, "by_provenance": {r[0]: r[1] for r in prov},
        "by_extraction_status": {r[0]: r[1] for r in ext}, "indexed_at": last.isoformat() if last else None,
    }


@router.get("/documents")
def documents(regulator: str | None = None, status: str | None = None, doc_type: str | None = None, provenance: str | None = None,
              q: str | None = Query(default=None, max_length=200), corpus_kind: str = "regulation", limit: int = Query(500, ge=1, le=1000)) -> list[dict]:
    if corpus_kind not in KINDS:
        raise HTTPException(422, detail={"code": "bad_request", "message": "corpus_kind must be regulation|surface"})
    where, p = ["tenant_id=:t", "corpus_kind=:k"], {"t": get_settings().tenant_id, "k": corpus_kind, "lim": limit}
    for col, val in (("regulator", regulator), ("status", status), ("doc_type", doc_type), ("provenance", provenance)):
        if val:
            where.append(f"lower({col}) = lower(:{col})"); p[col] = val
    if q:
        where.append("(title ILIKE :q OR coalesce(reference_no,'') ILIKE :q OR file_path ILIKE :q)"); p["q"] = f"%{q}%"
    with tx() as c:
        rows = c.execute(text(f"SELECT * FROM documents WHERE {' AND '.join(where)} ORDER BY regulator, issue_date DESC NULLS LAST, title LIMIT :lim"), p).all()
    return [_doc(r) for r in rows]


@router.get("/documents/{doc_id}")
def document(doc_id: str) -> dict:
    did = _uuid(doc_id)
    with tx() as c:
        d = c.execute(text("SELECT * FROM documents WHERE id=:i AND tenant_id=:t"), {"i": did, "t": get_settings().tenant_id}).first()
        if not d:
            raise HTTPException(404, detail={"code": "not_found", "message": "document not found"})
        heads = c.execute(text("SELECT id, text, page, locator FROM units WHERE document_id=:i AND kind='heading' ORDER BY ordinal LIMIT 400"), {"i": did}).all()
    outline = []
    for h in heads:
        lv = h.locator.count(".") + 1 if h.locator and h.locator.startswith("para ") else 1
        outline.append({"heading": h.text[:160], "level": min(lv, 4), "page": h.page, "unit_id": str(h.id)})
    return {**_doc(d), "outline": outline}


@router.get("/search")
def search(q: str = Query(min_length=2, max_length=300), regulator: str | None = None, doc_type: str | None = None,
           status: str | None = None, corpus_kind: str = "regulation", as_of: dt.date | None = None, kind: str | None = None,
           document_id: str | None = None, limit: int = Query(10, ge=1, le=50)) -> dict:
    if corpus_kind not in KINDS:
        raise HTTPException(422, detail={"code": "bad_request", "message": "corpus_kind must be regulation|surface"})
    with tx() as c:
        return kb_search(c, q, regulator=regulator, doc_type=doc_type, status=status, corpus_kind=corpus_kind, as_of=as_of,
                         kind=kind, doc_id=document_id, limit=limit)


@router.get("/units/{unit_id}")
def unit(unit_id: str, context: int = Query(1, ge=0, le=5)) -> dict:
    uid = _uuid(unit_id)
    with tx() as c:
        u = c.execute(text("SELECT u.*, d.title, d.regulator, d.status AS doc_status, d.provenance, d.text_basis, d.file_path, d.reference_no "
                           "FROM units u JOIN documents d ON d.id=u.document_id WHERE u.id=:i AND u.tenant_id=:t"),
                      {"i": uid, "t": get_settings().tenant_id}).first()
        if not u:
            raise HTTPException(404, detail={"code": "not_found", "message": "unit not found"})
        nb = c.execute(text("SELECT id, ordinal, kind, locator, text FROM units WHERE document_id=:d AND ordinal BETWEEN :a AND :b AND ordinal<>:o ORDER BY ordinal"),
                       {"d": u.document_id, "a": u.ordinal - context, "b": u.ordinal + context, "o": u.ordinal}).all()
    f = lambda r: {"unit_id": str(r.id), "id": str(r.id), "kind": r.kind, "locator": r.locator, "text": r.text}  # noqa: E731
    return {
        "unit_id": str(u.id), "id": str(u.id), "document_id": str(u.document_id), "document_title": u.title, "regulator": u.regulator,
        "doc_status": u.doc_status, "provenance": u.provenance, "text_basis": u.text_basis, "file": u.file_path, "reference_no": u.reference_no,
        "page": u.page, "locator": u.locator, "heading_path": u.heading_path, "kind": u.kind, "ordinal": u.ordinal, "text": u.text,
        "text_sha256": u.text_sha256, "prev": [f(r) for r in nb if r.ordinal < u.ordinal], "next": [f(r) for r in nb if r.ordinal > u.ordinal],
    }
