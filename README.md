# Niyam

**Proposals and brochures stop shipping claims that are out of date, and you can see when a fix is approved.**

Niyam is a sales-ops teammate for Indian payments and lending companies. When a new RBI or NPCI circular lands, it checks every customer-facing document (proposals, agreements, brochures, order forms, pitch decks, voice notes) against cited rules and your approved product terms, shows the exact sentence that is out of date, drafts the corrected wording, and tracks the fix from *drafted* to *approved by a named person*. The original file is never changed.

> Decision support, not legal advice. All demo documents and Paytm product facts in this repository are **synthetic**.

## What it does

```
circular → rule approved → library scanned → fix drafted → named approver signs → re-test → evidence
```

- **Scan**: clause-level review of a document library. Findings are `current`, `outdated`, `missing`, `contradiction` or `review`, each with a verbatim quote and the rule or product fact behind it.
- **Rules from a circular**: upload a PDF/DOCX/TXT (or pick a knowledge-base document); a language model drafts rule cards whose quotes are verified verbatim against the source. Nothing is active until a named person approves it.
- **PDF workbench**: apply approved wording to a *copy* of a PDF on the server (the old text is truly removed, never just covered), preview, then commit as version N+1. A commit whose extracted text still contains the stale sentence is refused (`409 stale_text_remains`). Wording that cannot fit is refused rather than hidden.
- **Voice notes**: spoken promises are transcribed and checked by the same rules (demo audio is synthetic; recorded notes only, not live calls).
- **Evidence**: SHA-256 of the original and current file, approvals with names and times, re-tests, a tamper-evident hash-chained audit log, and a downloadable PDF pack.

## Repository layout

| Path | What is there |
| --- | --- |
| `apps/api/` | FastAPI + Postgres: knowledge base, rule cards, deterministic Tier A engine, Tier B language-model judge, document review, PDF workbench, voice check |
| `apps/web/` | React 19 + Vite + TypeScript console and the public landing page |
| `rules/` | Rule cards (`cards/*.json`), product facts (`product-facts.json`, synthetic) and the card validator |
| `library/` | Synthetic demo documents (PDF and text) and synthetic demo voice clips |
| `regulations/` | Manifests of source documents, plus only the source files the rule cards cite (see below) |
| `docs/` | Product, contract and architecture documents. Start with `docs/README.md` |
| `tools/` | `reset_demo.sh`, `seed_demo.py`, `make_demo_pdfs.py` |
| `infra/` | Docker Compose and `.env.example` |
| `render.yaml`, `Dockerfile` | One-service Render deploy (API + console + disk). See `docs/RENDER.md` |
| `niyam-web/` | The earlier console prototype, kept for reference |

## Run it (host development)

Requires Python 3.12+, Node 20+, and a Postgres 16 with `pg_trgm`.

```bash
# 1. configuration (never commit infra/.env)
cp infra/.env.example infra/.env        # set POSTGRES_PASSWORD; add OLLAMA_API_KEY and/or SARVAM_API_KEY for AI features

# 2. database (any Postgres 16; this uses the compose service without pgvector)
docker compose -f infra/docker-compose.yml -f infra/docker-compose.nopgvector.yml --env-file infra/.env up -d db

# 3. API
cd apps/api && python3 -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'
set -a; . ../../infra/.env; set +a
export NIYAM_DATABASE_URL="postgresql+psycopg://niyam:${POSTGRES_PASSWORD}@127.0.0.1:5433/niyam" NIYAM_DATA_ROOT="$(cd ../.. && pwd)" PYTHONPATH=.
alembic upgrade head
python -m niyam.kb.ingest               # builds the knowledge base from whatever is in regulations/
uvicorn niyam.main:app --port 8000      # OpenAPI at /api/docs

# 4. web console (second terminal)
cd apps/web && npm install && npm run dev      # http://localhost:5173
```

Load the sales demo: `tools/reset_demo.sh && python3 tools/seed_demo.py`. Start over any time with `tools/reset_demo.sh`.

## Deploy on Render

The API is a long-running FastAPI process (PDF preview in memory, local blob files, PyMuPDF). Host it as **one Docker web service** that also serves the built console. Blueprint: `render.yaml`. Steps, env vars, seeding, and cost notes: **`docs/RENDER.md`**.

You will need a paid web instance (the free web plan has no persistent disk and sleeps) plus a small Postgres. Create **fresh** Sarvam / Ollama / `NIYAM_API_KEY` values before you paste them into the dashboard.

AI features: the language model is Ollama (`gpt-oss:120b`) when `OLLAMA_API_KEY` is set, otherwise Sarvam. Speech-to-text for voice notes always needs `SARVAM_API_KEY`. Without keys the deterministic checks still run and AI-drafted wording and voice are off.

## Tests

```bash
cd apps/api && python -m pytest -q --ignore=tests/engine                                   # needs the database above
cd apps/api && PYTHONPATH=. python -m pytest tests/engine --confcutdir=tests/engine -q     # engine, no database
cd apps/web && npm test
```

`tests/test_api.py::test_all_cards_are_draft_and_quotes_verified` expects a freshly reset database (`tools/reset_demo.sh`).

## What is and is not in this repository

- **The regulatory corpus is not committed wholesale.** One source file alone is 138 MB (over GitHub's limit) and most documents belong to other organisations. The repo contains the manifests (`regulations/*/MANIFEST.csv`, with source URLs and hashes) and only the files the rule cards cite, so every card still verifies. The knowledge base is therefore small until you re-fetch documents from the manifests and run the ingest. `paytm-terms/` is likewise not committed.
- **Everything demo is synthetic**: documents, merchant names, fees, settlement terms and the approvers' names. The product facts in `rules/product-facts.json` stand in for records only a real company could supply.
- **Rule cards are drafts until a named person approves them**, and several carry open issues noted in the card itself (for example paragraph numbers that must be confirmed against the page). Treat the rule set as a demonstration, not a validated compliance library.
- **Not built:** OCR of scanned PDFs, PII redaction and encryption of the evidence pack, live call monitoring, spoken read-back, and authentication beyond a static API key. The root `Dockerfile` (Render) was not built on the author's machine (local Docker pulls are blocked by a TLS-inspecting proxy); Render builds in its own cloud.
- Document text and circular text are sent to a hosted language model (Ollama or Sarvam) for drafting and judging. Do not load real merchant or customer data without making a data decision first.

## License

No license has been chosen yet, so all rights are reserved by default. Add a `LICENSE` file before inviting reuse.
