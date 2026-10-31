# Niyam PDF Workbench

**Status:** feature spec, **31 October 2026**. Not a product. A **core step** of the revamped document-review loop: the lawyer applies an approved clause delta onto a **copy** of the PDF, in the browser, then Niyam re-tests and files the evidence.

**Sibling docs:** [`NIYAM-SALES-NARRATIVE.md`](./NIYAM-SALES-NARRATIVE.md), [`REVAMP-CONTRACT.md`](./REVAMP-CONTRACT.md), [`ENGINE.md`](./ENGINE.md), [`NIYAM-PRODUCTION-ARCHITECTURE.md`](./NIYAM-PRODUCTION-ARCHITECTURE.md).

ihatepdf.cv is a **reference for client-side PDF technique** (pdf.js + pdf-lib + workers + optional Tesseract WASM). It is not a dependency, not a vendor, and not a 59-tool menu we ship. We reimplement only what the legal loop needs, with Niyam’s invariants on top.

---

## 0. Why this is core

Today the loop stops at **words**:

> find the stale sentence → draft replacement → named human approves → *someone else opens Word/Acrobat* → re-test if they remember to come back.

The missing product is **apply on the actual PDF**, still inside Niyam, still on a copy, still fail-closed.

Sales line this unlocks: *legal never round-trips the file through Word. They click the finding, accept the wording, download a new version whose hash sits on the evidence pack.*

The original document stays immutable. The workbench only mutates a working copy. Commit creates `version N+1`. The engine re-extracts text and must **not** still find the old quote.

---

## 1. Where it sits in the loop

```
source (circular PDF, often scanned)
  → rule (human activates)
  → scan (engine on extracted text + page map)
  → review (findings with quote, span, page, bbox)
  → WORKBENCH apply on a copy
       suggested_fix overlay → in-place rewrite
       local preview check → commit
  → approve (named actor; may happen before apply)
  → re-test (server extract + engine; comparison)
  → evidence (hashes, visual diff, optional encrypt / PII flatten)
```

Six screens stay the same. Workbench **is** the document-review canvas on `/library/:documentId`, not a seventh product called “PDF tools.”

| Stage | Server (already true) | Workbench (new) |
| --- | --- | --- |
| Ingest | Store bytes, sha256, extract text | pdf.js preview; Tesseract if no text layer |
| Review | Findings + `suggested_fix` | Highlight bbox; jump-to-finding |
| Apply | Forbids overwrite of version 1 | In-place replace on a **copy** |
| Gate | `/retest` on new content | Commit uploads bytes + client sha256 |
| Prove | Hash chain, export markdown | SHA-256 of PDF bytes; visual compare; pack options |

`pipeline.py` still does not edit a document. The workbench is the only writer, and it writes a new version.

---

## 2. End-to-end user path

1. Counsel opens Bluecart proposal (PDF) from Library.
2. Pages render locally. Findings list is docked; each row has `page`, `bbox`, `quote`, `suggested_fix.wording`, `validated`.
3. Click a finding. The text run highlights. Suggested wording is pre-filled.
4. **Apply.** Workbench rewrites that run on the working copy (font, size, colour, position). Original file in object store is untouched.
5. **Preview check.** Client extracts text from the working copy and `POST /check` (or `/guard/check` with facts). Rows that would close go green. If the old quote is still extractable, Apply is rejected (`stale_text_remains`).
6. Counsel clicks **Commit as version**. Multipart upload: PDF bytes, `sha256`, `applied_finding_ids[]`. Server re-hashes, extracts, runs the review pipeline, returns the same comparison as `POST /documents/{id}/retest`.
7. If a fix was not yet approved, Commit can also `send-for-approval` with before/after snippets. Approving a fix still does not mutate the original.
8. Evidence export includes both PDFs’ SHA-256, the visual page diff, approver, rule versions.

Word/Acrobat never enters the story.

---

## 3. What we take from the ihatepdf pattern

Client-side workbench, shared infrastructure, tool-specific operations. Heavy work in a Web Worker. pdf.js for render/parse; pdf-lib for structural write; canvas only when we must destroy pixels.

### 3.1 Ship (Niyam-shaped)

