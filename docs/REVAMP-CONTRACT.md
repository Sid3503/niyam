# Niyam revamp: document-review product, API contract (v0.2)

Sales story for this loop: [`NIYAM-SALES-NARRATIVE.md`](./NIYAM-SALES-NARRATIVE.md).

Source of truth for scope: the revamped PRD (merchant-payment document review). Loop:
`source → rule → scan → review → approve → re-test → evidence`. Six screens: Overview, Library, Rules, Impact, Approvals, Evidence.
Document review opens from a Library row (`/library/:documentId`). The original document is NEVER modified. Applying a redline to the actual PDF is the workbench on that same screen: [`NIYAM-PDF-WORKBENCH.md`](./NIYAM-PDF-WORKBENCH.md).

All routes are under `/api/v1`. Errors: `{"error":{"code","message"}}`. Optional `X-API-Key`. Optional `X-Actor` header names the human
(default `compliance.reviewer`); every decision records it. Demo data is synthetic and labelled as such.

## Vocabulary (one, used everywhere)

- Finding `status`: `current | outdated | missing | contradiction | review`. Missing evidence is never `current`.
- `severity`: `low | medium | high | critical`.
- Approval `status`: `pending | approved | rejected | deferred`. Approval `kind`: `rule | fix`.
- Document `status` (Library): `new | changed | unchanged | reviewed`.
- Rule `status`: `draft | in_review | active | superseded | retired | rejected`. A rule only counts in scans once `active`.
- A suggested fix is an ACTION on a finding (`suggested_fix`), not a status.

