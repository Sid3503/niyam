import * as React from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Activity, BookOpenCheck, ClipboardCheck, Gauge, Library, Map, Settings as SettingsIcon, ShieldCheck } from "lucide-react";
import { Hint } from "@/components/Hint";
import { HINT } from "@/lib/hints";
import { useTour } from "@/components/Tour";
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
import { Footer } from "@/components/Page";
import { useOverview } from "@/lib/api";

/* ─── Brand (same mark as the earlier console) ──────────────── */

export function NiyamMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 100 100" fill="none" role="img" aria-label="Niyam" className={className}>
      <path d="M6 88V25c0-10 11-14 17-6l35 42" stroke="currentColor" strokeWidth={7} strokeLinecap="round" strokeLinejoin="round" />
      <path d="M41 63l24 24c7 7 16 2 16-8V45" stroke="currentColor" strokeWidth={7} strokeLinecap="round" strokeLinejoin="round" />
      <path d="M85 9c1.6 7.5 5.5 11.4 13 13-7.5 1.6-11.4 5.5-13 13-1.6-7.5-5.5-11.4-13-13 7.5-1.6 11.4-5.5 13-13Z" fill="currentColor" />
    </svg>
  );
}

function WorkspaceMark() {
  const { collapsed } = useSidebar();
  const mark = <NiyamMark className="size-7 shrink-0 text-[var(--taupe)]" />;
  if (collapsed) return <div className="flex size-9 items-center justify-center">{mark}</div>;
  return (
    <Link to="/" aria-label="Niyam home" className="flex min-w-0 items-center gap-2.5">
      {mark}
      <span className="flex min-w-0 flex-col leading-none">
        <span className="truncate text-[14px] font-semibold tracking-[-0.01em]">Niyam</span>
        <span className="mt-1 truncate text-[10.5px] font-medium uppercase tracking-[0.09em] text-[var(--muted-foreground)]">Clear to send</span>
      </span>
    </Link>
  );
}

function CountBadge({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-md bg-[color-mix(in_srgb,var(--foreground)_7%,transparent)] px-1.5 py-0.5 text-[10.5px] font-medium leading-none tabular-nums text-[var(--muted-foreground)]">
      {children}
    </span>
  );
}

/* ─── Nav model ─────────────────────────────────────────────── */

const S = 17;
interface Route { path: string; label: string; icon: React.ReactNode; badge?: React.ReactNode }

function RailNav() {
  const { collapsed } = useSidebar();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const overview = useOverview();
  const pending = overview.data ? overview.data.fixes_awaiting_approval + overview.data.rules_pending_approval : 0; // neutral counter, Approvals only

  const groups: { label: string; routes: Route[] }[] = [
    {
      label: "Before you send",
      routes: [
        { path: "/overview", label: "Overview", icon: <Gauge size={S} strokeWidth={1.75} /> },
        { path: "/library", label: "Documents", icon: <Library size={S} strokeWidth={1.75} /> },
        { path: "/rules", label: "Rules", icon: <BookOpenCheck size={S} strokeWidth={1.75} /> },
        { path: "/impact", label: "What this circular breaks", icon: <Activity size={S} strokeWidth={1.75} /> },
        { path: "/guide", label: "How to use", icon: <Map size={S} strokeWidth={1.75} /> },
      ],
    },
    {
      label: "Sign off",
      routes: [
        { path: "/approvals", label: "Approvals", icon: <ClipboardCheck size={S} strokeWidth={1.75} />, badge: pending > 0 ? <CountBadge>{pending}</CountBadge> : undefined },
        { path: "/evidence", label: "Evidence", icon: <ShieldCheck size={S} strokeWidth={1.75} /> },
      ],
    },
  ];

  const isActive = (p: string) => pathname === p || pathname.startsWith(`${p}/`);

  return (
    <>
      {groups.map((g) => (
        <SidebarSection key={g.label} label={g.label}>
          {g.routes.map((r) => (
            <SidebarItem
              key={r.path}
              icon={r.icon}
              active={isActive(r.path)}
              badge={r.badge}
              aria-label={r.label}
              className={collapsed ? "mx-auto h-10 w-10 justify-center gap-0 px-0" : undefined}
              onClick={() => navigate(r.path)}
            >
              {r.label}
            </SidebarItem>
          ))}
        </SidebarSection>
      ))}
    </>
  );
}