| Capability | Niyam job |
| --- | --- |
| In-place text rewrite | Apply `suggested_fix` on the cited run |
| Add text box | Missing-disclosure findings (no bbox); place the required sentence |
| OCR (Tesseract WASM) | Scanned circulars and signed scans at ingest |
| Finding overlay | Jump from quote to page geometry |
| Visual compare | Version N vs N+1 on Evidence |
| SHA-256 fingerprint | Client checksum vs server `sha256`; evidence pack |
| Destructive redaction | PII on **exported evidence** (DPDP), rasterize affected pages, drop original page objects |
| Privacy strip | Author/creator/dates off the evidence PDF |
| Flatten / read-only | Signed pack cannot be quietly re-edited |
| Encrypt pack | AES-256 on the download, tenant password; implementation must be a library we name and test |
| Compress | Keep packs small |
| Merge | Circular excerpt + redlined PDF + evidence markdown → one download |

### 3.2 Do not ship as a toolkit

- A 59-tile “PDF lab.”
- Chat with PDF / Gemini (sends extracted text off-box; also the wrong judge). Console “ask the corpus” stays `/kb/search` + citations on **already stored** units.
- P2P share, whiteboard, Whisper, Kokoro.
- Unlock / remove-password as a cracker. Ingest may decrypt **if the tenant supplies the password**.
- Generic convert-to-Word. Extraction is for the engine, not a product.
- Invisible recipient fingerprinting. Our “fingerprint” is a file hash, already in the audit chain.
- Whiteout as the apply method for a **failed claim** (covers text; extraction still finds it). Whiteout is only a visual aid, never the compliance write.

---

## 4. The apply contract (this is Niyam, not a CV editor)

ihatepdf’s public writeup does not prove how original text is removed. For Niyam, **the stale claim must be gone from extracted text**, not merely hidden.

Apply strategies, in order:

1. **Content-stream rewrite** — replace the text showing operator for that run; keep the rest of the page as objects.
2. **If rewrite cannot guarantee removal** — rasterize **that page only** (high-res canvas), draw the new sentence, embed the image, **do not copy** the original page object. Selectable text is lost on that page; the old quote cannot be copied out. Untouched pages stay as objects.
3. **Never** “white rectangle over the words” as the committed fix.

**Commit gate (server, fail-closed):**

```
extract(new_pdf)
if old_quote still a substring of extract → 409 stale_text_remains
run engine on extract
comparison.resolved / remaining / new
suggested_fix.validated must be true before Approvals
```

Client preview uses the same rule so counsel sees the 409 before upload.

Font matching is best-effort (Helvetica / Times / Courier / licensed fallbacks). Unusual embedded fonts may substitute. If substitution overflows the bbox, the UI warns; counsel accepts wrap or rasterize. “Same font” is not a guarantee; “old quote gone” is.

---

## 5. Data and API

Keep `REVAMP-CONTRACT.md` shapes. Add geometry and bytes.

**`document_versions`**

| Field | Role |
| --- | --- |
| `sha256` | Bytes of the PDF (or markdown today) |
| `content` | Extracted text; engine and quotes index this |
| `page_map` | `[{clause_idx, page, x, y, w, h, font, size}]` |
| `blob_key` | Object store |
| `trigger` | `scan \| upload \| retest \| workbench` |

**`findings`** already have `span` into `content`. Join to `page_map` so the canvas can highlight.

