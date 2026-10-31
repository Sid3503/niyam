# Design delta: web console vs. earlier console designs (`_ref/screens`)

For syncing the Open Design project "Niyam - Assurance Console". Tokens, fonts (Raleway / JetBrains Mono), the light rail and its collapse behaviour are unchanged.

## Information architecture

| Earlier | Now |
| --- | --- |
| Overview, Circulars, Rule cards, Swarm runs, Verdicts, Fixes, Releases, Evidence | Overview, **Check**, Rule cards, **Knowledge base**, **Sources**, **History** (+ Settings via the footer gear) |
| Rail sections Workspace / Review / Audit | Workspace (Overview, Check) / Library (Rule cards, Knowledge base, Sources) / Audit (History) |
| Rail badges: live dot, red verdict count, warn dot | Only a neutral rule-card count. No alert dots: there is no gate or failure queue |
| Rail footer: PayDemo Staging + user avatar (roles) | PayDemo (+ "Mock API" when mock) and a Settings gear. No welcome gate, roles, or intro animation |
| Top bar: search palette (cmd-K), export, Run swarm | Breadcrumb + `mock api` / `PayDemo · synthetic` chips. No palette, export or swarm action |

## New screens

- **Check** (core): example presets row, message textarea, collapsed "Facts" form (surface, journey, transaction type, delay days, product, language, convenience fee, as-of, complaint-state fieldset), Run check, then verdict cards sorted fail > review > pass > not yet enforceable > not applicable.
- **Knowledge base**: search + regulator / document type / status / as-of filters, hit list with highlighted snippets, unit drawer with previous/next neighbours.
- **Sources**: documents table + outline drawer.
- **History**: table of runs with summary chips; opening a row re-renders its verdicts on the Check screen (`/check?run=<id>`).
- **Settings**: API key field.

## Changed screens

- **Overview**: no gate spine, ledger or KPI-of-pass-rate. Now: prominent amber "all rule cards are DRAFT, none approved" notice, four stat tiles (documents, units, rule cards, not yet enforceable), KB by regulator / provenance bars, rule cards by status / enforceability / severity bars, last 5 checks. Bars are single-colour taupe.
- **Rule cards**: card grid replaced by a filterable table (id + title, status, severity, tier, check type, effective date + enforceability chip, provenance + OCR, open issues). Drawer: draft warning, obligation, applicability, check configuration (scalar summary + collapsible YAML-ish mono view), source with provenance and "quotes verified" tick, validation warnings, open issues, notes, aliases (old demo ids). No pass-rate bar, no "Test this rule".

## New components

- **Verdict card**: left border in the verdict colour, rule id + version + title, verdict chip, confidence, draft badge, tier tag, matched text with highlighted span (fail = red underline wash, review = amber, pass = green) and char range, reason, per-check list (name, result chip, detail), collapsible "Cited source" (document, reference + locator, regulator quote, provenance + OCR badge, file path). Not-applicable and not-yet-enforceable cards start collapsed.
- **Summary chip row** (count per verdict state) and the disabled **"Send to compliance reviewer · coming soon"** button.
- **Chips**: verdict (green/amber/red; neutral grey for not applicable / not yet enforceable), status (`draft` amber), provenance (mirror and user_downloaded amber), `OCR`, enforceability (`not yet enforceable · effective <date>`), severity (neutral), tier.
- **Right drawer** (rule, KB unit, document): 680px max, scrim, Esc closes, focus trapped and restored, deep-linkable (`?rule=`, `?unit=`, `?doc=`).
- **Filter bar** (label above select), **term-highlighted snippet**, **unit neighbour cards**, **hairline bar rows**.
- **Notice banners**: amber (draft / mirror source / empty-evidence), neutral (stored-run banner).

## New states

Loading skeletons, empty ("No rule cards match", "No documents match", "No checks yet", "No results for ..."), error with retry, 401 ("Not authorised" with Open Settings), backend unreachable, quote that cannot be located (amber note, nothing highlighted), stored run without text (quote shown without context), disabled stub action, mock-mode chip, mobile (rail collapses to the logo rail at <=1024px, tables scroll horizontally, drawers go full width).

## Removed

Welcome / role picker / intro animation, swarm runs, fixes, releases, evidence pack, circulars, command palette, toasts, pass-rate sparklines and the input-style gap chart.


## Revamp (document-review console)

The product changed from a pre-send message checker to merchant-payment document review (`docs/REVAMP-CONTRACT.md`). Tokens, fonts, light rail, drawers, chips and cards are unchanged.