## Endpoints

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/overview` | `{documents_scanned, open_findings, fixes_awaiting_approval, rules_pending_approval, citation_coverage (0..1), rules:{active,draft}, next_action:{label, route, kind}}` |
| GET | `/library` | `[Document]` (see below) |
| POST | `/library/scan` | Body `{}`. Discovers new/changed files in the monitored folder, reviews only those not already reviewed against the same rule fingerprint. Returns `{scan_id, trigger:"scan_now", started_at, discovered, reviewed, skipped, documents:[{document_id,title,outcome:"reviewed|skipped_unchanged|new|changed", findings}]}` |
| GET | `/library/scans` | recent scans `[{scan_id, trigger, started_at, discovered, reviewed, skipped}]` |
| POST | `/library/upload` | `{title, doc_type, product, owner, content}` → creates/updates a document version, reviews it, returns the document detail |
| GET | `/documents/{id}` | `DocumentDetail` |
| POST | `/documents/{id}/retest` | Body `{content?: string}`. With `content`, stores it as a new version (the edited copy) and re-reviews it; without, re-reviews the latest version against current active rules. Returns `{document: DocumentDetail, comparison:{before:{open,by_status}, after:{open,by_status}, resolved:[finding_id], remaining:[finding_id], new:[finding_id]}, passed: bool}` |
| POST | `/findings/{id}/send-for-approval` | Creates (or returns) the `fix` approval item. Requires `suggested_fix`. Returns `Approval` |
| GET | `/rules` | existing list; each item now also has `approval_id` (pending item or null), `approved_by`, `approved_at`, `scan_active` (bool) |
| GET | `/rules/{id}` | existing full card (+ `versions:[{version,status,effective_from}]`, `approved_by`, `approved_at`) |
| GET | `/product-facts` | Paytm-controlled **synthetic** facts `[{id, category, title, statement, value, unit, owner, source_label:"Paytm-controlled demo data"}]` |
| POST | `/circulars` | `{url?, text?, title?, institution, product_area, effective_date?}` → `{source:{id,title,institution,url,sha256,retrieved_at,chars}, drafts:[{approval_id, rule_id, title, source_quote, quote_verified, obligation, severity, tier, product, claim_type}], notes:[string]}`. Draft rules appear in Approvals, `pending`. No draft is active |
| GET | `/approvals?status=&kind=` | `[Approval]`, severity desc then confidence asc (high-severity and low-confidence first) |
| POST | `/approvals/{id}/decision` | `{decision:"approve|reject|defer", reason?}` → updated `Approval`. Approving `rule` activates the card (records approver); approving `fix` records the approved wording against the finding (the document itself stays untouched) |
| GET | `/impact` | List of rules that can be analysed `[{rule_id, version, title, status, effective_from, previous_version|null, affected_count|null}]` |
| GET | `/impact/{rule_id}?version=` | `Impact` (see below). Works for draft rules too (dry run, labelled), so a reviewer sees impact before approving |
| GET | `/evidence` | `[{document_id, title, versions, findings, approvals, last_event_at, retest:"passed|failed|none"}]` |
| GET | `/evidence/{document_id}` | `EvidenceRecord` |
| GET | `/evidence/{document_id}/export` | `text/markdown`, one readable record another reviewer can follow |
| GET | `/audit/verify` | `{ok, events, head_hash}` hash-chain verification |

Existing endpoints stay: `/check`, `/runs`, `/kb/*`, `/guard`, `/fix` (the pre-send checker is a later extension; no screen for it).

## Shapes

```ts
Document = {
  id, title, doc_type: "proposal|agreement|order_form|brochure|pitch_deck|onboarding",
  product: string, owner: string, merchant: string|null, channel: string|null, version: number,
  last_modified: ISO, status: "new|changed|unchanged|reviewed", demo_data: true,
  open_findings: number, by_status: {current,outdated,missing,contradiction,review},
  last_reviewed_at: ISO|null, source_path: string
}
Clause = { idx, locator: string /* "§3.2" or "para 7" */, text, start, end /* offsets into version content */ }
Finding = {
  id, version_id, clause_idx: number|null /* null for a missing-disclosure finding */, locator,
  quote: string|null /* verbatim substring of the clause */, span: [start,end]|null /* offsets into version content */,
  status, severity, confidence, reason,
  rule_id: string|null, rule_version: number|null, rule_status: string|null, fact_id: string|null,
  source: { document, reference, locator, quote, regulator, provenance } | { fact_id, title, statement, label:"Paytm-controlled demo data" },
  tier: "A|B|A+B", suggested_fix: { wording, rationale, validated: boolean /* Tier A re-check of the wording passed */ } | null,
  approval: { id, status } | null, decision: null|"approved|rejected|deferred", needs_human: boolean
}
DocumentDetail = {
  document: Document, version: { id, version, sha256, content, created_at, trigger: "scan|upload|retest" },
  clauses: Clause[], findings: Finding[], versions: [{id,version,sha256,created_at,trigger,open_findings}],
  rule_fingerprint: string
}
Approval = {
  id, kind: "rule|fix", status, severity, confidence|null, title, created_at, decided_at|null, decided_by|null, reason|null,
  document: {id,title}|null, clause: {locator, text}|null, finding_id|null,
  current_wording|null, proposed_wording|null,           // fix
  rule: {id, version, title, obligation, tier, effective_from, status}|null,  // rule
  source: { document, reference, locator, quote, provenance, quote_verified: boolean }
}
Impact = {
  rule: {id,version,title,status,effective_from,obligation,source:{document,reference,quote}},
  previous: {version,status,effective_from,obligation, changes:[string]} | null,   // old vs new side by side
  dry_run: boolean, // true when the rule is not active yet
  affected: [{ document_id, title, owner, version, clause_locator, quote, status, reason /* why selected */, matched_on:[string], change_note, proposed_wording|null, task:{owner,title,state:"open|done"} }],
  scanned_documents: number
}
EvidenceRecord = {
  document: Document, original: {version, sha256, content_preview}, events:[{seq, ts, actor, action, summary, payload}],
  findings:[Finding], approvals:[Approval], retests:[{ts, passed, before, after}], notifications:[{ts, to, channel:"in_app", subject}],
  chain_ok: boolean
}
```

## Honest-labelling rules (UI must follow)

- Rule drafts show `draft`/`pending`; only `active` rules drive scans. Show approver and date once active.
- Product facts carry the label "Paytm-controlled demo data". Documents carry "Synthetic demo document".
- Every finding shows quote, rule id + version (or product fact id), and confidence. No finding without a source.
- Footer: "Decision support, not legal advice. All documents and Paytm product facts are synthetic demo data."

---

# v0.3 addendum: sales shift, PDF workbench, voice-note check

Goal of this addendum: the product is sold to sales ops and onboarding with one pitch: **"proposals and brochures stop shipping claims that are out of date, and you can see when a fix is approved"** (the mechanism is a circular becoming a reviewed redline pack with a named approver). Build to
`NIYAM-SALES-NARRATIVE.md`, `NIYAM-PDF-WORKBENCH.md`, and the voice PRD (V1 only: voice-note check). Everything above still holds.

**Deviation from the workbench spec (deliberate):** apply and commit run **on the server with PyMuPDF true redaction** (the old text is removed from the
content stream, then the new wording is inserted), not pdf-lib in the browser, because a browser rewrite cannot guarantee the old text is gone from
extraction. The browser renders (pdf.js) and drives the loop; the server is the writer. The invariants are unchanged: original bytes immutable, whiteout is
never the fix, a committed version whose extracted text still contains the stale quote is rejected `409 stale_text_remains`, the engine (not the canvas)
marks findings resolved.

## Document formats

`Document` gains: `format: "markdown" | "pdf" | "voice"`, `pages: number | null`, `duration_seconds: number | null`.
`doc_type` gains `"voice_note"`.
`Finding` gains: `page: number | null` (1-based), `bbox: [x0,y0,x1,y1] | null` (PDF points, origin top-left, i.e. PyMuPDF coordinates; null for markdown, voice, and missing-disclosure findings), `audio_time: [start_s, end_s] | null` (voice only; approximate when the speech API returns one segment).
`DocumentDetail` gains (present only for its format, else null):

```ts
workbench: { pdf_url: string /* GET /documents/{id}/file?version=<current version id> */, pages: number, page_sizes: [number, number][] /* [w,h] points per page */ } | null
voice: { audio_url: string, duration_seconds: number, language: string, transcript_original: string /* codemix, shown to the human */,
         transcript_en: string /* normalised English, == version.content, the text every quote is verified against */,
         sentences: [{ idx: number, start: number, end: number, text: string /* substring of transcript_en */, start_char: number, end_char: number }],
         stt: { provider: "sarvam", model: string }, timing_note: string } | null
