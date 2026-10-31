"""Hybrid lexical retrieval over units: Postgres FTS (AND + OR forms) + trigram, fused by weighted RRF.

Why lexical-first: regulatory text is term-heavy ("T + 5", "cooling-off", "suo moto", "Beneficiary bank"), and every hit must
be a verbatim, citable unit. Dense vectors are an optional add-on that we adopt only if kb/eval.py shows lexical misses.
Retrieval is DISCOVERY only. It never produces a verdict; verdicts come from approved rule cards + the Tier A engine.

`snippet` is plain source text with <mark>..</mark> around matches and NO HTML escaping: clients must render it as text
(split on the markers), never inject it as HTML.
"""
from __future__ import annotations

import math
import re
import time
from datetime import date

from sqlalchemy import text
from sqlalchemy.engine import Connection

from niyam.config import get_settings

RRF_K = 60
W_AND, W_COV, W_TRGM, W_PHRASE = 1.0, 1.5, 0.35, 2.0
KIND_WEIGHT = {"heading": 0.45, "paragraph": 1.0, "list_item": 1.0, "table_row": 1.05}
CANDIDATES = 60
RARE_IDF = 3.0          # tokens at/above this idf (rare in the corpus) drive the OR candidate pool
MAX_TOKENS = 14
LEN_NORM = 0.0006       # mild preference for tighter units
# Obligation search should prefer binding instruments over assessments/reports/press (mild, tunable prior; see docs).
DOC_TYPE_PRIOR = {"act": 1.15, "rules": 1.15, "master_direction": 1.15, "circular": 1.15, "notification": 1.1, "regulations": 1.15,
                  "report": 0.9, "press_release": 0.85, "case": 0.95, "advisory": 1.0}
STOP = {"the", "a", "an", "of", "to", "in", "for", "and", "or", "is", "are", "be", "by", "on", "what", "which", "how", "does", "do", "shall", "must", "any", "with", "as", "at", "from", "that", "this", "when", "get", "many", "much", "can", "i", "my", "me", "it", "if", "than", "then", "there"}
# Small, deliberate domain synonym set: customer words -> regulator words. Extra terms count at SYN_WEIGHT of their idf.
SYNONYMS = {
    "refund": ["reversal", "reverse", "credit"],
    "refunded": ["reversal", "reverse"],
    "fails": ["failed", "debited", "uncredited"],
    "failed": ["debited", "uncredited", "unsuccessful"],
    "failure": ["failed", "debited"],
    "guaranteed": ["assured", "guarantee"],
    "guarantee": ["assured"],
    "cancel": ["exit", "cancellation"],
    "cancellation": ["exit"],
    "cheating": ["fraud", "misrepresentation"],
    "scam": ["fraud"],
}
SYN_WEIGHT = 0.5
_df_cache: dict[str, int] = {}
_n_cache: dict[str, int] = {}


def _df(conn: Connection, tok: str) -> int:
    if tok not in _df_cache:
        _df_cache[tok] = conn.execute(text("SELECT count(*) FROM units WHERE tsv @@ to_tsquery('english', :t)"), {"t": tok}).scalar() or 0
    return _df_cache[tok]


def _n_units(conn: Connection) -> int:
    if "n" not in _n_cache:
        _n_cache["n"] = conn.execute(text("SELECT count(*) FROM units")).scalar() or 1
    return _n_cache["n"]


def invalidate_caches() -> None:
    _df_cache.clear(); _n_cache.clear()


def _idf(conn: Connection, tok: str) -> float:
    n, df = _n_units(conn), _df(conn, tok)
    return math.log(1 + (n - df + 0.5) / (df + 0.5))


def _tokens(q: str) -> list[str]:
    toks = [t.lower() for t in re.findall(r"[A-Za-z0-9]+", q)]
    return [t for t in toks if t not in STOP and (len(t) > 1 or t.isdigit())]


def _or_query(q: str) -> str | None:
    toks = list(dict.fromkeys(_tokens(q)))
    return " | ".join(toks) if toks else None