- **Navigation**: six items, Overview, Library, Rules, Impact, Approvals, Evidence (rail groups Workspace / Decide). The Approvals item carries a pending count. Settings gear stays in the rail footer and now also holds the actor name (`X-Actor`). Document review is not a nav item: it opens at `/library/:documentId` from a Library row.
- **Removed**: Check, Knowledge base, Sources, History, verdict cards, run history, the VITE_MOCK fixture layer and the mock engine.
- **New components**: finding chip (only `current` is green, `missing` amber), document status chip (new / changed / unchanged / reviewed), approval chip, clause block (left border and underline wash by worst finding, click to select), word-level redline (original left with struck deletions, proposed right with insertions), notice banner (neutral / amber), scan-result panel, evidence timeline.
- **Library**: table plus "Scan now" (result panel: discovered / reviewed / skipped) and an "Upload document" drawer.
- **Document review**: two columns. Left, clauses with highlighted spans, a "Missing from this document" block, version list. Right, findings (status, confidence, reason, quoted source with rule id and version linking to the rule drawer or product fact id, drafted wording as redline, Send for approval, Re-test). Re-test is a drawer prefilled with the current text showing before / after and passed or not. Banner: "The original document is never changed."
- **Rules**: tabs "Rule cards" and "Paytm product facts" (labelled Paytm-controlled demo data), "Add circular" drawer (URL or text) that lists the resulting drafts with the source quote beside each. Table shows effective period, approver and date once active, `scan_active`, "pending approval" for drafts.
- **Impact**: rule picker, old vs new side by side, "dry run, rule not active yet" banner, affected documents with matched_on chips, quote, change note, proposed wording, owner task, per-document Re-test.
- **Approvals**: single queue (rules and fixes) in API order, status and kind filters, Approve / Reject / Defer with optional reason, decided items show who and when.
- **Evidence**: per-document list; drawer (`?document=`) with timeline, findings, approvals, re-tests, notifications, chain_ok badge and an Export .md button (fetched with headers, saved via Blob).
- **Deep links**: `?rule=` (rule drawer on any page), `?tab=facts`, `?pick=<rule>@<version>` (Impact), `?document=` (Evidence), `?status=&kind=` (Approvals).
- **Footer**: "Decision support, not legal advice. All documents and Paytm product facts are synthetic demo data."

## Sales shift (31 Oct 2026)

Why: Niyam is now sold to legal ops and counsel as "a circular becomes a reviewed redline pack, with a named lawyer on the approval and an evidence file for audit" (`docs/NIYAM-SALES-NARRATIVE.md`). Agent-testing numbers are gone from every screen.

Note: the Open Design MCP tool was not available in this session, so this redesign was done in code only. No Open Design file was updated; sync it from this section.

- **Landing at `/`** (no rail): bold light-weight hero with the line, six-step loop, a worked example (stale clause, finding, suggested wording, named approval; synthetic and labelled), is / is-not table, audience, an illustrative "two weeks across forty templates" clock (labelled a story, not a measurement), CTA "Open the demo workspace" to `/overview`. Same taupe/ink tokens; one accent (taupe-strong); green/amber/red still only for compliance states. Entry motion and the clock hand stop under `prefers-reduced-motion`.
- **Routing**: Overview moved `/` to `/overview`. The logo and the "Niyam" breadcrumb go to `/`.
- **Rail**: groups Pack (Overview, Documents, Rules, Impact) and Decide (Counsel approvals, Evidence). One neutral counter, on Counsel approvals only. "Library" is labelled "Documents"; the route is still `/library`.
- **Overview** is the circular-to-pack command center: six-step ribbon from `/overview.steps` (done / current / todo, each step links to its route), a large clock card from `pack` (live-ticking until `approved_at`, "Approved in X" after, "Measured in this demo workspace"), documents total / affected / clear, five legal-ops tiles (scanned, open findings, fixes awaiting approval, rules pending approval, citation coverage), one primary next-action button, and the amber note while rules are draft. If the backend has no `steps`/`pack`, steps are derived from the old fields and the clock shows "Not started" (no invented time).
- **Wording**: Impact is "Circular impact: which documents break", Approvals is "Counsel approvals", Rules/Impact/Approvals/Settings/Overview each get a one-line "what happens here / next" strip (`HereStrip`), empty states name the next step, "Paytm" removed from shell copy. Footer: "Decision support, not legal advice. Demo documents and product facts are synthetic."
