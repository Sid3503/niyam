"use client";

/**
 * Niyam — Assurance Console sidebar.
 *
 * Product wiring for the shared <Sidebar> primitive: the Niyam "N + sparkle"
 * mark as the only visible element on the collapsed rail, section-labelled
 * navigation with count badges and an active pill when expanded, and the
 * workspace footer. Everything else in the sidebar comes from
 * components/ui/sidebar.tsx.
 */

import * as React from "react";
import {
  Archive,
  BookOpenCheck,
  FileStack,
  Gauge,
  RadioTower,
  Rocket,
  Stamp,
  Wrench,
} from "lucide-react";

import {
  Sidebar,
  SidebarFooter,
  SidebarHeader,
  SidebarItem,
  SidebarNav,
  SidebarSection,
  SidebarToggle,
  useSidebar,
} from "@/components/ui/sidebar";

/* ─── Brand ─────────────────────────────────────────────────── */

function NiyamMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 100 100"
      fill="none"
      role="img"
      aria-label="Niyam"
      className={className}
    >
      <path
        d="M6 88V25c0-10 11-14 17-6l35 42"
        stroke="currentColor"
        strokeWidth={7}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M41 63l24 24c7 7 16 2 16-8V45"
        stroke="currentColor"
        strokeWidth={7}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M85 9c1.6 7.5 5.5 11.4 13 13-7.5 1.6-11.4 5.5-13 13-1.6-7.5-5.5-11.4-13-13 7.5-1.6 11.4-5.5 13-13Z"
        fill="currentColor"
      />
    </svg>
  );
}

/**
 * Collapsed: the mark alone, centred in the rail. Expanded: mark + wordmark.
 * The header itself becomes the expand affordance when collapsed, so no
 * separate toggle is needed at rail width.
 */
function WorkspaceMark() {
  const { collapsed } = useSidebar();

  return (
    <div
      className={
        collapsed
          ? "flex size-9 items-center justify-center"
          : "flex min-w-0 items-center gap-2.5"
      }
    >
      <NiyamMark className="size-7 shrink-0 text-[var(--taupe)]" />
      {!collapsed && (
        <span className="flex min-w-0 flex-col leading-none">
          <span className="truncate text-[14px] font-semibold tracking-[-0.01em]">
            Niyam
          </span>
          <span className="mt-1 truncate text-[10.5px] font-medium uppercase tracking-[0.09em] text-[var(--muted-foreground)]">
            Assurance console
          </span>
        </span>
      )}
    </div>
  );
}

/* ─── Badges ────────────────────────────────────────────────── */

function CountBadge({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: "neutral" | "alert";
}) {
  return (
    <span
      className={
        tone === "alert"
          ? "rounded-md bg-[#FBEDED] px-1.5 py-0.5 text-[10.5px] font-semibold leading-none tabular-nums text-[var(--bad-ink)]"
          : "rounded-md bg-[color-mix(in_srgb,var(--foreground)_7%,transparent)] px-1.5 py-0.5 text-[10.5px] font-medium leading-none tabular-nums text-[var(--muted-foreground)]"
      }
    >
      {children}
    </span>
  );
}

/* ─── Footer ────────────────────────────────────────────────── */

function WorkspaceFooter() {
  const { collapsed } = useSidebar();

  if (collapsed) {
    return (
      <span className="flex flex-col items-center gap-2">
        <span
          className="size-1.5 rounded-full bg-[var(--ok)]"
          title="Staging · synthetic data"
        />
        <span className="flex size-7 items-center justify-center rounded-full bg-[var(--sand)] text-[10.5px] font-semibold text-[var(--taupe-strong)]">
          AM
        </span>
      </span>
    );
  }

  return (
    <>
      <div className="flex min-w-0 flex-1 flex-col leading-tight">
        <span className="flex items-center gap-1.5 text-[12px] font-medium">
          <span className="size-1.5 shrink-0 rounded-full bg-[var(--ok)]" />
          PayDemo · Staging
        </span>
        <span className="mt-0.5 truncate text-[10.5px] text-[var(--muted-foreground)]">
          Synthetic data only
        </span>
      </div>
      <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-[var(--sand)] text-[10px] font-semibold text-[var(--taupe-strong)]">
        AM
      </span>
    </>
  );
}

/* ─── Nav model ─────────────────────────────────────────────── */

type RouteId =
  | "overview"
  | "circulars"
  | "rules"
  | "runs"
  | "verdicts"
  | "fixes"
  | "releases"
  | "evidence";

type Route = {
  id: RouteId;
  label: string;
  icon: React.ReactNode;
  /** Count / state shown at full width. */
  badge?: React.ReactNode;
  /** Status dot shown on the logo rail, where badges have no room. */
  dot?: "live" | "alert" | "warn";
};

const S = 17;