def _filters(regulator, doc_type, status, corpus_kind, as_of, kind, doc_id) -> tuple[str, dict]:
    where = ["u.tenant_id = :tenant", "d.corpus_kind = :corpus_kind"]
    p: dict = {"tenant": get_settings().tenant_id, "corpus_kind": corpus_kind}
    if regulator:
        where.append("lower(d.regulator) = lower(:regulator)"); p["regulator"] = regulator
    if doc_type:
        where.append("d.doc_type = :doc_type"); p["doc_type"] = doc_type
    if status:
        where.append("d.status = :status"); p["status"] = status
    if as_of:
        where.append("(d.issue_date IS NULL OR d.issue_date <= :as_of)"); p["as_of"] = as_of
    if kind:
        where.append("u.kind = :kind"); p["kind"] = kind
    if doc_id:
        where.append("u.document_id = :doc_id"); p["doc_id"] = doc_id
    return " AND ".join(where), p


def search(
    conn: Connection,
    q: str,
    *,
    regulator: str | None = None,
    doc_type: str | None = None,
    status: str | None = None,
    corpus_kind: str = "regulation",
    as_of: date | None = None,
    kind: str | None = None,
    doc_id: str | None = None,
    limit: int = 10,
) -> dict:
    t0 = time.perf_counter()
    q = (q or "").strip()
    if not q:
        return {"query": q, "took_ms": 0, "hits": []}
    where, params = _filters(regulator, doc_type, status, corpus_kind, as_of, kind, doc_id)
    params.update(q=q, cand=CANDIDATES)
    base_toks = list(dict.fromkeys(_tokens(q)))[:MAX_TOKENS]
    weights: dict[str, float] = {t: _idf(conn, t) for t in base_toks}
    for t in base_toks:
        for syn in SYNONYMS.get(t, []):
            if syn not in weights:
                weights[syn] = SYN_WEIGHT * _idf(conn, syn)
    toks = list(weights)[: MAX_TOKENS + 6]
    orq = " | ".join(base_toks) if base_toks else None
    params["orq"] = orq or ""
    rare = [t for t in toks if weights[t] >= RARE_IDF]
    pool: dict = {}
    ranked: dict[str, list] = {}

    and_sql = f"""SELECT u.id FROM units u JOIN documents d ON d.id = u.document_id
                  WHERE {where} AND u.tsv @@ websearch_to_tsquery('english', :q)
                  ORDER BY ts_rank_cd(u.tsv, websearch_to_tsquery('english', :q), 32) DESC LIMIT :cand"""
    ranked["and"] = [r.id for r in conn.execute(text(and_sql), params)]
    if rare or toks:
        use = rare or toks
        params["rareq"] = " | ".join(use)
        rare_sql = f"""SELECT u.id FROM units u JOIN documents d ON d.id = u.document_id
                       WHERE {where} AND u.tsv @@ to_tsquery('english', :rareq)
                       ORDER BY ts_rank_cd(u.tsv, to_tsquery('english', :rareq), 32) DESC LIMIT 150"""
        ranked["rare"] = [r.id for r in conn.execute(text(rare_sql), params)]
    conn.execute(text("SET LOCAL pg_trgm.word_similarity_threshold = 0.5"))
    trg_sql = f"""SELECT u.id FROM units u JOIN documents d ON d.id = u.document_id
                  WHERE {where} AND :q <% u.text ORDER BY word_similarity(:q, u.text) DESC LIMIT 40"""
    ranked["trgm"] = [r.id for r in conn.execute(text(trg_sql), params)]
    if len(q) >= 12:   # verbatim phrase lookup (quote search)
        ph_sql = f"""SELECT u.id FROM units u JOIN documents d ON d.id = u.document_id
                     WHERE {where} AND u.text ILIKE :ph LIMIT 20"""
        ranked["phrase"] = [r.id for r in conn.execute(text(ph_sql), {**params, "ph": "%" + q.replace("%", "").replace("_", "") + "%"})]
    for lst in ranked.values():
        for i in lst:
            pool[i] = True
    if not pool:
        return {"query": q, "took_ms": round((time.perf_counter() - t0) * 1000), "hits": []}

    # IDF-weighted coverage of the pool: sum of idf for each query term the unit contains, mildly length-normalised
    cases, cp = [], {"ids": list(pool)}
    for n, t in enumerate(toks):
        cases.append(f"CASE WHEN u.tsv @@ to_tsquery('english', :t{n}) THEN {weights[t]:.6f} ELSE 0 END")
        cp[f"t{n}"] = t
    cov_rows = conn.execute(text(f"SELECT u.id, u.kind, u.char_count, d.doc_type, ({' + '.join(cases) or '0'}) AS cov FROM units u JOIN documents d ON d.id = u.document_id WHERE u.id = ANY(:ids)"), cp).all()
    cov = {r.id: (float(r.cov) / (1 + LEN_NORM * r.char_count)) * KIND_WEIGHT.get(r.kind, 1.0) * DOC_TYPE_PRIOR.get(r.doc_type, 1.0) for r in cov_rows}
    ranked["cov"] = [i for i, _ in sorted(cov.items(), key=lambda kv: kv[1], reverse=True)[:150]]
    kinds = {r.id: r.kind for r in cov_rows}

    fused: dict = {}
    for name, w in (("and", W_AND), ("cov", W_COV), ("trgm", W_TRGM), ("phrase", W_PHRASE)):
        for rank, uid in enumerate(ranked.get(name, []), 1):
            fused[uid] = fused.get(uid, 0.0) + w * KIND_WEIGHT.get(kinds.get(uid, "paragraph"), 1.0) / (RRF_K + rank)
    top = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[: limit * 3]   # over-fetch; identical units from duplicate copies collapse below
    if not top:
        return {"query": q, "took_ms": round((time.perf_counter() - t0) * 1000), "hits": []}
    ids = [i for i, _ in top]
    hl_query = "to_tsquery('english', :orq)" if orq else "websearch_to_tsquery('english', :q)"
    rows = conn.execute(
        text(
            f"""SELECT u.id, u.document_id, u.ordinal, u.page, u.kind, u.locator, u.heading_path, u.text,
                       ts_headline('english', u.text, {hl_query},
                                   'StartSel=⟦,StopSel=⟧,MaxWords=45,MinWords=18,ShortWord=2,MaxFragments=1') AS hl,
                       d.title, d.regulator, d.status AS doc_status, d.provenance, d.text_basis, d.reference_no,
                       d.issue_date, d.file_path, d.doc_type, d.corpus_kind, u.text_sha256
                FROM units u JOIN documents d ON d.id = u.document_id
                WHERE u.id = ANY(:ids)"""
        ),
        {"ids": ids, "orq": orq or "", "q": q},
    ).all()
    by_id = {r.id: r for r in rows}
    hits = []
    seen: dict[str, dict] = {}
    for uid, score in top:
        r = by_id.get(uid)
        if not r:
            continue
        if r.text_sha256 in seen:                      # same text in another copy of the document: collapse, but say where else it is
            seen[r.text_sha256].setdefault("also_in", []).append(r.file_path)
            continue
        snippet = r.hl.replace("⟦", "<mark>").replace("⟧", "</mark>")
        hits.append(
            {
                "unit_id": str(r.id), "document_id": str(r.document_id), "document_title": r.title, "regulator": r.regulator,
                "doc_type": r.doc_type, "doc_status": r.doc_status, "provenance": r.provenance, "text_basis": r.text_basis,
                "reference_no": r.reference_no, "issue_date": r.issue_date.isoformat() if r.issue_date else None,
                "file": r.file_path, "page": r.page, "locator": r.locator, "heading_path": r.heading_path, "kind": r.kind,
                "corpus_kind": r.corpus_kind, "ordinal": r.ordinal, "text": r.text, "snippet": snippet, "score": round(score * 1000, 3),
            }
        )
        seen[r.text_sha256] = hits[-1]
        if len(hits) >= limit:
            break
    return {"query": q, "took_ms": round((time.perf_counter() - t0) * 1000), "hits": hits}
