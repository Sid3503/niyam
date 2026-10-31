# Niyam — reference docs

Seven documents answer what Niyam is, how it is sold, how the PDF apply step works, how Sarvam fits, how voice/tools work, and how it scales.

| Doc | Read it for |
| --- | --- |
| [`NIYAM-SALES-NARRATIVE.md`](./NIYAM-SALES-NARRATIVE.md) | GTM door: sales-ops teammate. Core pitch: proposals and brochures stop shipping out-of-date claims, and you can see when a fix is approved. Circular → library scan → cited finding → drafted redline → named approval → re-test → evidence. Buyer, five-minute demo, claims, Overview metrics, talk track. Voice/Live Guard are phase 2 on the same rules. |
| [`NIYAM-PDF-WORKBENCH.md`](./NIYAM-PDF-WORKBENCH.md) | Core apply step: in-browser PDF canvas (pdf.js / pdf-lib pattern) on a **copy**. Finding overlays, in-place rewrite of suggested_fix, stale-quote commit gate, OCR, evidence hash/compare/redact/encrypt. Not a 59-tool PDF product. |
| [`NIYAM-END-TO-END.md`](./NIYAM-END-TO-END.md) | Product definition, users, the obligation graph, the nine-stage loop, rule-card and verdict contracts, console IA, architecture, data model, state machines, demo scope, metrics, risks. |
| [`SARVAM-AI-LOGIC.md`](./SARVAM-AI-LOGIC.md) | The Sarvam model/API inventory, the six functional Sarvam layers plus access, stage-by-stage prompts and schemas, model routing, validation, fallbacks, cost/latency/rate limits, privacy, and version corrections. |
| [`NIYAM-VOICE-AND-TOOLS.md`](./NIYAM-VOICE-AND-TOOLS.md) | HeyPari voice-shell / think-brain topology mapped onto Niyam Live Guard and the voice harness. Sarvam and Deepgram as hyperparameters, websocket contracts (31 Oct 2026), tool loop, fillers/barge-in/echo, three topologies, demo vs later build. |
| [`NIYAM-PRODUCTION-ARCHITECTURE.md`](./NIYAM-PRODUCTION-ARCHITECTURE.md) | Production-ready scalable shape: process split (api-hot, api-control, voice-relay, workers), chat vs voice vs corpus-ask, tool loop, Postgres/Redis/object store, outbox jobs, security, grow-from-today. Demo stays Compose; this is the post-demo target. |
| [`REGULATORY-CORPUS.md`](./REGULATORY-CORPUS.md) | The regulator document corpus (`../regulations/`, `../paytm-terms/`): what is stored, corrections to the rule cards (e.g. UPI merchant TAT is T+5, not T+1), revised and new rule cards, effective-date calendar, how it maps to the nine stages, gaps and manual downloads. Tags every claim [V] verified / [A] agent-read / [I] inference. |

Also in this folder (build contracts, not the product story): [`PLATFORM-BUILD.md`](./PLATFORM-BUILD.md), [`ENGINE.md`](./ENGINE.md), [`REVAMP-CONTRACT.md`](./REVAMP-CONTRACT.md).

## Source hierarchy used

1. `Niyam-Product-Guide.pdf` — the most complete statement of intent and build scope.
2. `Niyam-Pitch-Deck.pdf` — the outward-facing story and numbers.
3. `screens/*.png` — the visual and interaction specification for the console.
4. `DESIGN.md` — colour, role, entry, and motion rules.
5. `niyam-web/` — the only running code in this folder (a React sidebar demo, not the full console).
6. Sarvam AI documentation, checked 31 October 2026 — current model IDs, endpoints, limits, and prices.
7. HeyPari `docs/VOICE_AI_END_TO_END.md` — transferable voice-shell / think / tool invariants (different product; topology only).
8. Deepgram Voice Agent + Flux docs, checked 31 October 2026 via Firecrawl.

## Important framing

- Sales door is **legal time on the document library**, not the agent swarm. See [`NIYAM-SALES-NARRATIVE.md`](./NIYAM-SALES-NARRATIVE.md). Swarm numbers (71% → 96%, 11 minutes, 60 conversations, 8 rule cards) are **PayDemo agent-test targets**, not Paytm production, and they are the wrong headline for this motion.
- The durable asset is the **versioned obligation graph plus the labelled Indian-finance test corpus and its regression history**, not the LLM or the dashboard.
- Sarvam is the **India-language substrate** — documents, language, speech, translation. It is not the compliance logic, the judge of record, or the approval authority.
- AI never activates a rule, publishes a fix, or promotes a release. A named human does.