const dotClass: Record<NonNullable<Route["dot"]>, string> = {
  live: "bg-[var(--ok)] shadow-[0_0_0_3px_rgba(22,132,91,0.14)]",
  alert: "bg-[var(--bad)] shadow-[0_0_0_3px_rgba(214,69,69,0.14)]",
  warn: "bg-[var(--warn)] shadow-[0_0_0_3px_rgba(183,121,31,0.14)]",
};

const workspaceRoutes: Route[] = [
  { id: "overview", label: "Overview", icon: <Gauge size={S} strokeWidth={1.75} /> },
  {
    id: "circulars",
    label: "Circulars",
    icon: <FileStack size={S} strokeWidth={1.75} />,
    badge: <CountBadge>4</CountBadge>,
  },
  {
    id: "rules",
    label: "Rule cards",
    icon: <BookOpenCheck size={S} strokeWidth={1.75} />,
    badge: <CountBadge>8</CountBadge>,
  },
  {
    id: "runs",
    label: "Swarm runs",
    icon: <RadioTower size={S} strokeWidth={1.75} />,
    dot: "live",
    badge: (
      <span className="flex items-center gap-1.5">
        <span className="size-1.5 rounded-full bg-[var(--ok)] shadow-[0_0_0_3px_rgba(22,132,91,0.14)]" />
      </span>
    ),
  },
];

const reviewRoutes: Route[] = [
  {
    id: "verdicts",
    label: "Verdicts",
    icon: <Stamp size={S} strokeWidth={1.75} />,
    dot: "alert",
    badge: <CountBadge tone="alert">17</CountBadge>,
  },
  {
    id: "fixes",
    label: "Fixes",
    icon: <Wrench size={S} strokeWidth={1.75} />,
    badge: <CountBadge>3</CountBadge>,
  },
  {
    id: "releases",
    label: "Releases",
    icon: <Rocket size={S} strokeWidth={1.75} />,
    dot: "warn",
    badge: (
      <span className="size-1.5 rounded-full bg-[var(--warn)]" title="Gate closed" />
    ),
  },
];

const auditRoutes: Route[] = [
  {
    id: "evidence",
    label: "Evidence",
    icon: <Archive size={S} strokeWidth={1.75} />,
  },
];

const allRoutes = [...workspaceRoutes, ...reviewRoutes, ...auditRoutes];

/* ─── Sidebar ───────────────────────────────────────────────── */

/**
 * Nav lives inside <Sidebar> so it can read the real collapsed state: at rail
 * width the rows become 40px centred squares (icon only, pill tight around it),
 * at full width they keep the label + badge layout.
 */
function RailNav({
  active,
  onSelect,
}: {
  active: RouteId;
  onSelect: (id: RouteId) => void;
}) {
  const { collapsed } = useSidebar();

  const render = (routes: Route[]) =>
    routes.map((r) => (
      <SidebarItem
        key={r.id}
        icon={
          collapsed && r.dot ? (
            <span className="relative flex items-center justify-center">
              {r.icon}
              <span
                aria-hidden="true"
                className={`absolute -right-1.5 -top-1 h-1.5 w-1.5 rounded-full ${dotClass[r.dot]}`}
              />
            </span>
          ) : (
            r.icon
          )
        }
        active={active === r.id}
        badge={r.badge}
        className={
          collapsed
            ? "mx-auto h-10 w-10 justify-center gap-0 px-0"
            : undefined
        }
        onClick={() => onSelect(r.id)}
      >
        {r.label}
      </SidebarItem>
    ));

  return (
    <>
      <SidebarSection label="Workspace">{render(workspaceRoutes)}</SidebarSection>
      <SidebarSection label="Review">{render(reviewRoutes)}</SidebarSection>
      <SidebarSection label="Audit">{render(auditRoutes)}</SidebarSection>
    </>
  );
}

export function NiyamSidebar({
  active,
  onSelect,
  collapsed,
  onCollapsedChange,
}: {
  active: RouteId;
  onSelect: (id: RouteId) => void;
  collapsed: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
}) {
  return (
    <Sidebar
      variant="collapsible"
      width={264}
      collapsedWidth={76}
      collapsed={collapsed}
      onCollapsedChange={onCollapsedChange}
      className="rail-light"
      aria-label="Niyam sections"
    >
      <SidebarHeader>
        <WorkspaceMark />
        <SidebarToggle className="ml-auto" />
      </SidebarHeader>

      <SidebarNav>
        <RailNav active={active} onSelect={onSelect} />
      </SidebarNav>

      <SidebarFooter>
        <WorkspaceFooter />
      </SidebarFooter>
    </Sidebar>
  );
}

/* ─── Main pane (proof the sidebar sits in a real layout) ───── */

const stats = [
  { label: "Rules mapped", value: "8 / 8", note: "RBI · SEBI · NPCI" },
  { label: "Coverage", value: "71%", note: "baseline scan" },
  { label: "Open verdicts", value: "17", note: "2 blocking" },
  { label: "Days to release", value: "4", note: "v0.9.5" },
];

