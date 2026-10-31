# Niyam production architecture

**Status:** target architecture, **31 October 2026**. This is how chat, voice, tools, backend, data, and async work scale in production. The hackathon/demo stack stays Docker Compose with a single API process (`docs/PLATFORM-BUILD.md`, `docs/NIYAM-END-TO-END.md` §10). Production **splits the same Python package into entrypoints**; it does not replace `niyam.engine`.

**Sibling docs:** [`NIYAM-END-TO-END.md`](./NIYAM-END-TO-END.md) (product loop), [`PLATFORM-BUILD.md`](./PLATFORM-BUILD.md) (what is built), [`ENGINE.md`](./ENGINE.md) (Tier A), [`NIYAM-VOICE-AND-TOOLS.md`](./NIYAM-VOICE-AND-TOOLS.md) (voice topologies and vendor hyperparams), [`SARVAM-AI-LOGIC.md`](./SARVAM-AI-LOGIC.md) (models), [`REVAMP-CONTRACT.md`](./REVAMP-CONTRACT.md) (document-review API).

Niyam is a **compliance assurance layer**, not a consumer chatbot or collections product. Chat and voice in production are (1) the tenant agent under test or under Live Guard, (2) PayDemo, and (3) an optional console “ask the corpus” that retrieves citations and never issues a verdict.

---

## 0. Executive summary

One compliance brain. Two transports (chat SSE, voice WS). Three process classes (hot API, control API, workers). A fourth process for the voice relay. Postgres is the system of record. Tools run only in `/think`. Live Guard is after the draft and before TTS. The relay never decides policy.

```
Console (React) ──HTTPS──► API gateway (OIDC, rate limit, WAF)
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
     api-hot            api-control          voice-relay
     /check             CRUD, approvals      sticky WS
     /guard/check       enqueue jobs         PCM in/out
     /think (SSE)       evidence download    STT/TTS sockets
          │                   │                   │
          │                   ▼                   │
          │              Redis queue              │
          │              workers                  │
          │         ingest · DocAI · swarm        │
          │         Tier B · PDF evidence         │
          ▼                   ▼                   ▼
     Postgres 16 (primary + replica)     Object store (audio, PDFs, packs)
```

The durable asset is still the **versioned obligation graph plus labelled corpus**. Scaling is packaging around `niyam.engine` and `/guard/check`.

---

## 1. What is already true in the repo

| Piece | Today (`apps/api`) |
| --- | --- |
| Engine | Deterministic Tier A, stdlib, no network (`niyam.engine`). Guard is Tier A only. |
| Guard | `POST /api/v1/guard/check` — approve / fix / escalate inside a latency budget. |
| Check | `POST /api/v1/check` persists runs. |
| KB | Lexical FTS + trigram + RRF. Dense vectors deferred. |
| Audit | Append-only hash chain. Active cards need a named approver and are immutable. |
| LLM | `niyam.llm.sarvam` behind a provider; off unless `SARVAM_API_KEY` is set. |
| Infra | Compose: `db`, `api`, optional `web`. No Redis. `NIYAM_ENV=prod` refuses to start without `NIYAM_API_KEY`. |
| Missing | `/think`, voice sockets, RLS, OIDC, job workers, object store, turn durability. |

Hackathon constraint (Compose only, no Redis/Kafka/K8s) applies to the **demo**. This document is the **production** target after that.

---

## 2. Process classes

Same image, different entrypoints.

| Process | Holds | Scales on | Must not hold |
| --- | --- | --- | --- |
| **api-hot** | Tier A engine, compiled **active** cards, `/guard`, `/check`, `/think` | CPU / RPS | DocAI, swarm, PDF render, open mic sockets |
| **api-control** | library, rules, approvals, runs, evidence download | request volume | Live Guard’s 3 s budget |
| **voice-relay** | client WS + vendor STT/TTS WS, fillers, barge-in | concurrent **calls** (sticky) | tools, rule cards, LLM |
| **worker** | ingest, personas, attack, Tier B, cross-check, evidence pack | job concurrency + vendor RPM | HTTP to the browser |
| **paydemo** | mock tenant tools (refund, TAT, escalate) | isolated replica | Niyam’s judge |

```
uvicorn niyam.hot:app              # Guard / check / think
uvicorn niyam.main:app             # control plane (and, in dev, everything)
uvicorn niyam.voice.relay:app      # PCM pumps
arq niyam.workers.WorkerSettings   # jobs (Celery is an equivalent)
```

Demo Compose keeps one `api` service with all four. Production runs four services from `apps/api`.

Gateway routing:

- `/api/v1/guard`, `/api/v1/check`, `/api/v1/think` → api-hot
- `/api/v1/voice/ws/*` → voice-relay, **session affinity** on `session_id`
- everything else under `/api/v1` → api-control
- console static → `web`

---

## 3. Two paths, one rule graph

### 3.1 Hot path — Live Guard and `/check`

Customer-facing. p95 Guard ≤ **3 s**. Tier A target **&lt; 100 ms**.

```
draft text
  → sentence gate
  → engine.run_checks on active cards (in-process, no network, no LLM)
  → approve | replace with approved wording | safe handoff
  → (voice) TTS
  → Tier B async after the sentence (does not block)
```

Load cards from Postgres into memory on api-hot. Invalidate on `rule_version` / approval. Empty draft and empty tool trace stay `escalate` / `review`, never `pass`.

This is the function already in `niyam.api.guard`. Production keeps that contract.

### 3.2 Cold path — assurance loop

```
circular ingest → compile drafts → human activate → swarm
  → Tier A → Tier B (sarvam-105b) → second-vendor high-severity
  → fix draft → human approve → retest → gate → signed evidence
```

This is **jobs**, not request threads. Human approval is a **row** (`pending` → `approved` / `rejected` / `deferred`), not an in-memory LangGraph interrupt that dies with the process. LangGraph (or equivalent) may orchestrate job steps; every interrupt is a DB state the next worker can resume.

---

## 4. Chat

Three distinct chats. They do not share prompts or tool sets.

### 4.1 Tenant / PayDemo agent chat (under test or under Guard)

Same brain as voice: `POST /think` as OpenAI-shaped SSE.

- Tools bound by **closure** to `tenant_id` / `user_id` / `db`.
- `ChatSurface = chat`. No `end_conversation`.
- Disconnect **detaches**; the turn keeps running.
- After visible text is chosen: mutation receipts, then Live Guard, then stream.

Turn durability:

```
chat_turns (tenant_id, conversation_id, client_message_id UNIQUE)
status: accepted → running → background → completed | failed | cancelled
heartbeat_at, lease_until
```

Reattach = same `client_message_id` + `resume_after`. One live turn per conversation (409 if another is running). Event log in Redis (or Postgres NOTIFY in a single-worker deploy); Redis Streams when more than one think replica exists.

### 4.2 Console “ask the corpus”

`GET /kb/search` plus a short `sarvam-105b` answer with **unit citations**. Discovery only. **No tools. No verdicts.** Retrieval is never a judge (`PLATFORM-BUILD.md`).

### 4.3 Niyam does not ship a general consumer chat product.

---

## 5. Voice

Canonical production Guard path is **topology A (cascaded)** from [`NIYAM-VOICE-AND-TOOLS.md`](./NIYAM-VOICE-AND-TOOLS.md).

```
mic 16 kHz linear16
  → voice-relay  (bearer header + HMAC sig)
  → Saaras realtime WS   (saaras:v4, stream_type=fast)
  → POST /think          (sarvam-105b-conversations, reasoning_effort none)
  → Live Guard           (same function as /guard/check)
  → Bulbul WS            (config → text → flush, sentence chunks)
  → speaker
```

The relay is its own deployment. One replica owns N calls. It pumps bytes, injects fillers at 1.5 s, and forwards caption/barge-in events. It never parses a transcript to apply a rule.

`/think` and Guard stay on api-hot so **topology B** (Deepgram Voice Agent + BYO `open_ai` think) can call the same endpoint. Managed Sarvam Voice Agents (Samvaad) remain a **harness target**, not the Guard runtime.

**Voice harness** (Attack stage) is a **worker**, not the relay: persona line → Bulbul caller clip → tenant agent → Saaras verbatim → object store + `transcripts` + `tool_traces` → judge.

Vendors stay hyperparameters (`VOICE_TOPOLOGY`, `VOICE_STT_*`, `VOICE_TTS_*`, `VOICE_THINK_*`). Session mint 503s unless `agent_status() == ready`. Think URL+secret fail closed. Think URL is public if a cloud shell calls it.

---

## 6. Tool calling

| Who | Tools | Where they execute |
| --- | --- | --- |
| Tenant agent / PayDemo | refund, status, escalate, fee lookup, … | Tenant adapter inside `/think` |
| Niyam Compiler / Fixer | draft JSON only; no prod customer writes | worker |
| Niyam Judge / Guard / Tier A | none | — |
| STT / TTS / Deepgram / Samvaad | none for Niyam policy | — |

Rules:

1. Tool schemas live next to code; tool **policy** lives in prompts; `precedence` composed last.
2. `tenant_id` / `user_id` are never model-suppliable arguments.
3. Persist every invocation to `tool_traces` with idempotency `(tenant_id, session_id, tool_call_id, index)`.
4. Action tests read that table. `[]` means **unverified**.
5. If the model claimed a write and no tool ran, replace the line (receipt), then Guard the replacement.
6. Irreversible tools wait for end-of-turn and Guard pass. Deepgram `FunctionCallRequest` stays **off** on the Guard path; if ever used, `defer_until_eot: true` on the function definition.

---

## 7. Package layout

```
apps/api/niyam/
  engine/          Tier A — imported by api-hot AND workers
  guard/           sentence gate + decision table around engine
  think/           tool loop, ChatSurface, receipts, echo guard
  llm/             Sarvam + second vendor, timeouts, RPM, cache
  voice/           relay pumps, session mint, provider hyperparams
  kb/              ingest + FTS; workers write, api-hot/control read
  review/          document scan pipeline
  workers/         job handlers
  db/              session, RLS, outbox, audit
apps/web/          console
apps/paydemo/      mock tenant agent (today may still live as a fixture)
infra/             compose (demo) + prod overlays later
```

Do not put policy in `voice/`. Do not import `kb.search` from Guard.

---

## 8. Data plane

**Postgres 16 is the source of truth.** One primary. Read replica for console and KB search. `pgvector` later, only after a larger **independent** gold set still misses on FTS (current smoke: recall@10 0.91 / MRR 0.71 on 33 queries — not a benchmark).

| Store | Holds |
| --- | --- |
| **Postgres** | tenants, cards, versions, runs, conversations, transcripts, tool_traces, verdicts, approvals, **hash-chained audit**, FTS units, **outbox**, chat_turns |
| **Redis** | job queue, think event log (turn detach), Guard rate limits, session presence, idempotency locks |
| **Object store** | circular blobs, OCR sidecars, caller/agent audio, evidence PDF/JSON, oversized model-call payloads |

Keep the constraints already in Alembic:

- `active` card needs an approver and is immutable
- audit append-only + hash chain
- fail `quote` is a verbatim substring of the checked text
- `tenant_id` on every row; **enable RLS in production** (columns exist; RLS is not on yet)

Connection pools: **small** on api-hot (order of 5 + overflow 10). Workers get a separate pool. `idle_in_transaction` longer than the slowest think. Never hold a pooled connection across an LLM HTTP call. Audit writes do not share a transaction with a vendor call.

---

## 9. Async operations

```
API write (scan, compile, start run)
  → INSERT outbox (topic, payload, idempotency_key)
  → COMMIT
  → worker claims outbox / Redis job
  → handler idempotent on (tenant_id, sha256, rule_fingerprint)
  → run_events for console SSE
  → human steps wait on approval rows
  → poison → dead letter + audit
```

Separate queues so a 60-conversation swarm cannot starve Guard:

| Queue | Jobs | Bound by |
| --- | --- | --- |
| `ingest` | PDF / DocAI / unit extract | pages; assume DocAI **10 req/min** until the dashboard proves otherwise |
| `swarm` | persona conversations | per-tenant cap + 105B **60 rpm** |
| `judge_b` | Tier B + cross-check | 105B pool; second vendor on high severity only |
| `evidence` | PDF/JSON pack, sign | CPU |
| `voice_harness` | synthetic caller | Sarvam WS caps (STT 20 concurrent, TTS 60 concurrent as of 31 Oct 2026) |

**Replay:** cache `model_calls` by `prompt_hash`. A swarm can rerun with zero vendor calls.

**“60 conversations in under 90 seconds”:** Tier A first, bounded fan-out, cached personas. Sequential Tier B at 60 rpm cannot hit that number; say so on the scorecard.

---

## 10. Scaling

| Load | How |
| --- | --- |
| Live Guard RPS | Horizontal api-hot. Cards in memory. No Redis on the check itself. |
| Think | Separate pool from Guard. Cap concurrent thinks per tenant. Voice: `reasoning_effort=none`. |
| Voice calls | Relay replicas + gateway stickiness on `session_id`. One call = 1 client WS + 1–2 vendor WS. |
| Console | api-control + Postgres replica. SSE for `run_events`. |
| Swarm | Worker replicas on `swarm` / `judge_b` queues. Global RPM limiter in `niyam.llm`. |
| Ingest | `ingest` queue; chunk PDFs ≤ 10 pages until live DocAI limits are confirmed. |

