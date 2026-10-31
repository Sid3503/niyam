# Niyam platform — build contract (v0)

Working rule: **everything lives under the repository root.** `_ref/` is a frozen snapshot of the earlier files, for reference only; never import from it at runtime and never edit it. Canonical data inputs: `regulations/` (incl. `_user-dropped/`), `paytm-terms/`, `rules/cards/`.

## Decisions (and why)

| Area | Choice | Why |
| --- | --- | --- |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, psycopg 3 | Matches `docs/NIYAM-END-TO-END.md` §10; best PDF/NLP ecosystem. Runs in Docker (host Python is 3.14: do not rely on it) |
| DB | Postgres 16 + pgvector image (`pgvector/pgvector:pg16`) | One store for rules, units, audit, FTS and (later) embeddings. No separate vector DB |
| KB retrieval | **Lexical first**: Postgres FTS + trigram, metadata filters, rank fusion; dense vectors are an optional, measured add-on | Legal text is term-heavy; we prove recall on a gold set before adding embeddings (Sarvam has no embeddings endpoint) |
| Hot path | Approved rule cards + deterministic Tier A engine, no retrieval, no network | Reproducible, fast, auditable |
| Cold path | KB search, cross-references, impact analysis | Discovery only, never a verdict |
| LLM | Sarvam `sarvam-105b` behind a provider interface; off unless `SARVAM_API_KEY` set; Tier B abstains to `review` when off | Secrets only in `.env` (git-ignored) |
| Web | React 19 + Vite + TypeScript + Tailwind v4, TanStack Query, React Router; served by nginx in Docker | Reuses the existing Niyam sidebar/tokens |
| Infra | Docker Compose: `db`, `api`, `web`; `infra/` holds compose + `.env.example`; Makefile targets | Demo/hackathon mandate: Compose only (no Redis/Kafka/K8s). Production split: [`NIYAM-PRODUCTION-ARCHITECTURE.md`](./NIYAM-PRODUCTION-ARCHITECTURE.md) |

## Layout

```
apps/api/            niyam/{config,main}.py  niyam/db  niyam/kb  niyam/rules  niyam/engine  niyam/api  tests/  migrations/
apps/web/            React console + Dockerfile + nginx.conf
infra/               docker-compose.yml  .env.example
Makefile
rules/cards/*.json   source of truth for rule cards (validated by rules/validate.py)
```

## Rule-card and verdict contracts

Cards: see `rules/README.md` and any file in `rules/cards/`. Statuses: draft | in_review | active | superseded | retired | rejected. **Every card is currently `draft`.** The console and API must show that plainly and must never present a draft as approved.

`enforceability` (computed, not stored): `live` if `effective_from <= as_of`, else `not_yet_enforceable`.

**Verdict object** (engine output and API output):

```json
{
  "rule_id": "RBI-TAT-UPI-MERCHANT",
  "rule_version": 1,
  "rule_status": "draft",
  "verdict": "fail",                 // pass | fail | review | not_applicable | not_yet_enforceable
  "tier": "A",
  "confidence": 1.0,
  "quote": "it will be back tonight",   // verbatim substring of the checked text, or null
  "span": [34, 58],                      // char offsets into the checked text, or null
  "reason": "plain-language reason",
  "checks": [{"name": "timeline", "result": "fail", "detail": "promised 0 days; allowed 5"}],
  "source": {"document": "...", "reference": "...", "locator": "Annex, UPI row 4b", "file": "regulations/...", "quote": "verbatim regulator quote"}
}
```

Invariants (from the product spec): every verdict names its rule and shows confidence; a `fail` carries a `quote` that is a verbatim substring of the input; **empty or missing evidence is `review`, never `pass`**; the engine never guesses which rule row applies (e.g. UPI transfer vs merchant) from thin evidence: it returns `review` with the reason; AI never activates a rule.

## Check input

```json
POST /api/v1/check
{
  "text": "…agent reply or sales message…",
  "facts": {                            // all optional
    "surface": "agent_chat|macro|script|screen|voice",
    "journey": "failed_payment|refund_status|complaint|loan_offer|sales|…",
    "transaction_type": "upi_transfer|upi_merchant|other",
    "delay_days": 2,
    "complaint_state": {"rejected": true, "unsatisfied": false, "days_without_reply": 31},
    "product": "UPI|digital lending|investment advice|…",
    "convenience_fee_shown": true,
    "language": "en|hi|hinglish"
  },
  "rule_ids": ["…"],                    // optional; default: all applicable
  "as_of": "2026-10-31"                 // optional
}
```

## API (v1)

