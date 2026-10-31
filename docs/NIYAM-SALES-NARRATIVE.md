# Niyam sales narrative

**Status:** GTM story, **31 October 2026**. This is the door we sell through. The engine, rule cards, and human gates in the other docs stay the same.

**Sibling docs:** [`REVAMP-CONTRACT.md`](./REVAMP-CONTRACT.md) (document-review API and screens), [`NIYAM-PDF-WORKBENCH.md`](./NIYAM-PDF-WORKBENCH.md) (in-browser apply on a PDF copy), [`NIYAM-END-TO-END.md`](./NIYAM-END-TO-END.md) (full product loop), [`ENGINE.md`](./ENGINE.md) (what actually flags a clause), [`NIYAM-PRODUCTION-ARCHITECTURE.md`](./NIYAM-PRODUCTION-ARCHITECTURE.md) (what scales). Demo library: `library/` (Bluecart proposal/agreement, Sunrise order form, onboarding brochure and checklist).

Footer on every screen and leave-behind: *Decision support, not legal advice. Demo documents and product facts are synthetic.*

---

## 0. The line

**Proposals and brochures stop shipping claims that are out of date, and you can see when a fix is approved.**

That is the whole pitch, and the only one we lead with. It is written for the people who send the documents: sales ops and merchant onboarding.

How it is true: when a new RBI or NPCI circular lands, Niyam checks every customer-facing document against cited rules and your approved product terms, drafts the corrected wording, and shows the fix moving from drafted to **approved by a named person**. The original file is never changed. The evidence file for audit is a by-product, not the headline.

*Decision-support detail we say second, never first:* a reviewed redline pack for every document, a named lawyer on every approval, an evidence file for audit. Counsel keeps the signature; Niyam saves the hunt and the first draft.

Niyam is a **sales-ops teammate that keeps proposals, brochures and agreements current with the rules**, with a named approver on every fix. It is not a chatbot, not a contract generator, not an agent builder, and not legal advice.

> **Positioning change, 31 Oct 2026.** Earlier drafts led with legal ops and the General Counsel. The lead audience is now sales ops and onboarding, because they are the ones who feel a stale deck going out, and "you can see when a fix is approved" is something they watch. Legal and counsel stay in the product as the named approvers; they are a required seat, not the lead message.

---

## 1. Why this door

Legal already has a budget, a queue, and a fear of stale paper. Agent red-teaming often does not.

A circular lands. Counsel spends days finding which proposals, agreements, brochures, and order forms still say the old TAT, the old fee line, the old cooling-off sentence. They redline Word files by hand. Sales keeps pitching the stale deck. Audit asks who looked.

Niyam:

1. **Finds** the line, against a cited rule, with a quoted span.
2. **Drafts the delta** — suggested wording, original file untouched.
3. **Waits for a named human.**
4. **Re-tests** the pack.
5. **Exports evidence.**

That is the revamp loop: `source → rule → scan → review → approve → re-test → evidence`. Six screens: Overview, Library, Rules, Impact, Approvals, Evidence.

The Product Guide already warned that judges will see a developer tool. This story is a GC / legal-ops tool. Same obligation graph. Different buyer.

---

## 2. Who buys

| Seat | Job | What they see |
| --- | --- | --- |
| **Sales ops / merchant onboarding** (lead audience, daily user) | Send proposals and brochures that do not say something out of date | Documents list with open findings and **fix status** (drafted, waiting, approved by whom), suggested wording, re-test result |
| **Counsel / compliance** (the named approver; a required seat) | Approve the rule and each fix | Approvals queue, the quote and the cited rule |
| **Legal ops** (runs the circular intake) | A circular landed; which documents break? | Add circular, impact, hours-to-pack |
| **GC / business head** (economic buyer) | Capacity and audit fear | Evidence pack, named approver, tamper-evident log |

Lead with the first row. The approver is why "approved" means something, so keep that seat visible, but do not open the pitch with it.

Do not open with “bot owners” or “release gates.” Those seats are expansion (same rules on chat, macros, voice).

---

## 3. The five-minute demo

Use the synthetic Bluecart / Sunrise pack. Say **synthetic** out loud.

1. **Library.** Open the Bluecart payment-gateway proposal. It still promises 7-working-day UPI reversal, “no hidden charges,” “assured returns of 12%,” “no KYC hassles.”
2. **Scan.** Findings land as `outdated` / `missing` / `contradiction`, each with a quote and a card. Merchant UPI TAT is **T+5**, not T+1 or 7 working days. SEBI: no assured returns. NPCI: UPI fee cannot be a surprise after mode selection.
3. **Fix draft.** Suggested wording appears. The original document is **never modified**; a new version is a copy.
4. **Approve.** Named actor (counsel) approves the fix. A draft rule is never `active` until this click.
5. **Apply (PDF workbench).** Open the copy in the canvas, click the finding, apply the T+5 wording in place. Preview check; commit version 2. Original bytes stay put. See [`NIYAM-PDF-WORKBENCH.md`](./NIYAM-PDF-WORKBENCH.md).
6. **Re-test.** Those findings close; leftovers stay open. `passed` is honest.
7. **Evidence.** Export the pack: two SHA-256s, page diff, quotes, rule versions, approver, re-test, hash chain.