```
For `format="voice"`, `version.content` is `transcript_en`; clause spans index it; the original transcript is display-only.

## New / changed endpoints

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/overview` | **adds** `steps` and `pack` (below) |
| POST | `/library/upload-file` | multipart: `file` (PDF, WAV/MP3/M4A/OGG/WEBM audio), `doc_type`, `product`, `owner`, `merchant?`, `title?`. PDF: stored as bytes, text + page geometry extracted. Audio: transcribed, reviewed. Returns `DocumentDetail`. 422 `no_text` for an image-only PDF ("needs OCR"), 415 for other types |
| GET | `/voice/samples` | `[{name, title, language, duration_seconds, audio_url, expected: string}]` synthetic demo clips shipped with the repo |
| POST | `/voice/samples/{name}/check` | runs a sample through the same pipeline; returns `DocumentDetail` |
| GET | `/documents/{id}/file?version=` | bytes of that version's PDF or audio (default latest). Original version stays addressable |
| POST | `/documents/{id}/apply` | PDF only. Body `{ edits: [{finding_id, wording}], commit: boolean }`. `commit=false`: build a working copy in memory, extract, run the engine, return a preview. `commit=true`: same, then, if no stale text remains, store version N+1 (`trigger: "workbench"`). Response `{ committed, strategy: [{finding_id, method: "redact_rewrite"\|"rasterize_page"\|"append_text"}], stale_text_remains: [{finding_id, quote}], sha256_before, sha256_after, comparison, preview_url: string \| null, document: DocumentDetail \| null }`. `409 {code:"stale_text_remains"}` when `commit=true` and any stale quote is still extractable. A `missing` finding (no bbox) is applied as `append_text` (a new "Additional terms" block on the last page) |
| GET | `/documents/{id}/preview.pdf?token=` | the uncommitted working copy from the last `apply` with `commit=false` (kept briefly in server memory, not the record) |
| GET | `/documents/{id}/page.png?version=&page=&dpi=` | rendered page image (default 110 dpi) for compare |
| GET | `/documents/{id}/compare?from=&to=` | `{from:{version_id,version,sha256}, to:{...}, pages:[{page, from_url, to_url, changed: boolean}]}` |
| GET | `/evidence/{id}/pack.pdf` | cover page(s) with findings, approvals, re-tests, both SHA-256s, chain status + the latest PDF, metadata stripped. Only for PDF documents |
| GET | `/evidence/{id}` | **adds** `hashes: {original:{version,sha256}, current:{version,sha256}}`, `format` |
| GET | `/evidence/{id}/export` | markdown now lists both SHA-256s |

### `/overview` additions

```ts
steps: [{ key: "circular"|"rules"|"scan"|"fixes"|"retest"|"evidence", label: string, state: "done"|"current"|"todo", detail: string, route: string }]
pack: { circular_title: string|null, started_at: ISO|null, approved_at: ISO|null /* set once open_findings == 0 after fixes were approved */,
        elapsed_seconds: number|null /* until approved_at, else until now */, documents_total: number, documents_affected: number, documents_clear: number } 
```
`steps` is the six-step loop the Overview draws as a ribbon; exactly one step is `current`.

## Honest labelling additions

- Voice clips are **synthetic** (generated with Sarvam TTS for the demo). Timestamps are approximate when the speech API returns one segment.
- A PDF apply that had to rasterize a page loses that page's selectable text; the UI says so.
- Redaction/encrypt/PII on the pack and OCR are **not built**; do not show them as working.

## v0.3 implementation notes (what the build actually does)

- `POST /documents/{id}/apply` re-typesets the rest of a **text-only** page downward when the new wording is longer (strategy still `redact_rewrite`). It never rasterizes: a flattened page would hide every other clause on it from the engine and cause false passes, so `rasterize_page` is not produced. A page with images or vector graphics, or wording that cannot fit the page, returns `422 wording_does_not_fit` with `finding_id`, `locator` and a plain-language reason.
- Error bodies pass through extra fields (`409 stale_text_remains` carries `stale_text_remains: [{finding_id, quote}]`).
- Voice: `transcript_en` (Sarvam `translate` mode) is what the engine checks and what quotes are verified against; `transcript_original` (codemix) is display only. Sentence times are approximate for single-segment clips and the response says so.
- `GET /overview.next_action` follows `steps`: it is the call to action of the one `current` step.
