# Niyam API

FastAPI + Postgres. Knowledge base over the regulator corpus, rule-card store, Tier A check engine, audit log.

## Run it

**Docker (target setup)** — needs a Docker daemon that can pull `python:3.12-slim` and `pgvector/pgvector:pg16`:

```bash
cp infra/.env.example infra/.env      # set POSTGRES_PASSWORD (and NIYAM_API_KEY for anything non-local)
make up            # db + api (migrates on start)
make ingest        # build the knowledge base from regulations/ and paytm-terms/
make eval          # retrieval evaluation against tests/gold/kb_queries.jsonl
make test          # pytest inside the api container
make web-up        # adds the web console (profile "web")
```

**Host dev (what was used to build and test this)**

```bash
cd apps/api && python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'                                   # Python 3.12+ (3.14 verified)
# Postgres: any 16.x with pg_trgm. If pgvector/pgvector cannot be pulled (TLS-inspecting proxy), use the local override:
docker compose -f infra/docker-compose.yml -f infra/docker-compose.nopgvector.yml --env-file infra/.env up -d db
export NIYAM_DATABASE_URL=postgresql+psycopg://niyam:<password>@127.0.0.1:5433/niyam NIYAM_DATA_ROOT=<repo root> PYTHONPATH=.
alembic upgrade head && python -m niyam.kb.ingest && python -m niyam.kb.eval
uvicorn niyam.main:app --port 8000        # OpenAPI at /api/docs
python -m pytest
```

Scanned PDFs: `python tools/make_ocr_sidecars.py <regulations dir>` (macOS, Apple Vision) writes machine-read `_ocr/*.ocr.txt` sidecars; ingestion uses them and flags the document `text_basis=ocr`. On Linux use Tesseract and the same sidecar format.

## What is where

| Path | Role |
| --- | --- |
| `niyam/kb/extract.py` | PDF/HTML/MD/OCR -> blocks. Table rows become their own units (row-spans expanded, group labels carried) |
| `niyam/kb/units.py` | blocks -> citable units with locators ("para 10(i)"), stable ids and hashes |
| `niyam/kb/ingest.py` | idempotent ingest, sha256 de-dupe, manifest metadata, `--refresh-metadata` |
| `niyam/kb/search.py` | FTS + trigram + IDF-weighted coverage + exact-phrase, fused by weighted RRF; collapses duplicate copies |
| `niyam/kb/eval.py` | recall@k / MRR on a gold set |
| `niyam/rules/loader.py` | cards from `rules/cards` -> DB, validated with `rules/validate.py` against the KB's own extractor |
| `niyam/engine/` | deterministic Tier A engine (see `docs/ENGINE.md`) |
| `niyam/db/` | session, append-only hash-chained audit log |
| `migrations/` | Alembic. DB enforces: active card needs an approver and is immutable; audit log append-only |

## Design rules the code enforces

- Retrieval is discovery only. Verdicts come from rule cards + the engine, never from search.
- Paytm's T&Cs are `corpus_kind=surface` (statements to test) and are excluded from default search.
- Every API response about a rule shows its status; nothing is `active` until a named human approves it.
- Fail closed: `NIYAM_ENV=prod` refuses to start without `NIYAM_API_KEY`; the corpus mounts read-only; the container runs as non-root with a read-only filesystem.

## Retrieval quality (honest numbers)

33 hand-written queries, `tests/gold/kb_queries.jsonl`, 31 Oct 2026, 219 documents / ~125k units:

| Version | recall@1 | recall@10 | MRR |
| --- | --- | --- | --- |
| Postgres FTS + trigram only | 0.36 | 0.64 | 0.46 |
| + IDF-weighted coverage, rare-term pool, phrase lookup, synonyms | 0.55 | 0.88 | 0.68 |
| + dedupe, doc-type prior, one corrected expectation | 0.58 | 0.91 | 0.71 |

Caveats: the set is small; I corrected three expectations after seeing misses (the KFS rule is restated in three instruments; two phrases sat in the neighbouring unit), so treat it as a smoke test, not a benchmark. Known misses: `dpdp-notice`, `kyc-tipping` (a FATF report outranks the KYC Directions for "tipping off"), `trai-robo`. Dense embeddings are NOT added: build a larger, independently written gold set first and add them only if lexical misses persist.

## Known limits

- Docker image build/compose of `api` and `web` were **not verified here**: this machine's Docker daemon cannot pull images because a Fortinet TLS-inspection proxy's CA is not trusted. Fix the CA (not certificate verification), then run `make build`.
- PDF table extraction is imperfect (columns can garble); paragraph text is always kept alongside table rows.
- Hindi/Devanagari PDFs from RBI sometimes contain replacement glyphs in headers; English text is unaffected.
- One scanned PDF (OC 100B, 20 pages) has no OCR sidecar yet (image-heavy brand guidelines).
- No row-level security yet (tenant_id columns exist); no rate limiting; Tier B / Sarvam not wired (engine abstains to `review`).


## Revamp: document review (31 Oct 2026)

The product is now sold as "a circular becomes a reviewed redline pack" (see `docs/NIYAM-SALES-NARRATIVE.md`, `docs/REVAMP-CONTRACT.md` incl. the v0.3 addendum).

| Path | Role |
| --- | --- |
| `niyam/review/claims.py` | Tier A checks against Paytm-controlled product facts (`rules/product-facts.json`, **synthetic**) and required disclosures |
| `niyam/review/pipeline.py` | clauses -> findings (`compute_findings` is pure; `review_version` persists). Idempotent per rule fingerprint |
| `niyam/review/pdfio.py` | PDF text + page geometry; the writer (PyMuPDF **true redaction**, reflow, fail-closed) |
| `niyam/review/workbench.py` | apply / preview / commit as version N+1; `409 stale_text_remains` gate |
| `niyam/review/voice.py`, `niyam/llm/speech.py` | voice-note check: Sarvam speech-to-text (codemix for display, translate for the engine) |
| `niyam/llm/router.py`, `ollama.py`, `sarvam.py` | LLM provider: `NIYAM_LLM_PROVIDER=auto\|ollama\|sarvam`. Speech-to-text always needs `SARVAM_API_KEY` |
| `niyam/review/blobs.py` | content-addressed store for original PDF/audio bytes (object-store stand-in); path `NIYAM_BLOB_DIR` or `<data root>/var/blobs` |
| `tools/make_demo_pdfs.py`, `tools/reset_demo.sh` | render demo PDFs; reset the demo to its starting state |

Invariants: original bytes are immutable; whiteout is never the fix (a unit test proves it is caught); the engine, not the canvas, decides what is resolved; wording that cannot fit the page is refused rather than hidden.
Not built: OCR for scanned PDFs, PII redaction and encryption of the pack, live call streaming (V2), read-back (V3), Docker image builds (blocked by the TLS proxy), auth beyond a static key.