Put a **clock** on the story: “this used to be two weeks across forty templates.” Do not lead with models, websockets, or 60 conversations.

Optional close (one sentence, not a second demo): *Once the clause is approved, the same rule can sit in front of the agent.* Then stop.

---

## 4. What we sell vs what we are not

| We sell | We are not |
| --- | --- |
| Hunt + first-draft redline + audit trail on **the customer’s own library** | Harvey / Spellbook (AI writes the MSA) |
| Cited Indian FS rules as executable checks | A circular tracker with a task list |
| Hours, not weeks, after a circular | A replacement for counsel |
| Decision support with a named approver | Legal advice |
| Evidence a second reviewer can follow | Autocomplete for lawyers |

“Drafting docs” in this product means **draft the delta on the clause that failed the rule**. It does not mean generate a full agreement from a prompt.

Suggested wording reaches Approvals only if Tier A **re-checks the new text** (`suggested_fix.validated`). Unvalidated drafts stay in review.

---

## 5. Claims we may make (and how)

Say, after checking the live demo:

- A circular becomes a **cited finding list** across the document library.
- Each finding has a **verbatim quote**, a rule id and version, and a confidence.
- The original file is **untouched**.
- A **named human** activates rules and approves fixes.
- Re-test compares before/after on the same document.
- The evidence pack is **hash-chained** and exportable.
- Demo data is **synthetic** and labelled.

Do not say:

- Competitors are English-only; nobody tests before release; we are the only ones.
- FREE-AI is binding (it is a committee report, 13 Aug 2025).
- 71% → 96%, 11 minutes, 60 conversations as if they were Paytm production. Those are **PayDemo agent-test targets** from the old pitch. Wrong headline for this motion.
- Niyam writes contracts. Niyam replaces legal. Niyam is legal advice.
- Live Indic voice as a current capability.

Market and ARR figures in `NIYAM-END-TO-END.md` §2.7 must be re-checked before a buyer meeting. Do not lead with them in this motion.

---

## 6. Metrics on the Overview screen

Lead with what a sender needs to know (can I send this, and is the fix approved?), then the intake and audit numbers:

| Metric | Meaning |
| --- | --- |
| Documents scanned | Library coverage this period |
| Open findings | Documents that still say something out of date |
| Fixes awaiting approval | Fixes drafted but not yet approved by a named person |
| Documents with no open findings | The ones you can send. Say "no open findings", never "safe" or "compliant" |
| Rules pending approval | Circulars not yet turned into checks |
| Citation coverage | Share of findings that carry a verified quote |
| Hours from circular to approved pack | The time story (demo target; label it) |

Keep agent pass-rate, swarm size, and Guard p95 for a later SKU slide.

---

## 7. Pricing motion (indicative)

Land: **one product line, one circular, one library, one evidence pack**, live in a week.

Subscribe: seats for legal ops + counsel, priced on **document surfaces** (proposal set, agreement set, brochure set, onboarding kit) rather than on “agents.” Indicative band in the product guide (₹50k–1.5L / surface / month) can be reused if re-validated; say “indicative.”

Expand:

1. Every merchant template in the line.
2. Every circular that legal already tracks.
3. Same rules on sales macros, support scripts, then the agent (Live Guard).
4. Attach to Paytm Pi: every deployed agent ships with a Niyam pack — **second sentence**, not the first.

---

## 8. Competitive frame

Generic legal AI drafts from a prompt and hopes. Circular trackers assign tasks. Agent testers simulate calls.

Niyam starts from a **named Indian rule**, runs it against **this company’s documents**, drafts the **clause-level** change, and leaves a pack another reviewer can follow.

The defensible sentence: *cited Indian rule → executable check → finding on your library → scoped redline → named approval → re-test → evidence.*

---

## 9. What stays true from the rest of the product

- Obligation graph is the durable asset, not the LLM.
- Sarvam reads and drafts; Niyam verifies; a human activates.
- Tier A is deterministic and fail-closed. Empty evidence is `review`, never `pass`.
- AI never activates a rule, publishes a fix, or promotes a release.
- Voice, `/think`, Live Guard, persona swarm: **same checks on spoken and chat copy**, phase 2. Architecture: [`NIYAM-PRODUCTION-ARCHITECTURE.md`](./NIYAM-PRODUCTION-ARCHITECTURE.md) — api-control + workers + engine is the revenue path; api-hot Guard and voice-relay are the second SKU.

---

## 10. Talk track (about 90 seconds)

> Your proposals and brochures keep going out with claims that were true last quarter: the old refund time, the old fee, a settlement promise nobody can keep. When a rule changes, nobody tells the people who send them.
>
> Niyam reads every proposal, agreement and brochure against the cited RBI and NPCI rule and your approved product terms. It shows you the exact sentence that is out of date and drafts the corrected wording. Then you watch the fix move from drafted to approved, by a named person, so you know which version is the one to send. The original file never changes.
>
> Counsel keeps the signature, and there is an evidence file if anyone asks later. Once that wording is approved, the same rule can sit in front of the agent. Today we are showing you the documents your team already ships.

---

## 11. Leave-behind checklist

- One-pager with the core pitch in §0 and the six-step loop.
- Screenshot: Library row → findings with quotes → Approvals with a name → Evidence export.
- Footer: decision support, synthetic demo data.
- No swarm chart on page one.
