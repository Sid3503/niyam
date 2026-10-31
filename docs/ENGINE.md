# Tier A check engine (`apps/api/niyam/engine`)

Deterministic, stdlib-only (Python 3.11 to 3.14 verified here; 3.12 not installed on the build host), no network, no LLM. It never changes a card's `status`; drafts stay drafts and every verdict echoes `rule_status`.

```python
from niyam.engine import load_cards, run_checks
cards = load_cards("rules/cards")
verdicts = run_checks(text, facts, cards, as_of=None, rule_ids=None)   # list[Verdict], sorted by rule_id
```

* `rule_ids` given: exactly those cards (`ValueError` on an unknown id; retired/superseded cards run too). Not given: all cards except `superseded|retired|rejected`.
* `as_of` accepts a `date` or ISO string; default is today. DPDP is `not_yet_enforceable` until 2027-05-13.
* Verdict shape is exactly the one in `docs/PLATFORM-BUILD.md`.

## How it works

1. **Gates, in order** (`runner.py`): enforceability (`effective_from > as_of` gives `not_yet_enforceable`, even for blank text) -> blank text (`review`; blank means empty, whitespace, zero-width or control characters) -> facts scope (`surface`, `journey`, `product` outside the card scope gives `not_applicable`) -> the card's predicate.
2. **Folding** (`common.fold`): lower-case, curly quotes/dashes to ASCII, Devanagari digits to ASCII, precomposed nukta letters to the base consonant. It is *length preserving*, so spans found in the folded text index the original and every `fail` quote is `text[start:end]` verbatim. A final `finalize()` guard downgrades any `fail` whose quote is not a verbatim substring (never upgrades).
3. **Matchers live in the cards** (`check.config.matchers`, all `draft`, flagged `matchers_unreviewed: true`): regex lists per language, phrase lists, number-word/unit lexicons, negation and hedge cues. The code only supplies mechanics. Compliance can edit them; the validator still passes.
4. **Segmentation**: sentences (`. ! ? । ; newline`, not after `Rs`/`No`) and clauses (commas, `but/lekin/magar/लेकिन`). Negation, hedges and attribution are judged per clause; relevance per sentence.
5. **Abstention**: anything the matchers cannot decide is `review` with a reason. Confidence: 1.0 for structural facts, about 0.95 for a clear fail, 0.8-0.9 for a pass, 0.5-0.6 for an abstention.
6. **Tier strings**: decided verdicts have `tier: "A"`. Abstentions that need the Tier B judge have `tier: "B"` and `verdict: "review"`; "Tier B not configured" is in `reason` (and in a `semantic` check), so the API can route them. A card with no matchers also abstains this way.

## The transfer-vs-merchant guard (rows 4a / 4b)

Row = `facts.transaction_type`; else `facts.journey == merchant_payment`; else *clear* text cues (merchant, shop, store, QR, dukaan, दुकान ... vs friend, brother, transfer, dost, दोस्त ...). No cue, or cues of both kinds, gives `review` with reason `cannot determine which RBI TAT row applies`, and the engine does not even evaluate the timeline (it lists what it saw in `checks`). The other card returns `not_applicable` when the row is known. `RBI-TAT-COMP-100` only needs the row when `1 < delay_days <= 5`; delay `<= 1` is not late under any row and delay `> 5` is late under every row. Enforced by `test_transfer_vs_merchant_guard_on_all_labelled_texts` and `test_row_cannot_be_guessed_from_thin_evidence`.

## Timeline normalisation (`timeline.py`)

Calendar days from T. `today/tonight/same day/aaj raat/आज` = 0 (kind `same_day`); `tomorrow/kal tak/कल तक/next day/24 hours/T+1` = 1; `N days/din/दिन`, ranges use the **max** (`2-3 days` = 3), weeks x7, hours <= 12 count as same-day else `ceil(h/24)`. `working/business days` stay flagged: n working days are 5-day-week worst-case `n + 2*ceil(n/5)` calendar days, so the judge fails only if `n > deadline`, passes if the worst case fits, else `review`. `a few days` is vague: fail only if the minimum (2) already exceeds the deadline. Relative words are read as T+offset (the engine does not know when the agent writes; known limitation). Ignored on purpose: negated promises (`we cannot promise it will be back tonight`, `kal tak nahi`), update/contact timelines (`we will get back to you in 2 days`), escalation thresholds (`if not credited within T+1, contact your bank`), initiation (`ticket raised today`), past/delay phrases (`3 days ago`, `delay of 3 days`). `not more than`, `do not worry`, `no later than` are guarded so they are not read as negations. `delay_days` is read as days elapsed since T (the contract does not define it; flagged to the API owner).

## Predicate list