New routes (all `/api/v1`, same auth and `X-Actor`):

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/documents/{id}/file` | Signed URL or bytes of **latest** version; original remains addressable as `?version=` |
| `GET` | `/documents/{id}/workbench` | `{file_url, page_map, findings[]}` for the canvas |
| `POST` | `/documents/{id}/preview-check` | `{extracted_text}` → engine comparison **without** persisting a version (local apply preview) |
| `POST` | `/documents/{id}/commit` | Multipart PDF + `sha256` + `applied_finding_ids[]`. Server verifies hash, extracts, reviews, returns `DocumentDetail` + `comparison`. Creates version. |
| `GET` | `/documents/{id}/compare?from=&to=` | Page images or object-diff metadata for Evidence |
| `GET` | `/evidence/{id}/pack.pdf` | Optional: merged, flattened, metadata-stripped, SHA-256 listed; encrypt if requested |

`POST /documents/{id}/retest` with `content` remains for markdown/demo. PDF path is `commit`.

Object store holds PDFs (production architecture). IndexedDB on the client is **only** the in-progress working copy; closing the tab should prompt; we do not treat browser storage as the record. Postgres remains the system of record.

---

## 6. Ingest: circulars and library PDFs

Two inputs, one extractor contract.

**Library (customer docs).** Upload PDF → store bytes → extract text + `page_map` (server PyMuPDF today; client pdf.js can send a proposed map, server always recomputes). No text layer → queue OCR (worker: existing `make_ocr_sidecars.py`, or Tesseract in the browser then send sidecar). Engine runs on text. Scanned-only pages get OCR confidence; low-confidence words are `review`, never `fail` with a fake quote.

**Circulars.** Same OCR path. Quote verification still requires the quote to be a substring of extracted text. A scanned RBI PDF that only has glyphs does not activate a rule until OCR (or a human paste) produces a verifiable quote.

Do not send circular or library bytes to Gemini or any “chat with PDF” vendor.

---

## 7. Evidence and DPDP

The workbench also **finishes** the pack, which is why this is core rather than an editor plugin.

| Pack step | Behaviour |
| --- | --- |
| Hash | SHA-256 of original and new PDFs; must match `document_versions.sha256`. SubtleCrypto in the browser for the download receipt; MD5 is not used. |
| Compare | Side-by-side pages; finding overlays on both. |
| Flatten | Evidence PDF annotations burned in; further silent edits are obvious. |
| Metadata strip | Author, producer, dates, embedded-image GPS off the **pack**, not off the working legal file unless counsel asks. |
| PII redact | Pattern pass (Aadhaar, PAN, passport, cards with Luhn, email, phone) as an **assistive** list. Counsel reviews. Export uses **destructive** page rasterization for accepted hits. Label: not a compliance guarantee. |
| Encrypt | Optional password on the downloaded pack. Name the library in code and verify with an independent inspector. |
| Unlock | Out of scope except “tenant typed the open password at ingest.” |

ihatepdf’s own docs contradict “everything stays local” (Chat with PDF → Gemini) and “no size caps” (device memory limits). Niyam copy:

- Working edits happen in browser memory so we are not streaming keystrokes.
- **Commit and evidence are server-side.** That is the audit product.
- Chat-with-PDF is not a Niyam feature.
- Practical size limits are honest (order of 50–150 MB by device).

---

## 8. Architecture

Fits [`NIYAM-PRODUCTION-ARCHITECTURE.md`](./NIYAM-PRODUCTION-ARCHITECTURE.md): this is **api-control + web + object store + ingest worker**. Not api-hot. Not voice-relay.

```
apps/web  /library/:id
  pdf.js render + finding overlays
  pdf-lib working copy in a Web Worker
  tesseract.wasm only on pages with no text layer
  preview-check → POST extracted text
  commit → multipart

apps/api
  extract + page_map (PyMuPDF)
  engine / review pipeline (unchanged)
  commit handler: hash, store blob, extract, review, audit

worker ingest
  OCR sidecars, large PDFs
```

Judge and Guard still have **no PDF library**. They see extracted text.

Vendor hyperparams stay Sarvam for language/Tier B. The workbench has **no LLM in the write path**. Suggested wording already came from the fixer; Apply is geometry.

---

## 9. Invariants

1. **Original bytes are immutable.** Workbench writes version N+1 only.
2. **Stale quote must be absent from extract** after commit, or the commit is rejected.
3. **Whiteout is not a fix.** Destructive rasterize is allowed when rewrite cannot prove removal.
4. **Named human** still approves rules and fixes. Apply without approval is a draft version, labelled.
5. **Engine is the judge of record** on extracted text. The canvas does not “mark resolved.”
6. **No third-party chat on document text.**
7. **PII redact is assistive** and destructive on export; it is not a DPDP certification.
8. **Fingerprint means SHA-256 of file bytes**, the same hash already on the version row.
9. **We do not ship ihatepdf.** We ship a Niyam canvas using ordinary PDF libraries. Domain clones (`ihatepdf.pro` etc.) are irrelevant.

---

## 10. Demo (adds one beat to the sales narrative)

After findings on the Bluecart proposal:

7. Open the PDF canvas. The 7-working-day reversal sentence is highlighted.
8. Apply the T+5 wording. Preview check turns that finding green; “assured returns” stays red.
9. Commit version 2. Re-test comparison shows resolved / remaining.
10. Evidence pack lists two SHA-256s and the page image.

Clock still on: hunt + first draft + **file** in one sitting.

---

## 11. Build order

1. `page_map` on ingest + highlight in the existing review UI (even on markdown as fake one-page).
2. pdf.js viewer on `/library/:id` for real PDFs in object store.
3. Apply via rewrite or page-rasterize; `preview-check`; `commit`.
4. `stale_text_remains` gate (the acceptance test that matters).
5. Compare view on Evidence.
6. Pack: flatten + SHA-256 receipt.
7. OCR for scans.
8. Optional: PII assist on pack export, encrypt pack.

Skip everything in §3.2 until someone asks for a PDF utility company. That is a different product.