Measure **first-reply time with Guard on vs off**. Support teams will reject Guard if that SLO regresses.

Voice relays need session affinity. A generic HTTP autoscaler without stickiness splits a call across replicas and drops audio.

---

## 11. Security and tenancy

- Console: SSO/OIDC, RBAC, named actor on every approval (`X-Actor` in the revamp contract becomes the IdP subject).
- Tenant Guard ingest: mTLS or signed service tokens from the tenant gateway.
- Voice: bearer on the **Authorization header**; HMAC `sig` on the WS URL. Both required. Close `4401` with the same message for forged and mistyped.
- Think: shared secret fail-closed. URL without secret is 503, not a no-tool fallback.
- Secrets: manager; never in the browser bundle; rotate. `NIYAM_ENV=prod` already requires `NIYAM_API_KEY`.
- Data: synthetic in PayDemo; production tenant data purpose-limited, retention TTL on audio, transcript logging **off** by default, no vendor training on tenant audio. DPDP-aligned by construction.
- Prompt safety: circulars, transcripts, and agent output are untrusted; judge has no tools; rule text last; structured output.
- Separation of duties: rule author ≠ sole approver; fix author ≠ fix approver; release approver ≠ sole tester. AI never holds a role.

---

## 12. Observability

Every model call logs: `tenant_id`, `run_id`, `conversation_id`, `stage`, `model`, `prompt_version`, `prompt_hash`, `request_id`, tokens in/out, cost, `latency_ms`, `cache_hit`, `error_code`.

Metrics: pass rate by rule/style, Tier A/B agreement, false positives, Guard latency p50/p95, first-reply time, think concurrency, voice call count, queue depth, vendor 429s, cost per run.

Two clocks: containers UTC; correlate on epoch ms. Reproduce env **inside** the container (`docker compose restart` reloads neither `.env` nor deps).

---

## 13. Failure modes that drive the shape

| Symptom | Architecture cause |
| --- | --- |
| Guard p95 &gt; 3 s | Tier B or KB search on the hot path; cards loaded per request; LLM in Guard |
| Swarm starves live replies | one worker pool / one process |
| “Refunded” with no API call | `tool_calls=[]` treated as evidence; receipts skipped on background turns |
| Voice silent, socket healthy | think URL stale/private; secret missing (must 503 at session mint) |
| Call split / frozen audio | relay without session affinity |
| Judge certifies its own compile | no second vendor; no human activation |
| Redis down | hot path still works (Guard is in-process). Jobs pause. Think reattach degrades to durable poll. |
| Postgres primary down | everything stops. Replica is read-only console, not writes. |

---

## 14. Grow from today

| Now | Production |
| --- | --- |
| One FastAPI (`check`, `guard`, `kb`, `fix`, review) | Split hot / control / relay / worker |
| Compose, no Redis | Redis for jobs + turn event log; Postgres still the record |
| Static API key | OIDC + RLS |
| Guard = Tier A only | Keep that; Tier B async after send |
| No `/think`, no voice sockets | Add think + relay; vendors as hyperparams |
| In-process ThreadPool for Tier B | `judge_b` queue |
| LangGraph as one in-process nine-stage graph | Job orchestration with DB interrupts; Guard stays a function |

Build order (after the engine and text Guard, which exist):

1. Outbox + worker for ingest / scan (already the slow path).
2. `/think` SSE + `chat_turns` + receipts + Guard on the visible text.
3. PayDemo tools + action tests on `tool_traces`.
4. Voice relay topology B (Deepgram English) if a talking demo is needed.
5. Topology A (Saaras + Bulbul) for Indic Guard.
6. Voice harness worker.
7. OIDC, RLS, object store, replica, RPM limiter.

---

## 15. Invariants

1. **`niyam.engine` is the judge of record on the hot path.** LLMs draft and abstain; they do not silently override a Tier A pass/fail.
2. **Tools run in `/think` (or the tenant adapter).** Never in STT, TTS, the relay, Guard, or the judge.
3. **Live Guard is after draft, before TTS.** Managed Voice Agents cannot host that claim.
4. **Empty evidence is unverified.**
5. **Human rows, not in-memory interrupts**, own activation, fix publish, and release.
6. **Postgres is the system of record.** Redis is a queue and a cache. Object store is blobs.
7. **Hot path has no vendor round trip** except the think call the tenant already made.
8. **Same brain for voice and chat.** Surface flag is the only difference (`end_conversation` on voice).
9. **Vendors are hyperparameters.** Topology A is the production Guard path.
10. **AI never activates a rule, publishes a fix, or promotes a release.**
