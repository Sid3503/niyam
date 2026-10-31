# Niyam — Assurance Console (React)

The Niyam sidebar, integrated as a real React + TypeScript + Tailwind v4
component, wired to the same information architecture as the HTML console
(Overview → Circulars → Rule cards → Swarm runs → Verdicts → Fixes → Releases →
Evidence).

```
niyam-web/
├─ components/ui/
│  ├─ sidebar.tsx        ← the supplied component (copied verbatim, one edit: icons)
│  └─ sidebar-demo.tsx   ← Niyam wiring: brand, routes, badges, footer, demo shell
├─ lib/utils.ts          ← cn()
├─ src/
│  ├─ index.css          ← Tailwind v4 + Niyam tokens + .rail-dark
│  ├─ main.tsx
│  └─ App.tsx
├─ components.json       ← shadcn config (aliases → @/components/ui)
└─ vite.config.ts        ← "@" → project root
```

## Run it

```bash
cd niyam-web
npm install
npm run dev      # http://localhost:5173
npm run build    # tsc -b && vite build
```

## What changed vs. the supplied source

| Change | Why |
| --- | --- |
| `cn` imported from `@/lib/utils` | shadcn convention; one implementation, not two. |
| `@tabler/icons-react` → `lucide-react` | Project icon library, per the integration brief. Only three glyphs were used (`ChevronRight`, `PanelLeftOpen`, `PanelLeftClose`). |
| Fonts + tokens moved out of the component | Styling belongs in `src/index.css` so the component stays portable. |

Everything else — the `useRender` asChild path, the memoised collapse context,
the gliding `layoutId` active pill, `useReducedMotion` gating, the resizable
handle, keyboard support — is untouched.

## Colour

The palette lives in `src/index.css` and mirrors `../DESIGN.md`: warm taupe
`#A18A7D` for the mark and icons, deep taupe `#786253` for primary actions,
off-white `#FAF9F7` canvas, white surfaces, and `#16845B / #B7791F / #D64545`
reserved for compliant / review / violation states. The sidebar uses the
`.rail-light` skin so it reads as part of the page rather than a dark object.

## Answers to the integration questions

**What data/props does it take?** `sidebar.tsx` is a compound component:
`<Sidebar variant="collapsible" width collapsedWidth>` owns state and exposes it
to `SidebarHeader/Nav/Section/Item/Nested/Footer/Toggle` through context.
`SidebarItem` takes `icon`, `active`, `badge`, `href`/`external`, `asChild`,
and all button props. `useSidebar()` reads `{ collapsed, toggleCollapsed }` for
custom header/footer content. `sidebar-demo.tsx` adds the Niyam layer: a route
union (`RouteId`), a route table with icon + badge + rail dot, and `active` /
`onSelect` callbacks.

**State management?** Local only — no provider or store needed. The demo holds
`active` and `collapsed` with `useState`; `collapsed` is controlled so the
viewport rule can drive it (tablet and below start on the logo rail, and widen
back on resize). Drop the controlled props to use the component's internal
state instead.

**Assets?** None. The Niyam mark is an inline SVG (`NiyamMark`), so it inherits
`currentColor` and stays crisp at rail size. `public/favicon.svg` is the same
mark on the ink tile. No remote images are referenced.

**Responsive behaviour?** 264 px expanded ↔ 76 px collapsed, 240 ms width
transition. At ≤1024 px the demo defaults to the rail; at rail width the toggle
is hidden and the header becomes the expand button (click, `Enter`, `Space`).
Nav rows shrink to 40 px centred targets and badges become status dots, since a
count badge has nowhere to sit. Below ~380 px the main pane's cards go 2-up and
the table scrolls horizontally.

**Where should it live in the app?** As the app shell: render `<NiyamSidebar>`
once, next to a router outlet, and pass `active` from the route plus
`onSelect` → `navigate()`. The demo's `MainPane` stands in for that outlet.

## If you are starting from an empty (non-shadcn) project

This repo is already set up, but the same result from scratch:

```bash
# 1. Vite + React + TS
npm create vite@latest my-app -- --template react-ts
cd my-app && npm install

# 2. Tailwind v4 (no tailwind.config.js, no PostCSS config needed)
npm install tailwindcss @tailwindcss/vite
# vite.config.ts → plugins: [react(), tailwindcss()]
# src/index.css → @import "tailwindcss";

# 3. shadcn CLI
npx shadcn@latest init          # style: new-york, base colour: stone, css vars: yes
```

`shadcn init` writes `components.json` and, for a non-Next project, points the
`@` alias at your source root. **Check `tsconfig` before you copy anything in:**

```jsonc
// tsconfig.app.json
{
  "compilerOptions": {
    "paths": { "@/*": ["./*"] }   // root-level aliases (this repo's choice)
  }
}
```

```ts
// vite.config.ts — must match the tsconfig paths
resolve: { alias: { "@": fileURLToPath(new URL("./", import.meta.url)) } }
```

Then add the runtime dependencies:

```bash
npm install framer-motion @base-ui/react clsx tailwind-merge lucide-react
```

and drop `sidebar.tsx` into `components/ui/`.

> TypeScript 7 note: `baseUrl` was removed, so `paths` must be relative to the
> tsconfig itself (as above). Also add `src/vite-env.d.ts` with
> `/// <reference types="vite/client" />` or the CSS side-effect import errors.

## Why `/components/ui` matters

`components.json` is the contract the CLI reads:

```json
"aliases": { "components": "@/components", "ui": "@/components/ui", "utils": "@/lib/utils" }
```

`npx shadcn@latest add button` resolves `ui` → `components/ui` and writes
`button.tsx` there, importing `cn` from `@/lib/utils`. If this component lives
elsewhere, every future `add` produces a second tree, and two copies of shared
primitives drift apart. Keeping `sidebar.tsx` at `components/ui/sidebar.tsx` and
`cn` at `lib/utils.ts` means the CLI keeps working and the import path never
changes.

This project aliases `@` to the repo root (not `./src`), so `@/components/ui/sidebar`
is literally `components/ui/sidebar.tsx`. If you prefer the shadcn default
(`@` → `src`), move the folders under `src/` and update both `paths` and the Vite
alias — the component imports are unaffected.

## Using the sidebar elsewhere

```tsx
import { Sidebar, SidebarHeader, SidebarItem, SidebarNav, SidebarSection, SidebarToggle, useSidebar } from "@/components/ui/sidebar";

<Sidebar variant="collapsible" width={264} collapsedWidth={76} className="rail-dark">
  <SidebarHeader>
    <Logo />                      {/* collapse-aware via useSidebar() */}
    <SidebarToggle className="ml-auto" />
  </SidebarHeader>
  <SidebarNav>
    <SidebarSection label="Workspace">
      <SidebarItem icon={<Gauge size={17} />} active>Overview</SidebarItem>
    </SidebarSection>
  </SidebarNav>
</Sidebar>
```

Variants: `default`, `collapsible`, `icon-rail` (always 60 px, no toggle),
`floating` (inset card with shadow), `resizable` (drag or arrow-key resize,
double-click to reset).