| Method | Path | Returns |
| --- | --- | --- |
| GET | `/healthz`, `/readyz` | liveness / DB-ready |
| GET | `/api/v1/rules` | `[{id, version, title, status, severity, tier, check_type, effective_from, enforceability, regulator, source:{document,file,provenance,text_basis}, open_issues_count, aliases}]` |
| GET | `/api/v1/rules/{id}` | full card JSON + `validation:{ok, errors[], warnings[], quotes_verified}` |
| POST | `/api/v1/check` | `{run_id, created_at, summary:{pass,fail,review,not_applicable,not_yet_enforceable}, verdicts:[Verdict]}` |
| GET | `/api/v1/runs`, `/api/v1/runs/{id}` | history of checks (persisted) |
| GET | `/api/v1/kb/stats` | `{documents, units, by_regulator:{…}, by_provenance:{…}, indexed_at}` |
| GET | `/api/v1/kb/documents?regulator=&status=&q=` | `[{id, title, regulator, doc_type, reference_no, issue_date, status, provenance, text_basis, pages, units, file, sha256}]` |
| GET | `/api/v1/kb/documents/{id}` | document + outline of headings |
| GET | `/api/v1/kb/search?q=&regulator=&doc_type=&status=&as_of=&limit=10` | `{query, took_ms, hits:[{unit_id, document_id, document_title, regulator, doc_status, provenance, page, locator, kind, text, snippet, score}]}` (`snippet` marks matches with `<mark>`) |
| GET | `/api/v1/kb/units/{id}` | the unit + `prev`/`next` neighbours + document header |

Errors: `{"error": {"code": "...", "message": "..."}}`. Auth: optional `X-API-Key` (enforced only when `NIYAM_API_KEY` is set).

## Honest-labelling rules for every screen

- Show `draft` status on every rule/verdict. Show provenance badges (`official`, `official_html_extract`, `mirror`, `user_downloaded`) and `OCR` where `text_basis=ocr`.
- Show `not yet enforceable` with the effective date.
- Footer on every screen: "Decision support, not legal advice. Demo numbers are PayDemo/synthetic."
- Tokens/colours: `DESIGN.md` (warm taupe identity; green/amber/red only for compliance states).

---

## Status at 31 Oct 2026 (end of first build session)

| Piece | State |
| --- | --- |
| Corpus intake | 220 files -> 219 documents / ~125k units. 31 loose PDFs from the project root moved to `regulations/_user-dropped/` with a manifest (the Integrated Ombudsman Scheme 2026, KFS Annexes A-C, KYC Directions, FREE-AI PDF and others are now primary-source PDFs). 28 scanned PDFs read through OCR sidecars (machine-read, flagged `text_basis=ocr`). Two unidentified downloads were identified by OCR as MeitY advisories (26 Dec 2023, 15 Mar 2024). |
| Database | Postgres 16, Alembic migration `0001`. Enforced in the DB: `active` card needs an approver and is immutable; audit log is append-only and hash-chained; verdict confidence/span constraints. |
| Knowledge base | FTS + trigram + IDF coverage + phrase, weighted RRF, duplicate collapse. recall@10 0.91 / MRR 0.71 on a 33-query smoke set (see `apps/api/README.md` for caveats). Paytm T&Cs kept as `corpus_kind=surface`. |
| Rule cards | 10 draft cards synced and validated by the API against its own extractor: all 10 quotes verified. |
| API | `/healthz`, `/readyz`, rules, KB (stats, documents, search, units), check, runs. `/check` depends on `niyam.engine` (in progress). 23 backend tests pass. |
| Web console | Built (React/Vite/TS/Tailwind), 6 screens + settings, 6 vitest tests. Verified against the real API for Overview and Knowledge base (headless screenshots). Check / History not yet verified against the live engine. |
| Docker | Dockerfiles, compose, entrypoint, Makefile written. **Not built or run here**: the Docker daemon cannot pull images (Fortinet TLS inspection; its CA is not trusted). Everything above was run on the host against a local `postgres:16-alpine`. |
| Not started | Sarvam Tier B judge/rewrite (needs `SARVAM_API_KEY` and a provider module), Live Guard, fix/re-test/gate/evidence loop, MCP tool server, auth beyond a static API key, row-level security, rate limiting. |

Contract amendments made while building (the console already handles these):
- Search `snippet` is plain source text with `<mark>` markers and **no HTML escaping**: render as text, never inject as HTML. Hits also carry `text_basis`, `corpus_kind`, `also_in[]` (other files holding the same unit).
- Verdicts are enriched with `rule_title` and `source.provenance` / `source.text_basis`; `GET /runs` has `text_preview`; `GET /runs/{id}` returns `text` and `facts`; `GET /kb/documents/{id}` returns `outline[{heading, level, page, unit_id}]`; `/kb/units/{id}` neighbours use `unit_id`.
- `corpus_kind` (`regulation` default | `surface`) is a search/list parameter.