| Card | Check | Fail when | Review when | Notes |
| --- | --- | --- | --- | --- |
| RBI-TAT-UPI-TRANSFER (T+1) | timeline | promised days > 1; complaint/ticket/claim required for reversal/compensation; delay > 1 and compensation not fully conveyed | unconditional same-day promise; 1 working day (may exceed T+1); no timeline; row unknown | hedged same-day passes |
| RBI-TAT-UPI-MERCHANT (T+5) | timeline | promised > 5; `T+1` or an RBI-framed next-day limit applied to a merchant payment; complaint required; late and compensation incomplete | unconditional same/next-day promise; 4-5 working days; row unknown | |
| RBI-TAT-COMP-100 | must_contain | discretionary/claim wording about compensation; delay beyond the row deadline and (not Rs100/day or not automatic); wrong amount | row unknown for 1 < delay <= 5; `delay_days` missing; row `other` | `not_applicable` if delay within deadline |
| RBI-KFS-LOAN | document | clearly a KFS document (marker + >= 3 features) lacks language, proposal number, validity, APR computation sheet or amortisation schedule; validity < 3 working days with tenor >= 7 days | all elements present (Tier B must confirm sequencing/language); KFS only mentioned; validity 1-2 days with unknown tenor | `repayment schedule` is accepted as amortisation (limitation) |
| RBI-COOLING-OFF | must_not_convey | no cancellation after disbursal / loan is final / no way out; penalty for exit within cooling-off; stated period < 1 day | exit discussed without the explicit penal-free exit + cooling-off + principal-and-APR wording; facts say cancellation journey but no text cue | pass needs all three |
| NPCI-UPI-CHARGES-PRE | ordering/fact | "no fee/free" while `convenience_fee_shown` true; surcharge on UPI; fee revealed after mode selection | "no fee" with unknown fact; fee mentioned without upfront disclosure | `no surcharge` passes |
| DPDP-CONSENT-PURPOSE | Tier B + Tier A sub-check | cannot/no option to withdraw consent; consent online but withdrawal only by call/visit/post | everything else (notice completeness is Tier B; elements listed in `checks`) | `not_yet_enforceable` before 2027-05-13 |
| RBI-OMB-ESCALATION | escalation_required | trigger (facts rejected / unsatisfied / days_without_reply >= 30) and no RBI CMS / Ombudsman route, or route negated | product or trigger unknown; trigger from text only | `not_applicable`: not lending, or facts show no trigger |
| SEBI-NO-ASSURED-RETURNS | must_not_claim | live assured/guaranteed/risk-free/pakka/minimum/target return or percentage-accuracy wording (EN, Hinglish, Devanagari, common typos) | claim only inside a question; `fixed returns`, `double your money`; claim next to a government guarantee; bare `guarantee` in an investment context | negated/warned/disclaimed wording passes; `not_applicable` without investment context |
| NPCI-UPI-MASK-IDENTIFIERS | forbidden pattern | unmasked UPI ID (known PSP handle), `+91`/grouped mobile, 10-digit mobile or 9-18 digit account number with a positive cue | unknown `@handle`; digit run with no cue | policy below |

Mask false-positive policy: masked forms (`***`, `xxxx`, bullets) pass; e-mail addresses (dot in the domain) are not UPI IDs; digit runs next to reference cues (UTR, RRN, txn, ref, order, ticket, OTP, amount, ₹, support/helpline numbers) are ignored; the closest cue before the number decides; letters glued to digits (`T26103...`) mean an id; < 9 digits is never an account number; a bare 10-digit or 12-digit number with no cue is `review`. There is no echo exemption: an agent repeating the customer's own number is still flagged (the circular covers all customer-facing communications; compliance may want a different rule).

Compensation is one shared predicate (`phrases.comp_elements`) used by COMP-100 and both TAT cards, so they cannot disagree about a sentence: it needs Rs100 and a per-day wording (`per day`, `each/every (extra) day`, `har din`, `प्रति दिन`, `हर अतिरिक्त दिन` ...) in one sentence or two adjacent ones, plus an automatic/no-claim wording.

## Scores (honest)

`pytest tests/engine -s` prints these; run from `apps/api` with `PYTHONPATH=. pytest tests/engine --confcutdir=tests/engine -p no:cacheprovider` (the parent `tests/conftest.py` needs sqlalchemy; the engine tests do not). 473 tests.

Corpus: 356 labelled cases in `apps/api/tests/engine/labelled/*.jsonl` (128 test, 228 dev). The **test split was written first** (before any engine code) and then frozen (verified byte-identical at the end); matchers were tuned on **dev** only. Test mismatches were looked at once, for reporting; no matcher was changed in response to them.

| Card | dev n | dev acc | test n | test acc | test fail precision / recall |
| --- | --- | --- | --- | --- | --- |
| RBI-TAT-UPI-TRANSFER | 40 | 100% | 20 | 100% | 100% / 100% |
| RBI-TAT-UPI-MERCHANT | 35 | 100% | 20 | 100% | 100% / 100% |
| RBI-TAT-COMP-100 | 19 | 100% | 9 | 100% | 100% / 100% |
| RBI-KFS-LOAN | 11 | 100% | 8 | 100% | 100% / 100% |
| RBI-COOLING-OFF | 17 | 100% | 8 | 88% (7/8) | 100% / 100% |
| NPCI-UPI-CHARGES-PRE | 12 | 100% | 7 | 100% | 100% / 100% |
| DPDP-CONSENT-PURPOSE | 11 | 100% | 8 | 100% | 100% / 100% |
| RBI-OMB-ESCALATION | 11 | 100% | 8 | 100% | 100% / 100% |
| SEBI-NO-ASSURED-RETURNS | 37 | 100% | 20 | 100% | 100% / 100% |
| NPCI-UPI-MASK-IDENTIFIERS | 35 | 100% | 20 | 95% (19/20) | 100% / 100% |
| **all** | 228 | 100% | 128 | 98% (126/128) | 100% / 100% |

