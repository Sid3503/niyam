# Niyam web console

React 19 + Vite + TypeScript + Tailwind v4, React Router, TanStack Query. Reuses the Niyam light rail
(`src/components/ui/sidebar.tsx`, copied from the earlier `niyam-web`) and the warm-taupe tokens (`src/index.css`, see `/DESIGN.md`).

Public landing page at `/` (no app shell). App screens: Overview (`/overview`), Documents (`/library`, + document review at `/library/:id`), Rules, Impact, Counsel approvals (`/approvals`), Evidence, plus Settings (API key and your name). Rail groups: Pack (Overview, Documents, Rules, Impact) and Decide (Approvals, Evidence). Contract: `/docs/REVAMP-CONTRACT.md`.

## Run

```bash
npm install
npm run dev          # http://localhost:5173, proxies /api and /healthz to http://localhost:8000
npm run build        # tsc -b && vite build  -> dist/
npm test             # vitest: status mapping, redline diff, clause highlighting, Approvals decision flow, landing, Overview ribbon and clock helper (mocked fetch)
```

Set `NIYAM_API_TARGET=http://host:port` to point the dev proxy elsewhere.

## API

Base path `/api/v1` (contract: `/docs/PLATFORM-BUILD.md`). If the server sets `NIYAM_API_KEY`, paste the key in
Settings; it is stored in `localStorage` (`niyam.apiKey`, access wrapped in try/catch) and sent as `X-API-Key`.
A 401 shows a "Not authorised" state with a link to Settings.

## Honest-labelling rules enforced in the UI

- Drafts show `draft` / "pending approval" (amber); only `active` rules are green. Approver and date show once active.
- Finding status chips: only `current` is green; `missing` is amber and never green. A clause is green only when it has a `current` finding.
- Every finding shows its quote, rule id + version (opens the rule drawer via `?rule=`) or product fact id, and confidence.
- Product facts are labelled "Paytm-controlled demo data"; documents "Synthetic demo document".
- "The original document is never changed" banner on document review.
- Settings stores the API key and actor name in `localStorage`, sent as `X-API-Key` / `X-Actor`.
- Footer on every screen: "Decision support, not legal advice. Demo documents and product facts are synthetic."
- The Overview clock is labelled "measured in this demo workspace"; the landing page's "two weeks across forty templates" is labelled an illustrative story, not a measurement.

## Docker

```bash
docker build -t niyam-web apps/web                         # real API
```

`nginx.conf` serves the SPA (history fallback), proxies `/api/`, `/healthz`, `/readyz` to `http://api:8000` (resolved lazily via Docker DNS),
gzips, caches `/assets/*` for a year, never caches `index.html`, and sets CSP (`script-src 'self'`, no eval; `style-src` allows inline because
the sidebar injects a style tag), `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`. `/nginx-health` is the container healthcheck.

## Layout

```
src/lib/        api.ts (fetch + TanStack hooks), types.ts (contract), highlight.ts, clauses.ts, redline.ts, settings.ts, format.ts, download.ts
src/components/ AppShell, Badges, Drawer, RuleDrawer, Redline, Notice, States, Filters, Page, ui/sidebar.tsx
src/pages/      Overview, Library, DocumentReview, Rules, Impact, Approvals, Evidence, Settings
```
