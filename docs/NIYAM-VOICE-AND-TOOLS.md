# Niyam voice, tools, and Live Guard

**Status:** architecture mapping, **31 October 2026**. Nothing in this repo implements the sockets yet. Vendor IDs, limits, and prices change; re-check on build day.

**Scope:** how HeyPari’s voice-shell / think-brain / tool-loop topology transfers to Niyam, with Sarvam and Deepgram treated as **hyperparameters**, and Live Guard sitting in the only slot that can actually block a spoken reply.

**Sibling docs:** [`NIYAM-END-TO-END.md`](./NIYAM-END-TO-END.md) (product loop), [`NIYAM-PRODUCTION-ARCHITECTURE.md`](./NIYAM-PRODUCTION-ARCHITECTURE.md) (process split, jobs, data plane), [`SARVAM-AI-LOGIC.md`](./SARVAM-AI-LOGIC.md) (model inventory and S0–S6), [`REGULATORY-CORPUS.md`](./REGULATORY-CORPUS.md) (rule cards). HeyPari source of the invariants: `heypari/docs/VOICE_AI_END_TO_END.md` and `heypari/.grok/skills/voice-agent/SKILL.md`.

**Vendor snapshot (Firecrawl, 31 Oct 2026):**

- [Sarvam realtime STT](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/realtime-streaming)
- [Sarvam STT best practices](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/best-practices)
- [Bulbul v4 Flash best practices](https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/best-practices)
- [Sarvam-105B](https://docs.sarvam.ai/api/getting-started/models/sarvam-105b)
- [Sarvam Voice Agents (Samvaad)](https://docs.sarvam.ai/voice-agents/deploy/deploy-with-code)
- [Deepgram Voice Agent config](https://developers.deepgram.com/docs/configure-voice-agent)
- [Deepgram think / LLM models](https://developers.deepgram.com/docs/voice-agent-llm-models)
- [Deepgram Voice Agent STT](https://developers.deepgram.com/docs/voice-agent-stt-models)

Niyam is **not** a collections or voice product. Voice here is (1) a **test surface** for the persona swarm and (2) the **Live Guard** path that stops a bad reply before a customer hears it.

---

## 0. Executive summary

Keep HeyPari’s split. Change the vendors and insert Niyam’s compliance brain.

| Piece | HeyPari | Niyam |
| --- | --- | --- |
| Voice shell | Deepgram Agent (Flux STT + Aura TTS + VAD) | **Hyperparam.** Default cascaded: Saaras realtime STT + Bulbul TTS. Alternate: Deepgram Agent Flux. |
| Relay | `agent_bridge.py` owns sockets, never content | Same job: Niyam relay. Dumb about transcripts. |
| Brain | LangGraph in `pari_agent.py` via OpenAI-shaped SSE `/agent/think` | Same job: PayDemo / tenant agent via `/think`. Tools run **here**. |
| Tools | 20 LangGraph tools, bound by closure to the signed-in user | Tenant tools + Niyam **action tests**. Empty `tool_calls` means nothing ran. |
| Reply gate | mutation receipts before the user hears a write claim | **Live Guard** after the draft, **before TTS**. Same slot as HeyPari’s reconciler. |
| Captions / barge-in | Second Listen socket; partials, not finals | Same: dual socket or `vad.speech_start` / `transcript.partial`. Never `transcript.final`. |

**The design principle:** *vendors hear and speak; Niyam thinks, tools, and judges.* A managed Voice Agents product (Sarvam Samvaad, Deepgram with native functions) is a **target under test**, not the Live Guard runtime.

**Canonical path (topology A):**

```
mic PCM
  → Niyam relay WS
  → STT vendor WS  (Saaras realtime or Deepgram Listen/Flux)
  → Niyam /think   (sarvam-105b-conversations + tools)
  → Live Guard     (Tier A inline, 3 s budget)
  → TTS vendor WS  (Bulbul v4 Flash or Deepgram Flux TTS)
  → speaker PCM
```

---

## 1. Two jobs for voice in Niyam

### 1.1 Voice harness (Stage 4 — Attack)

Synthetic Indian caller audio hits the **tenant** agent. Niyam records audio + transcript + tool trace, then judges.

```
persona line
  → Bulbul TTS (caller)
  → tenant voice agent (any vendor, including Samvaad / Deepgram / Vapi)
  → agent audio
  → Saaras STT (transcribe / codemix / verbatim)
  → transcript + tool_trace
  → Tier A / Tier B
```

This is a **test instrument**. The tenant may own a fully managed voice stack. Niyam still needs the transcript and a real tool trace. Empty trace on an action rule is `review`, never `pass`.

### 1.2 Live Guard (Stage 9 — Prove / Guard)

The **same rules** applied to a live draft, 3-second budget, before the customer hears it.

```
draft reply (text)
  → sentence gate
  → Tier A inline
  → approve | replace with approved wording | safe handoff
  → TTS
  → Tier B async (does not block the sentence)
```

Text Live Guard is the **must**. Voice Live Guard is a **should** once the text path works. Demo skip: live Indic cascaded voice.

---

## 2. HeyPari invariants that transfer

These are protocol facts, not product facts. They stay even when every vendor ID changes.

1. **The STT/TTS vendor is a voice shell.** It never executes tenant tools. Tools run in Niyam’s backend (or the tenant backend Niyam is assuring).
2. **Think is an OpenAI-shaped HTTPS SSE endpoint.** Deepgram’s Voice Agent `think.provider.type = open_ai` plus `think.endpoint.url` is the proven way to keep the brain on our side. Sarvam-105B already speaks Chat Completions (`/v1` and, for flagship, `/v2`).
3. **Two sockets per call when the agent socket has no interim transcripts.** Deepgram Agent still does not emit partials; `ConversationText` is too late for captions and barge-in. Sarvam realtime STT **does** emit `transcript.partial` and `vad.speech_start` on one socket — so topology A can use one STT socket, plus a droppable caption consumer. Topology B (Deepgram Agent) still needs the second Listen socket.
4. **Two auth checks.** Bearer says *who*. HMAC `sig` on the session WS says *this session was issued to who*. Both, always. Close `4401` with the same message for forged and mistyped.
5. **Think shared secret fails closed.** URL without secret is 503, not a silent no-tool fallback.
6. **Fillers are a protocol event, not a regex.** Inject after ~1.5–2.5 s of silence while tools/guard run; bound the chain; suppress barge-in while a filler plays.
7. **Echo is an AEC problem.** Text matching is a last-resort alarm (`think_echo`: exact filler, or same think in flight). Do not mute the uplink to kill echo (that also kills barge-in).
8. **Empty `tool_calls` means nothing ran.** A mutation/receipt/action check handed `[]` must say unverified, never “the write failed” and never “the write succeeded.”
9. **Grant wins over classifier.** Capability comes from provenance (what just happened), not from the shape of a sentence.
10. **Prompt order is a security control.** Rule text and `precedence` last. Judge has **no tools**.
11. **Execution is detached from delivery.** A turn outlives its socket. Disconnect is detach, not cancel.
12. **Same brain, two surfaces.** Voice and typed chat share the think loop. `end_conversation` is voice-only.
13. **Captions never sit on the audio critical path.** Bounded droppable queue. An `await` on a second socket inside the mic uplink serialises two networks.
14. **Agent behaviour lives in prompts and protocol flags**, not growing regex.

---

## 3. What does not transfer

| HeyPari | Niyam |
| --- | --- |
| Food diary, 20 health tools, meal slots | Tenant FS tools (refund, TAT, fee disclosure, escalation). Niyam **tests** those tools; it does not own the diary. |
| Fast-path food log | Fast-path only for Live Guard **Tier A** (deterministic). No skip of the judge on an action rule. |
| `write_policy` over natural language | Rule cards + tool-trace checks. Provenance still authorises writes. |
| Aura-2 helena, Flux English-only as the product voice | Indic is in-scope for the harness. Deepgram Flux English is a **demo stretch**, not coverage. |
| Phone as first-class client | Console + PayDemo. Mobile AEC traps still apply if a live call is shown. |
| Ollama / OpenRouter / Groq brain chain | `sarvam-105b-conversations` for voice think; `sarvam-105b` for compiler/judge; **different vendor** for high-severity cross-check. Token Factory models do not count as second vendor. |

---

## 4. Providers as hyperparameters

One relay, one think contract, one Live Guard slot. Swap STT / TTS / think model with config, not with a rewrite.

```
# topology
VOICE_TOPOLOGY=cascaded            # cascaded | deepgram_agent
# cascaded = Niyam owns STT, think, guard, TTS (canonical)
# deepgram_agent = Deepgram Voice Agent shell + Niyam /think (HeyPari shape)

# STT
VOICE_STT_PROVIDER=sarvam          # sarvam | deepgram
VOICE_STT_MODEL=saaras:v4          # saaras:v4 | saaras:v3-realtime | flux-general-en | flux-general-multi | nova-3
VOICE_STT_LANGUAGE=auto            # auto | hi-IN | en-IN | …
VOICE_STT_STREAM_TYPE=fast         # Sarvam: fast | balanced | simulated
VOICE_STT_MODE=codemix             # final only: transcribe | codemix | verbatim | translit | translate

# TTS
VOICE_TTS_PROVIDER=sarvam          # sarvam | deepgram
VOICE_TTS_MODEL=bulbul:v4-flash    # bulbul:v4-flash | bulbul:v3 | flux-{voice}-en | aura-2-{voice}-en
VOICE_TTS_SPEAKER=aparna_en_companion
VOICE_TTS_LANGUAGE=en-IN
VOICE_TTS_SAMPLE_RATE=16000        # agents: 16 kHz wav; telephony: 8 kHz

# think
VOICE_THINK_MODEL=sarvam-105b-conversations
VOICE_THINK_REASONING=none         # voice: none; compiler/judge: set explicitly
VOICE_THINK_ENDPOINT_URL=          # public URL Deepgram (or others) will POST
VOICE_THINK_SHARED_SECRET=         # fail-closed if URL set and this empty

# guard
GUARD_BUDGET_MS=3000
GUARD_FILLER_MS=1500
GUARD_TIER_B=async
```

`agent_status()` vocabulary, same shape as HeyPari:

| Value | Meaning |
| --- | --- |
| `ready` | keys, think URL+secret, at least one STT and one TTS provider |
| `no_stt_key` / `no_tts_key` / `no_think_key` | missing vendor credential |
| `misconfigured_think_secret` | think URL set, secret empty |
| `sdk_missing` | required WS SDK not importable |

Session minting **503s** unless `ready`.

---

## 5. Three topologies

### A — Cascaded (canonical for Live Guard)

Niyam relay owns every hop. Live Guard sits on text after think, before TTS. This is the only topology where Niyam can **prove** a sentence was gated.

Use for: Indic Live Guard, Hinglish, the production assurance story.

**STT:** `wss://api.sarvam.ai/speech-to-text-realtime/ws` with `model=saaras:v4` (or default `saaras:v3-realtime`). `stream_type=fast`. Barge-in on `vad.speech_start` or early `transcript.partial`.

**Think:** Niyam `POST /think` → `sarvam-105b-conversations` (`POST https://api.sarvam.ai/v1/chat/completions` only; 32K context). Tools bound in Niyam/PayDemo.

**Guard:** sentence buffer → Tier A → release or replace.

**TTS:** `wss://api.sarvam.ai/text-to-speech/ws?model=bulbul:v4-flash`, frames **config → text → flush** per utterance. Malayalam / Odia: `bulbul:v3` until v4 Flash has `ml` / `od` personas.

### B — Deepgram Agent shell + Niyam think (HeyPari shape)

One Deepgram Voice Agent websocket: Flux STT + Flux TTS (or Aura v1) + turn-taking. `agent.think.provider.type = open_ai`, `endpoint.url` = Niyam `/think`.

Use for: English PayDemo stretch if cascaded Indic is not ready by hour 5. Matches the Product Guide “PayDemo voice agent in English on the Deepgram stack, with sentence gating.”

**Required pins (current Deepgram docs):**

- Listen Flux: `provider.version = v2`, model `flux-general-en`. `language_hints` **only** on `flux-general-multi`; sending hints on `flux-general-en` fails the settings handshake (HTTP 400 / WS `4402`).
- Speak Flux TTS: `provider.version = v2`, voice `flux-{name}-en`. Drop `version` and the agent falls back to Aura v1, where Flux voice IDs are invalid.
- Think: BYO OpenAI-compatible URL. Sarvam-105B conversations is a valid BYO target **if** the URL is publicly reachable and the shared secret is set.
- **Do not** register tenant tools as Deepgram `FunctionCallRequest`s for the Live Guard path. Tools stay inside `/think` so fillers can speak while the graph runs, and so Guard sees the draft **before** audio. If a Deepgram function is ever used, set `defer_until_eot: true` on irreversible calls (refund, hangup, charge).

**Still two sockets:** Agent + independent Listen (Nova-3 or Flux) for captions/barge-in. Caption queue bounded (HeyPari: 64 frames), droppable.

### C — Managed Voice Agents (Samvaad / vendor-native) — target, not runtime

Sarvam Voice Agents (`AsyncSamvaadAgent` / `sarvam-conv-ai-sdk`) mints a signed WS URL and owns STT + LLM + TTS + turns. Deepgram can similarly own functions and speak without our `/think`.

Use as: **the system under test** in the voice harness. Do **not** use as Niyam Live Guard. There is no reliable “after draft, before TTS” hook that Niyam controls, so an independent assurance claim is false.

If a tenant already runs Samvaad, Niyam attaches as:

- transcript + tool-trace ingest (batch or sidecar), and/or
- a **text** Live Guard on whatever draft the tenant will send to TTS, if they expose it.

---

## 6. Topology A — relay, think, guard, speak

```
┌─────────────────────────────────────────────────────────────┐
│ CLIENT / PAYDEMO / PHONE                                    │
│  mic 16 kHz linear16  ·  playback 16 or 24 kHz              │
└───────────────────────────┬─────────────────────────────────┘
                            │ WSS /voice/ws/{session_id}?sig=
                            │ PCM up, PCM down, JSON events
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ NIYAM RELAY  (HeyPari SessionRelay equivalent)              │
│  · two-check handshake                                      │
│  · pump mic → STT                                           │
│  · pump TTS → client                                        │
│  · FillerInjector, activity cards, echo holdoff             │
│  · never parses a transcript to make a policy decision      │
└──────┬───────────────────────────────┬──────────────────────┘
       │ STT WS                        │ TTS WS
       ▼                               ▼
┌──────────────────┐            ┌──────────────────┐
│ Saaras realtime  │            │ Bulbul v4-flash  │
│ or Deepgram Listen│            │ or Flux TTS      │
└────────┬─────────┘            └────────▲─────────┘
         │ transcript.final              │ guarded sentences
         ▼                               │
┌─────────────────────────────────────────────────────────────┐
│ NIYAM THINK  POST /think  (OpenAI SSE)                      │
│  echo guard → optional fast path (Tier A only)              │
│  → sarvam-105b-conversations + bound tools                  │
│  → persist tool_calls (best-effort)                         │
│  → LIVE GUARD (sentence gate + Tier A)                      │
│  → stream visible text to relay                             │
└─────────────────────────────────────────────────────────────┘
```

The relay is intentionally dumb. Policy lives in think + guard, the same way HeyPari keeps it out of `agent_bridge.py`.

---

## 7. Think endpoint and tool calling

### 7.1 Wire contract

Same shape HeyPari already uses, so Deepgram topology B and any OpenAI-compatible shell can call it:

```
POST /think
Authorization: Bearer <shared secret>   # or X-Niyam-Think-Sig
X-Niyam-Session-Id: …
X-Niyam-Tenant-Id: …
X-Niyam-Surface: voice | chat
Content-Type: application/json

{ "model": "sarvam-105b-conversations",
  "messages": [ … ],
  "stream": true,
  "tools": [ … optional, usually bound server-side … ] }
```

Response: SSE `data:` chunks, final usage, `data: [DONE]`. Visible text is **only** finalized non-tool assistant content, after Live Guard. Strip leaked tool-call JSON before it can be spoken.

Sarvam-105B:

| | `sarvam-105b` | `sarvam-105b-conversations` |
| --- | --- | --- |
| Role | Compiler, personas, Tier B, agentic tools | Voice / chat think |
| Endpoint | `/v1` or `/v2` chat completions | `/v1` only |
| Context | 128K | 32K |
| Reasoning | On by default (`reasoning_effort` default `low`) | Same schema; set `none` on the voice path |

Voice think must set `reasoning_effort` to `none` (or the documented disable value) and budget `max_tokens` so reasoning cannot eat the spoken answer. Compiler/judge set the effort **explicitly** (docs still conflict on the default enum). Temperature 0 for compiler/judge.

Auth to Sarvam: `api-subscription-key` and, for Chat Completions, `Authorization: Bearer`.

### 7.2 Where tools run

| Layer | Runs tools? |
| --- | --- |
| STT / TTS vendor | No |
| Niyam relay | No |
| Niyam `/think` (PayDemo or tenant adapter) | **Yes** |
| Live Guard / Tier A / Tier B | **No** — judge has no tools |
| Deepgram `FunctionCallRequest` | Only if topology B opts in; default **off** for Guard |
| Sarvam Samvaad | Tenant’s problem; Niyam consumes the trace |

Tools bind `tenant` / `user` / `db` **by closure**, never as LLM-suppliable arguments. A tool argument is something prompt injection can change.

### 7.3 Action tests (Niyam-specific)

HeyPari’s mutation receipts become Niyam’s **action conformance** checks:

- Refund API path actually called, in order.
- No write without approval.
- Escalation tool bound when the rule requires it.
- Evidence: the `tool_calls` row. `[]` → `review`.

`reconcile_mutation_reply` equivalent: if the model **said** it refunded and no refund tool ran, replace the spoken line with an honest failure, then Guard that line too.

### 7.4 Surfaces

`ChatSurface = voice | chat`. Voice adds `end_conversation`. Typed chat keeps the thread open. A typed goodbye must not archive the conversation.

---

## 8. Live Guard insertion

**Placement:** after the brain drafts a reply, before TTS/streaming. Same slot as HeyPari `reconcile_mutation_reply`. Never in the relay. Never inside Saaras/Bulbul/Deepgram.

```
draft tokens
  → buffer to sentence boundary          # never split mid-sentence into TTS
  → Tier A (regex, arithmetic, ordering, must_contain, must_not_claim,
            tool-trace)  target <100 ms
  → decision table (SARVAM-AI-LOGIC §3.9)
  → release sentence to TTS
  → Tier B async (105B + second vendor on high severity)
```

| Situation | Action |
| --- | --- |
| Tier A pass | Release. |
| Tier A fail, approved wording exists | Replace, release, log. |
| Tier A fail, no approved wording | Safe handoff; escalate. |
| Inconclusive, high severity | Safe handoff. |
| Inconclusive, low severity | Release; flag Tier B. |
| Timeout, high severity | Safe handoff. |
| Timeout, low severity | Release; flag. |
| Empty tool trace on an action rule | Review; do not pass. |

Fillers at **1.5 s** if Guard is still working (tighter than HeyPari’s 2.5 s tool filler, because the customer is waiting on a live support reply). First-reply time is a measured SLO; Guard must not regress it.

High-severity timeout **speaks the safe handoff**, never the unchecked draft.

---

## 9. Dual sockets, barge-in, fillers, echo

### 9.1 When you need two STT sockets

| Shell | Interim transcripts? | Second socket? |
| --- | --- | --- |
| Sarvam realtime (`saaras:v3-realtime` / `saaras:v4`) | Yes (`transcript.partial`, `vad.speech_start`) | Optional. One socket can drive barge-in; a bounded caption consumer may share it. |
| Deepgram Voice Agent | **No.** `ConversationText` is post-endpointing (~4 s late in HeyPari) | **Yes.** Independent Listen for captions + barge-in. |
| Legacy Deepgram Nova on `/v1/listen` | Yes, interims | One socket if you own VAD. |

Barge-in is driven from **partials / VAD start**, never from finals.

### 9.2 Sarvam realtime knobs (current)

Endpoint: `GET/WSS /speech-to-text-realtime/ws` (`wss://api.sarvam.ai/speech-to-text-realtime/ws`).

| Param | Production default for Niyam |
| --- | --- |
| `model` | `saaras:v4` (keyterms up to 50). Fallback `saaras:v3-realtime`. |
| `language_code` | required; `auto` for Hinglish swarm, or `hi-IN` / `en-IN` when known |
| `stream_type` | `fast` for Live Guard / conversational; `balanced` for evidence captions |
| `mode` | applied to **finals only**; partials are always plain transcription. `codemix` or `transcribe`; `verbatim` when the exact words are evidence |
| `endpointing` | `vad` unless the client already has Silero/WebRTC VAD (`manual`) |
| `encoding` | `linear16` |
| `sample_rate` | `16000` (or `8000` telephony). Any other value closes with code `4000`. |
| `silence_duration_ms` | start 500; raise if it cuts mid-sentence |
| Odia code | **`or-IN`** on this endpoint (`od-IN` is the legacy stream) |

Client events: `audio_input` (base64), `ping`, `config.update`, `end`. Server: `session.begin`, `vad.speech_start/end`, `transcript.partial/final`, `pong`, `session.end` (`audio_duration_s` is billed), `error`.

Idle: realtime docs use close `1008` + `ping`. Legacy STT best-practices still document **60 s inactivity** and silent-audio keep-alive / `high_vad_sensitivity=true` on the older `/speech-to-text/ws` path. Pin the keep-alive to the endpoint you actually open; do not copy legacy VAD frame-count params onto realtime (realtime uses milliseconds).

### 9.3 Bulbul knobs (current)

| | HTTP stream | REST | WebSocket |
| --- | --- | --- | --- |
| Path | `POST /text-to-speech/stream` | `POST /text-to-speech` | `wss://api.sarvam.ai/text-to-speech/ws?model=…` |
| Live Guard / agents | Preferred | Offline clips, 48 kHz | Multi-utterance one connection |
| Max rate | 24 kHz | 48 kHz | 24 kHz |

WS sequence per utterance: **config → text → flush**. Hold the socket; `{"type":"ping"}` on idle. Audio: `{"type":"audio", "data": {"audio": "<base64>"}}`.

v4 Flash: 11 language **codes** including `ml-IN` and `od-IN`, but **no `ml` / `od` personas yet** — keep Malayalam/Odia on `bulbul:v3`. Speakers are persona IDs (`aparna_en_companion`, `shubh_en_recovery`); v3 short names (`shubh`) 400 on v4. Native script for Indic; English in Latin, Hindi in Devanagari for Hinglish. `enable_preprocessing: true`. No SSML. Chunk on **sentence** boundaries (this is also the Guard gate). `en-US` is rejected; use `en-IN`. Agent default: `wav` @ 16 kHz.

PayDemo support voice starting points from Sarvam’s own roster: `aparna_en_companion` / `aparna_hi_customer`. Collections-style demo (if shown as a **target**, not as Niyam): `shubh_en_recovery` / `simran_hi_recovery`.

### 9.4 Deepgram knobs (current)

| Knob | Value |
| --- | --- |
| Agent listen Flux | `version: v2`, `flux-general-en`, `eot_threshold` ~0.7 |
| Multilingual Flux | `flux-general-multi` + `language_hints` |
| Agent speak Flux TTS | `version: v2`, `flux-{voice}-en` |
| Agent speak Aura (legacy) | omit `version` / v1; HeyPari still ships `aura-2-helena-en` |
| Think | `open_ai` + public `endpoint.url` + headers |
| Irreversible tools | `defer_until_eot: true` on the **function definition in Settings**, not on `FunctionCallRequest` |
| Fallback LLMs | `think` may be an **array** of providers; per-request ordered fallback |

### 9.5 Echo and AEC

Copy HeyPari’s rule, not its heuristics:

- One capture engine; TTS renders through the engine that owns the mic.
- iOS: voice processing on **input and output** nodes before taps/`start()`.
- Android: `VOICE_COMMUNICATION` source **and** `USAGE_VOICE_COMMUNICATION` on the track; enable `AcousticEchoCanceler`.
- Client: `suppressBargeIn` while filler plays; `looksLikeSelfEcho` = exact substring of current reply + `BARGE_IN_WORDS` escape.
- Server: `think_echo` drops the exact filler just injected, or the in-flight think. Similarity check is a last-resort alarm inside a short playback window. Never Levenshtein.

---

## 10. Session handshake

`POST /voice/session` (or `/agent/session` if topology B reuses the HeyPari names):

```
session_id = uuid4()
sig = HMAC-SHA256(JWT_SECRET, f"{user_id}:{session_id}")
ws_url = /voice/ws/{session_id}?sig={sig}
audio.output.rate = TTS rate (16k or 24k)
audio.input.rate  = 16000
```

WS checks:

1. Bearer / `?token=` → which user.
2. `?sig=` → this session was issued to that user.

Close codes: `4401` unauthorised, `4503` bridge unavailable, `4402` vendor rejected settings, `1011` internal. `finally`: seal the session so a dead call still leaves a transcript.

Think URL must be **public** if Deepgram (or any cloud shell) calls it. `localhost` never works. Stale tunnel → `FAILED_TO_THINK`, healthy audio socket, silence.

---

## 11. Voice harness (Attack), distinct from Live Guard

The harness is a **worker**, not the relay.

```
persona (105B)
  → sentence in native script
  → Bulbul TTS  (caller clip; REST 48 kHz or stream 16 kHz)
  → play into tenant agent  (telephony 8 kHz if PSTN)
  → capture agent audio
  → Saaras  (verbatim when quoting; keyterms: UPI, TAT, refund, ₹, IFSC…)
  → persist audio + transcript + tool_trace + agent_version + prompt_hash
  → judge
```

Deepgram Flux English-only on the **target** does not give Indic coverage. Claim coverage from Saaras on the **Niyam** side of the harness, or from a recorded Hindi/Hinglish clip.

Demo: text Live Guard is the must; English Deepgram PayDemo is should-if-hour-5; one recorded Sarvam clip is could. Skip live Indic cascaded voice in the eight-hour build.

---

## 12. Persistence and evidence

Minimum extra on top of `NIYAM-END-TO-END.md` §10.4:

| Table / field | Why |
| --- | --- |
| `conversations.session_type` | `voice` \| `chat` |
| `conversations.has_audio` | evidence pack |
| `tool_traces` | action tests; empty ≠ fail |
| `guard_events` | draft, verdict, replacement, latency_ms, rule_ids |
| `model_calls` | think + STT + TTS + judge, with `prompt_hash` |
| `audio_objects` | caller clip, agent clip, hashes |

Transcript logging **off** by default (`DEEPGRAM_LOG_TRANSCRIPT_CHARS=0` equivalent). Synthetic data only in PayDemo.

---

## 13. Failure modes (voice)

| Symptom | Cause |
| --- | --- |
| Connects, greets, never tools | Think URL stale / not public |
| Session POST 503 | `agent_status()` ≠ `ready` |
| WS `4402` | Deepgram rejected settings (`language_hints` on `flux-general-en`, Flux model on v1, Aura voice on v2) |
| WS `4401` | bad token or sig |
| Sarvam STT close `4000` | sample_rate not 8k/16k, bad model/language |
| Sarvam STT close `1008` | idle; missing `ping` |
| Speaks twice | echo guard closed early, or AEC off |
| Reply cut mid-sentence | `AudioDone` honoured during in-flight think/guard |
| “Refunded” with no API call | `tool_calls=[]` handed to the receipt reconciler |
| Guard silence >3 s | Tier B accidentally inline; filler injector not armed |
| Indic TTS garbage | romanised Hindi; or v3 speaker ID on v4 Flash |
| Malayalam/Odia 400 on v4 | no persona; use `bulbul:v3` |
| Managed Samvaad “guarded” | topology C — you never saw the draft |

Env trap (HeyPari, still true): `docker compose restart` reloads nothing. Recreate, then `printenv` **inside** the container.

---

## 14. Demo vs later build

Aligned with `NIYAM-END-TO-END.md` §11:

| When | Voice / tools work |
| --- | --- |
| **Must (hour 5–6)** | `POST /guard/check` on a **text** draft. One action test with a real tool trace. |
| **Should** | Think-style endpoint, approved wording, audit log. English PayDemo on Deepgram Agent (topology B) with sentence gating. |
| **Could** | Recorded Saaras clip scored by the judge. |
| **Skip in 8h** | Live Indic cascaded sockets, Samvaad as Guard, production telephony. |
| **After demo** | Topology A with Saaras realtime + Bulbul WS, fillers, dual-path barge-in, HMAC sessions, evidence audio. |

Build order after the hackathon:

1. Text `/think` + `/guard/check` sharing the rule cards.
2. Tool-trace persistence and empty-trace → review.
3. Deepgram Agent English (topology B) — fastest “it talks” using HeyPari’s known-good settings, with Flux TTS v2 pins.
4. Swap STT to Saaras realtime, TTS to Bulbul WS, keep `/think` (topology A).
5. Fillers, echo holdoff, caption socket policy.
6. Voice harness worker (synthetic caller).
7. Never invert 4 and 6 into “just use Samvaad.”

---

## 15. Invariants, compressed

1. **Vendors are hyperparameters.** Topology, model IDs, speakers, and VAD numbers live in config.
2. **Tools run in Niyam (or the tenant adapter), never in STT/TTS.**
3. **Live Guard is after draft, before TTS.** Managed Voice Agents cannot host that claim.
4. **Barge-in from partials / `vad.speech_start`, never from finals.**
5. **Two auth checks; think secret fails closed; think URL is public.**
6. **Empty tool evidence is unverified.**
7. **Fillers are protocol; echo is AEC; prompts beat regex.**
8. **Voice think = `sarvam-105b-conversations` with reasoning off. Compiler/judge = `sarvam-105b` with effort set explicitly. Second vendor ≠ Token Factory.**
9. **`saaras:v4` on realtime WS for Indic; `flux-general-en` + `version:v2` for English Agent. `bulbul:v4-flash` WS; `bulbul:v3` for Malayalam/Odia personas.**
10. **Same brain for voice and chat.** Guard both.

---

## 16. Corrections to older Niyam notes

These supersede a few lines in `SARVAM-AI-LOGIC.md` S5 where vendor docs moved:

- Realtime STT is a **different** endpoint from legacy streaming: `/speech-to-text-realtime/ws`, default `saaras:v3-realtime`, `saaras:v4` supported, partials exist, VAD in milliseconds.
- Bulbul v4 Flash **accepts** `ml-IN` / `od-IN` codes but has **no Malayalam/Odia personas** yet; keep those languages on v3.
- v4 Flash speakers are persona IDs (`voice_language_style`), not v3 short names.
- Deepgram Agent speak default in current docs is **Flux TTS v2**, not Aura-2. Aura remains valid if `version` is v1. HeyPari’s `aura-2-helena-en` still works on the v1 speak path.
- Flux multilingual is `flux-general-multi` + `language_hints`, not hints on `flux-general-en`.
- Sarvam Voice Agents (Samvaad SDK) exists as a managed product. It is a **harness target**, not Niyam’s Guard runtime.

Re-check model IDs, prices, and page limits on build day. Do not store vendor API keys in this repo.