Test mismatches (2 of 128): both are arguably label errors by the author, left unedited:

* `NPCI-UPI-MASK-IDENTIFIERS-test-13` "Reference number 4561237890 ..." labelled `review` ("no cue") but the text contains the cue "Reference"; the engine says `pass` per its stated policy.
* `RBI-COOLING-OFF-test-08` Hindi paraphrase labelled `review` ("engine abstains unless a matcher exists") but a Hindi matcher was written; the engine says `pass`, which is the correct reading of that sentence.

**These numbers overstate real accuracy.** The same person wrote the test split and the engine design, so the test split is not independent. A better estimate is first-contact agreement on 89 *novel* probe texts I wrote after the engine existed: 7 disagreements (about 92% agreement), of which about 3 were my expectation being wrong. Those disagreements were fixed and added to dev as `*-dev-pNN`. After API integration the coordinator found three more bugs (false fail on `For each extra day, ₹100 ...`; COOLING-OFF `not_applicable` despite facts; tier string), now `*-dev-rNN` regression cases. A native-speaker, independent annotator set is the real next measurement.

## Known limitations / failure modes not fixed

* **Hindi / Hinglish / typo variants are engineering-authored and unreviewed** (`matchers_unreviewed: true`); a native-speaker compliance review is required before any card is activated. Spelling variants not in the lists (for example another transliteration of `paanch`) are missed, which degrades to `review`/`pass` rather than a wrong `fail` in most paths, but a missed *violation* can surface as `pass` (SEBI, MASK).
* Relative words are anchored to T, not to when the agent writes; "tomorrow" said on day 3 is read as day 1.
* An initiation statement phrased unlike the matchers ("we will start the refund today") is read as a same-day crediting promise (`review`).
* If a reply states both rows' rules ("T+1 for transfers, T+5 for merchants") the TAT card for one row will fail on the other row's number. No clause-level row attribution yet.
* No implied-guarantee, tone, or paraphrase understanding (Tier B). "Your money will double" is only `review`; "safe like a bank deposit" is `pass`.
* Row inference from text cues is deliberately narrow: replies with neither cue are `review` even when a human would know. Brand names (Zomato, Amazon) are not cues.
* KFS: `repayment schedule` counts as the amortisation schedule; language detection is keyword-only; Annex A fields are not checked (card says unread).
* MASK: `UPI id`-shaped tokens with an unlisted PSP handle are `review`; card numbers (16 digits) with no cue are `review`; the regexes for mask detection live in `payments.py`, not in the card (only handles and cues are in config). The card's own `forbidden_patterns` regexes are not used as-is: they match e-mail addresses and every 12-digit UTR.
* DPDP notice completeness, KFS sequencing/language-understood, OMB wording adequacy, SEBI implied guarantees are Tier B.

## What Tier B must handle later

Every `review` with `tier: "B"`: DPDP notice elements (data and purpose, rights incl. withdrawal, complaint to the Board) and comparable-ease reasoning; KFS provided before the contract, language understood, validity vs tenor when unknown; COOLING-OFF paraphrases, and whether the agent states the lender's *actual* period; OMB adequacy of the escalation wording and trigger when only text exists; SEBI implied/oblique guarantees, `fixed returns`, `double your money`, government-guarantee statements; COMP-100 paraphrases the matchers do not know. Tier B must quote verbatim text for any `fail`, and may only escalate a Tier A `review`, never override a Tier A `fail`/`pass` silently.

## Contradictions noticed between cards, contract and quotes

* `PLATFORM-BUILD.md` example shows `RBI-TAT-UPI-MERCHANT` **fail** on "it will be back tonight"; the card says an unconditional same-day/next-day promise is **review** and only `T+1` applied to a merchant payment fails. Engine follows the card.
* `RBI-OMB-ESCALATION` is `tier: B`, `deterministic: false`, but the engine implements the facts-driven trigger and route check in Tier A (pass/fail/not_applicable) and abstains with `tier: "B"` where facts are missing.
* `RBI-COOLING-OFF` `must_not_convey` "no cancellation once disbursed" is only wrong *within* the cooling-off period (quote: exit "during an initial cooling-off period"); the engine exempts "after the cooling-off period ends".
* `NPCI-UPI-MASK-IDENTIFIERS.forbidden_patterns`: the account regex `\d{9,18}` also matches UTR/RRN (12 digits) and 10-digit mobiles; the UPI regex matches e-mail addresses; the mobile regex misses grouped `98765 43210`.
* `RBI-TAT-COMP-100` mentions "per day of delay" from each row's deadline; `facts.delay_days` is undefined in the contract (read here as elapsed days since T).