const queue = [
  { id: "F-217", rule: "UPI refund TAT", owner: "Payments", state: "Blocking" },
  { id: "F-204", rule: "KYC re-verification", owner: "Onboarding", state: "Blocking" },
  { id: "F-231", rule: "Grievance clock", owner: "Support", state: "Review" },
];

function MainPane({ active }: { active: RouteId }) {
  const route = allRoutes.find((r) => r.id === active);

  return (
    <div className="flex min-w-0 flex-1 flex-col overflow-y-auto bg-[var(--background)]">
      <header className="flex items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3.5 sm:px-7">
        <div className="flex items-center gap-2 text-[12px]">
          <span className="text-[var(--muted-foreground)]">Niyam</span>
          <span className="text-[var(--muted-foreground)]">/</span>
          <span className="font-medium">{route?.label ?? "Overview"}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="hidden rounded-md border border-[var(--border)] px-2 py-1 text-[11px] text-[var(--muted-foreground)] sm:inline">
            PayDemo · synthetic
          </span>
          <span className="rounded-md bg-[var(--taupe-strong)] px-2.5 py-1 text-[11px] font-medium text-white">
            Run sweep
          </span>
        </div>
      </header>

      <div className="flex flex-col gap-5 px-4 py-6 sm:px-7">
        <div>
          <h1 className="text-[22px] font-semibold tracking-[-0.02em]">
            {route?.label ?? "Overview"}
          </h1>
          <p className="mt-1 text-[12.5px] text-[var(--muted-foreground)]">
            Release readiness for PayDemo · gate at 95% evidence coverage.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {stats.map((s) => (
            <div
              key={s.label}
              className="rounded-xl border border-[var(--border)] bg-[var(--card)] px-3.5 py-3"
            >
              <div className="text-[10.5px] font-medium uppercase tracking-[0.08em] text-[var(--muted-foreground)]">
                {s.label}
              </div>
              <div className="mt-1.5 text-[20px] font-semibold leading-none tabular-nums">
                {s.value}
              </div>
              <div className="mt-1.5 text-[11px] text-[var(--muted-foreground)]">
                {s.note}
              </div>
            </div>
          ))}
        </div>

        <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
          <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-2.5">
            <span className="text-[12px] font-medium">Blocking fixes</span>
            <span className="text-[11px] text-[var(--muted-foreground)]">
              3 open
            </span>
          </div>
          <div className="overflow-x-auto">
          <table className="w-full min-w-[540px] text-left text-[12px]">
            <thead>
              <tr className="text-[10.5px] uppercase tracking-[0.07em] text-[var(--muted-foreground)]">
                <th className="px-4 py-2 font-medium">ID</th>
                <th className="px-4 py-2 font-medium">Rule</th>
                <th className="px-4 py-2 font-medium">Owner</th>
                <th className="px-4 py-2 font-medium">State</th>
              </tr>
            </thead>
            <tbody>
              {queue.map((row) => (
                <tr
                  key={row.id}
                  className="border-t border-[var(--border)] transition-colors hover:bg-[color-mix(in_srgb,var(--foreground)_3%,transparent)]"
                >
                  <td className="px-4 py-2.5 font-mono text-[11.5px]">{row.id}</td>
                  <td className="px-4 py-2.5">{row.rule}</td>
                  <td className="px-4 py-2.5 text-[var(--muted-foreground)]">
                    {row.owner}
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={
                        row.state === "Blocking"
                          ? "rounded-md bg-[#FBEDED] px-1.5 py-0.5 text-[10.5px] font-medium text-[var(--bad-ink)]"
                          : "rounded-md bg-[var(--hover)] px-1.5 py-0.5 text-[10.5px] font-medium text-[var(--muted-foreground)]"
                      }
                    >
                      {row.state}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </div>

        <p className="text-[11px] text-[var(--muted-foreground)]">
          Press the toggle (or the mark, when collapsed) to switch between the
          full rail and the logo-only rail.
        </p>
      </div>
    </div>
  );
}

/* ─── Demo ──────────────────────────────────────────────────── */

const NARROW = "(max-width: 1024px)";

export function SidebarDemo() {
  const [active, setActive] = React.useState<RouteId>("overview");
  const [collapsed, setCollapsed] = React.useState(
    () => typeof window !== "undefined" && window.matchMedia(NARROW).matches,
  );

  // Tablet and below start on the logo rail; going back to a wide viewport
  // restores the full rail. The toggle still wins in between.
  React.useEffect(() => {
    const mq = window.matchMedia(NARROW);
    const sync = () => setCollapsed(mq.matches);
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  return (
    <div className="flex h-full w-full overflow-hidden">
      <NiyamSidebar
        active={active}
        onSelect={setActive}
        collapsed={collapsed}
        onCollapsedChange={setCollapsed}
      />
      <MainPane active={active} />
    </div>
  );
}

export default SidebarDemo;
