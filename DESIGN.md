# Niyam — colour system

Warm taupe for identity, off-white canvas, charcoal text. Green, amber, red and
blue appear only where a compliance state is being reported.

## Tokens

| Token | Hex | Used for |
| --- | --- | --- |
| `--paper` | `#FAF9F7` | Page canvas |
| `--card` | `#FFFFFF` | Cards, tables, modals, drawers |
| `--hover` | `#F5F1ED` | Hover surfaces, neutral chips, table header strips |
| `--sand` | `#E9E2DC` | Selected nav, active pill, avatars |
| `--ink` | `#1C1B1A` | Headings, primary text |
| `--body` | `#3F3B38` | Nav labels, body copy |
| `--mute` | `#77716C` | Descriptions, metadata |
| `--faint` | `#948C85` | Tertiary labels |
| `--line` | `#E9E4DF` | Dividers, card outlines |
| `--taupe` | `#A18A7D` | Logo mark, nav icons, brand accents |
| `--taupe-strong` | `#786253` | Primary buttons, active icon, eyebrow |
| `--focus` | `#B8A397` | Keyboard focus ring |
| `--ok` | `#16845B` | Compliant, compiled, released, deployed |
| `--warn` | `#B7791F` | Review, pending approval, gate warning |
| `--bad` | `#D64545` | Violation, failed verdict, blocking gate |
| `--info` | `#3975B7` | Informational only |

Tints are derived per state rather than added as new palette entries:
`#EDF6F2 / #CBE4D8` for success, `#FBF3E4 / #EDDCBE` for warning,
`#FBEDED / #F0CCCC` for critical.

## Where it lives

**Console** — `niyam-console/styles.css`, `:root`. Legacy aliases (`--verm`,
`--lime`) resolve to the semantic tokens so inline view styles keep working.
The sidebar is a light rail (`--rail: #FBFAF8`) with a hairline border, a sand
active pill, and taupe icons.

**React** — `niyam-web/src/index.css`. The same values are mapped onto the
shadcn contract (`--background`, `--foreground`, `--primary`, …) plus the
`--primitive-*` layer the sidebar reads. The `.rail-light` class carries the
rail-specific overrides.

## Rules applied

- 90% of every screen is neutral. Taupe is limited to the mark, nav icons,
  primary actions, progress bars and the eyebrow.
- Red, amber and green only mark an outcome: verdict state, fix approval, run
  failures, gate readiness, release status.
- Input style (English / regional / code-mixed) is a fact about the message,
  not an outcome — it uses the neutral `tag` pill.
- No gradients, no saturated AI accents, no heavy shadows. Elevation is a
  1px border plus a shadow under 5% opacity.
- Numbers are set at 500 weight; headings stay at 300–400 for the editorial
  voice. Raleway carries everything except console, diff and YAML surfaces,
  which stay in JetBrains Mono.

## Entry and roles

The console opens on `#/welcome` unless the tab already has a session. The
screen does two jobs at once: the pitch sits on the left, the workspace and
role picker on the right. There are no credentials.

- **Compliance lead** — Aarav Mehta. Approve fixes, run the swarm, promote a
  release.
- **Auditor** — Nisha Rao, read-only. Can inspect verdicts, fixes, rules and
  the evidence pack; cannot approve, release or start a run.

`canAct()` in `app.js` is the single permission check. `writeBtn()` renders
write controls; for the auditor it swaps them to a lock icon and routes the
click to a `denyWrite()` toast. Locked controls use the neutral `--hover`
surface and taupe text — a permission boundary is not an error, so it never
borrows red.

The session lives in `sessionStorage` under `niyam.session.v1`. Deep links
(`#/verdicts`, `#/releases`, …) bypass the gate and seed a lead session so a
judge can open the console directly. Sign out returns to `#/welcome` with the
last role still selected; Switch role preselects the other seat, so seeing both
sides of the gate is two clicks.

## Intro motion

The landing opens on the mark drawing itself at the centre of the canvas, then
hands over to the two-column gate. The geometry is the real logo — the same
three paths as the rail — so nothing is redrawn by hand.

| Beat | Time | What happens |
| --- | --- | --- |
| 01 Point | 0.0s | A dot appears at the start of the first stroke, with a soft glow |
| 02 First stroke | 0.2s | The left stem rises, turns, and draws the upper diagonal |
| 03 Shape forms | 0.8s | The lower diagonal and its curve complete the N |
| 04 Final stroke | 1.4s | The right stem draws upward |
| 05 Spark | 1.8s | The four-point star scales in |
| 06 Wordmark | 2.0s | "Niyam · Assurance console" fades up |
| 07 Glow | 2.1s | A single low-opacity pulse settles the mark |
| 08 Handover | 2.7s | The canvas fades, then the landing rises in |

The draw is driven by `getTotalLength()` and `getPointAtLength()` in
`app.js`, so the leading dot rides the exact path and the stroke lengths never
need hard-coding. Every stroke fades its head in and out, which reads as a pen
lifting between segments.

The intro plays once per page load at `#/welcome` only. Deep links, a tab that
already holds a session, and sign-out from inside the console all skip it.
Any click, `Enter`, `Space` or `Escape` skips to the finished lockup, and
`Skip intro` appears after 0.8s. `prefers-reduced-motion: reduce` removes the
intro entirely — the landing renders as it did before.

## Overview

The overview is a working surface, not a dashboard of tiles. It answers one
question — *may this build ship?* — and then shows the evidence that decides it.

**Gate spine (left).** The release gate is the first thing on the page: build,
state, and the one number that moves during the demo. Below it, six steps trace
the product's actual pipeline — circular ingested, rule cards compiled, swarm
run, verdicts filed, fixes approved, release gate. The current step carries a
slow pulse and, when the gate is shut, a red `blocked here` flag on the step
that is holding it. Each step is a button to its view, so the spine doubles as
navigation. Live Guard latency sits at the foot as a budget, not a headline.

**Live ledger (right).** Rows, not cards. Each open failure carries an ID, a
severity dot, the rule and persona, the surface, the input style and the
judge's confidence. Severity filters re-cut the list in place. Approving F-217
marks the refund row closed in green and drops the count from 17 to 3 while the
pass rate counts up to 96 — the change the judge just caused is visible in the
same surface.

**Footnotes.** Below the fold, three ruled columns hold the thesis evidence:
the input-style gap (91 / 68 / 52), the latest circular and its obligations,
and the audit trail. They are deliberately below the first screen — the gate
and its failures own the fold.

Rules for this screen:

- No KPI grid. Numbers sit in the spine and the ledger, where they are read in
  context.
- Hairlines, not nested cards. One white sheet, ruled rows, no shadows.
- Colour only on severity, gate state and the closed row.
- The page must fit the fold at 1440×900; anything that does not is evidence,
  and evidence goes below.
