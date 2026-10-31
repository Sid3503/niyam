# Niyam rule cards (draft pack v1)

Ten machine-readable rule cards, built 31 Oct 2026 from the stored regulator documents in `../regulations/`. **Every card is `draft` with no approver.** The product's own invariant is that only a named human moves a card to `active`; nothing here has been reviewed by a compliance officer.

```
rules/
├─ cards/<ID>.v<N>.json   one obligation per file, immutable once active (new version = new file)
├─ validate.py            python3 -I rules/validate.py [--stamp] [--as-of YYYY-MM-DD] [card.json ...]
└─ tools/pdftxt.swift     macOS PDFKit text helper (used only if `pdftotext` is not installed)
```

## Run it

```bash
python3 -I rules/validate.py            # all cards; exit code 1 on any error
python3 -I rules/validate.py --as-of 2027-06-01   # see which date-gated cards are live by then
```

## What the validator proves, and what it does not

| It checks | It cannot check |
| --- | --- |
| Required fields, closed vocabularies (check type, tier, severity, status) | That the `obligation` is a **correct reading** of the quote |
| `status: active` has `approved_by` + `approved_at` (a human) | That the person approving understood it |
| `source.file` exists and its **sha256** matches | That the file is the latest or an official copy (it warns on mirrors / user downloads) |
| Every `source.quotes[]` is an **exact substring** of the source text (whitespace-normalised only); warns if a quote is not unique | That an OCR-read quote matches the page image (it warns) |
| Numbers in the config (`deadline_days`, `compensation_per_day_inr`) appear in the cited quotes | Hinglish / regional phrase lists (marked unreviewed) |
| `effective_from` vs `--as-of`: labels not-yet-enforceable cards | Whether a rule was later superseded |

Tested with deliberately broken cards: a tampered quote (T+5 → T+1), a wrong hash, an `active` card with no approver, a bad vocabulary value, a Tier A card with no config, a lowercase id, a missing file, and a wrong deadline or amount in the config. All were rejected.

## The ten cards

| ID | Source | Check | Note |
| --- | --- | --- | --- |
| `RBI-TAT-UPI-TRANSFER` | RBI 2019 TAT, UPI row 4a | timeline A | T+1, **beneficiary bank** reverses. Replaces demo `RBI-TAT-UPI-P2P` |
| `RBI-TAT-UPI-MERCHANT` | RBI 2019 TAT, UPI row 4b | timeline A | **T+5**, not T+1. Replaces demo `RBI-TAT-UPI-P2M` |
| `RBI-TAT-COMP-100` | RBI 2019 TAT paras 4-5 | must_contain A+B | ₹100/day runs from **each row's** deadline, paid suo moto |
| `RBI-KFS-LOAN` | RBI KFS circular 15 Apr 2024 paras 4-6 | must_contain A+B | Annex A field list **unread** (blocked) |
| `RBI-COOLING-OFF` | Digital Lending Directions 2025 para 10 | must_contain A+B | New; split from KFS card |
| `NPCI-UPI-CHARGES-PRE` | NPCI UPI Consolidated Circular | ordering A | **Mirror** source. Replaces demo `RBI-CHARGES-PRE` |
| `DPDP-CONSENT-PURPOSE` | DPDP Act s.5(1), s.6(4) | must_contain B | **Not enforceable until ~13 May 2027** (provisional) |
| `RBI-OMB-ESCALATION` | Digital Lending Directions para 11(iv) | escalation B | **Digital lending only**; 2026 Ombudsman Scheme text unread |
| `SEBI-NO-ASSURED-RETURNS` | SEBI IA Master Circular 6 Feb 2026 | must_not_claim A+B | Replaces demo `RBI-MIS-SELL-GUARANTEE` (no plain RBI ban found) |
| `NPCI-UPI-MASK-IDENTIFIERS` | NPCI OC 234 FY26-27 (**OCR**) | must_not_claim A | New; user-downloaded file, official URL unknown |

## Before any card can be activated

1. A compliance officer reads the quote and the obligation and approves. Set `status`, `approved_by`, `approved_at`, and an `owner` who is an active user.
2. Replace mirror / user-downloaded / OCR sources with the official document, then re-run `--stamp` (clear `sha256` first) and `validate.py`.
3. Close each card's `open_issues` (unread annexes, blocked PDFs, provisional dates).
4. Have a native reviewer approve every Hinglish / regional phrase variant (`variants_unreviewed`).
5. Decide the closed-vocabulary gap: `NPCI-UPI-MASK-IDENTIFIERS` uses `must_not_claim` as the nearest type; a forbidden-output-pattern type is probably needed.

## Design notes

- A card cites **row-level** evidence (the TAT table rows are separate cards), because merging rows 4a and 4b is exactly the error the earlier demo cards contained.
- `check.config` mixes quoted facts with `authored_by_niyam: true` test logic (`fail_if`, `review_if`, phrase lists). The first is regulation; the second is our design and needs review.
- `aliases` records the old demo ids so existing console/deck references can be mapped.
- `.json` is the source of truth. Cards are immutable once active; a change creates `<ID>.v2.json` with `supersedes` set.
- `tools/bin/pdftxt` is a compiled helper that `validate.py` builds on first use if `pdftotext` is absent. Safe to delete.