function WorkspaceFooter() {
  const { collapsed } = useSidebar();
  const navigate = useNavigate();
  const settingsBtn = (
    <button
      type="button"
      aria-label="Settings"
      title="Settings"
      onClick={() => navigate("/settings")}
      className="flex size-7 shrink-0 items-center justify-center rounded-full bg-[var(--sand)] text-[var(--taupe-strong)] transition-colors hover:bg-[#ded4cb]"
    >
      <SettingsIcon size={14} />
    </button>
  );
  if (collapsed) {
    return (
      <span className="flex flex-col items-center gap-2">
        <Hint text={HINT.synthetic}><span className="size-1.5 rounded-full bg-[var(--taupe)]" /></Hint>
        {settingsBtn}
      </span>
    );
  }
  return (
    <>
      <div className="flex min-w-0 flex-1 flex-col leading-tight">
        <span className="flex items-center gap-1.5 text-[12px] font-medium">
          <Hint text={HINT.synthetic}><span className="size-1.5 shrink-0 rounded-full bg-[var(--taupe)]" /></Hint>
          BlueCart sales pack
        </span>
        <span className="mt-0.5 truncate text-[10.5px] text-[var(--muted-foreground)]">Synthetic merchant docs</span>
      </div>
      {settingsBtn}
    </>
  );
}

const NARROW = "(max-width: 1024px)";
const TITLES: Record<string, string> = { overview: "Overview", library: "Documents", rules: "Rules", impact: "What this circular breaks", approvals: "Approvals", evidence: "Evidence", guide: "How to use", settings: "Settings" };

function WalkthroughButton() {
  const tour = useTour();
  return (
    <button type="button" className="btn btn-sm" onClick={tour.start}>
      2-min walkthrough
    </button>
  );
}

export function AppShell() {
  const { pathname } = useLocation();
  const [collapsed, setCollapsed] = React.useState(() => typeof window !== "undefined" && window.matchMedia(NARROW).matches);
  const main = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const mq = window.matchMedia(NARROW);
    const sync = () => setCollapsed(mq.matches);
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  React.useEffect(() => {
    main.current?.scrollTo?.({ top: 0 });
    const seg = pathname.split("/")[1] ?? "";
    document.title = `${TITLES[seg] ?? "Niyam"} · Niyam`;
  }, [pathname]);

  const seg = pathname.split("/")[1] ?? "";

  return (
    <div className="flex h-full w-full overflow-hidden">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-[60] focus:m-2 focus:rounded-md focus:bg-[var(--card)] focus:px-3 focus:py-2 focus:text-[12px]">
        Skip to content
      </a>
      <Sidebar variant="collapsible" width={264} collapsedWidth={76} collapsed={collapsed} onCollapsedChange={setCollapsed} className="rail-light" aria-label="Niyam sections">
        <SidebarHeader>
          <WorkspaceMark />
          <SidebarToggle className="ml-auto" />
        </SidebarHeader>
        <SidebarNav>
          <RailNav />
        </SidebarNav>
        <SidebarFooter>
          <WorkspaceFooter />
        </SidebarFooter>
      </Sidebar>

      <div ref={main} className="flex min-w-0 flex-1 flex-col overflow-y-auto bg-[var(--background)]">
        <div className="flex items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3.5 sm:px-8">
          <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.12em]">
            <Link to="/" className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]">Niyam</Link>
            <span className="text-[var(--muted-foreground)]">›</span>
            <span>{TITLES[seg] ?? "Niyam"}</span>
          </nav>
          <div className="flex items-center gap-2">
            <WalkthroughButton />
            <span className="chip chip-plain hidden sm:inline-flex">Synthetic demo data</span>
          </div>
        </div>
        <p className="pitch-bar">
          Don’t send last quarter’s deck. <strong>BlueCart still promises 7-day UPI refunds; the rule is T+5.</strong> A named person has to approve the fix before it goes out.
        </p>
        <main id="main" tabIndex={-1} className="mx-auto flex w-full max-w-[1200px] flex-1 flex-col px-4 py-7 outline-none sm:px-8 sm:py-9">
          <div className="flex-1">
            <Outlet />
          </div>
          <Footer />
        </main>
      </div>
    </div>
  );
}
