import * as React from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Check } from "lucide-react";
import { HereStrip, PageHeader } from "@/components/Page";
import { Notice } from "@/components/Notice";
import { ErrorState, LoadingBlock } from "@/components/States";
import { useApprovals, useOverview } from "@/lib/api";
import { fmtElapsed, pct } from "@/lib/format";
import { liveElapsed, packClock, packSteps } from "@/lib/overview";
import type { Overview as OverviewT, PackStep } from "@/lib/types";

function Stat({ label, value, note }: { label: string; value: React.ReactNode; note?: string }) {
  return (
    <div className="sheet px-4 py-3.5">
      <div className="label">{label}</div>
      <div className="num mt-2 text-[30px] font-medium leading-none">{value}</div>
      {note ? <div className="mt-2 text-[11.5px] text-[var(--muted-foreground)]">{note}</div> : null}
    </div>
  );
}

export function StepRibbon({ steps }: { steps: PackStep[] }) {
  return (
    <ol aria-label="Circular to approved pack" className="ribbon grid gap-2 sm:grid-cols-2 lg:grid-cols-6">
      {steps.map((s, i) => (
        <li key={s.key} data-state={s.state} aria-current={s.state === "current" ? "step" : undefined} className="ribbon-step">
          <Link to={s.route} className="ribbon-link">
            <span className="ribbon-dot" aria-hidden="true">{s.state === "done" ? <Check size={14} strokeWidth={2.5} /> : i + 1}</span>
            <span className="ribbon-label">{s.label}</span>
            <span className="ribbon-state">{s.state === "done" ? "Done" : s.state === "current" ? "Now" : "Next"}</span>
            <span className="ribbon-detail">{s.detail}</span>
          </Link>
        </li>
      ))}
    </ol>
  );
}

function ClockCard({ o, fetchedAt }: { o: OverviewT; fetchedAt: number }) {
  const pack = packClock(o);
  const [now, setNow] = React.useState(() => Date.now());
  const running = pack.elapsed_seconds !== null && !pack.approved_at;
  React.useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [running]);
  const secs = liveElapsed(pack, fetchedAt, now);
  const known = !!o.pack;
  return (
    <section className="sheet clock-card grid gap-6 p-5 sm:p-6 lg:grid-cols-[1.3fr_1fr]" aria-label="Circular to approved pack">
      <div>
        <div className="label">Circular to approved pack</div>
        <p className="mt-2 text-[13px] text-[var(--muted-foreground)]">{pack.circular_title ?? "No circular added yet. Add one under Rules to start the clock."}</p>
        <div className="clock-num num mt-3" aria-live="off">{secs === null ? "Not started" : fmtElapsed(secs)}</div>
        <p className="mt-2 text-[12px] text-[var(--muted-foreground)]">
          {pack.approved_at ? `Approved in ${fmtElapsed(pack.elapsed_seconds)}. ` : running ? "The clock runs until the pack is approved. " : ""}
          Timed in this demo workspace on synthetic documents.
        </p>
      </div>
      <dl className="grid grid-cols-3 gap-3 self-end">
        {([["Documents", pack.documents_total], ["Affected", pack.documents_affected], ["Clear", pack.documents_clear]] as const).map(([k, v]) => (
          <div key={k} className="rounded-xl border border-[var(--border)] bg-[var(--background)] px-3 py-3">
            <dt className="label">{k}</dt>
            <dd className="num mt-2 text-[26px] leading-none">{known || k === "Documents" ? v : "—"}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

export default function Overview() {
  const q = useOverview();
  const d = q.data;
  const approved = useApprovals({ kind: "fix", status: "approved" });
  return (
    <>
      <PageHeader eyebrow="Overview" title="From circular to approved pack" lede="See which proposals and brochures say something out of date, which fixes are waiting, and which a named person has approved. Check Documents before you send." />
      <HereStrip here="Six steps take a circular to an approved pack. One waits for a named approver." next={d ? `Next: ${d.next_action.label}.` : "Next: see below."} />
      {q.isLoading ? <div className="sheet"><LoadingBlock rows={4} label="Loading overview" /></div> : q.isError ? <div className="sheet"><ErrorState error={q.error} onRetry={() => void q.refetch()} /></div> : d ? (
        <div className="flex flex-col gap-5">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <Stat label="Documents scanned" value={d.documents_scanned} />
            <Stat label="Out-of-date claims still open" value={d.open_findings} note="Open findings across your documents" />
            <Stat label="Fixes approved" value={approved.isError || !Array.isArray(approved.data) ? "—" : approved.data.length} note="Each one has a named approver" />
            <Stat label="Fixes waiting for approval" value={d.fixes_awaiting_approval} note="A named person has not approved these yet" />
            <Stat label="Rules waiting for approval" value={d.rules_pending_approval} />
            <Stat label="Citation coverage" value={pct(d.citation_coverage)} note="Findings backed by a verified quote" />
          </div>
          <StepRibbon steps={packSteps(d)} />
          <ClockCard o={d} fetchedAt={q.dataUpdatedAt || Date.now()} />
          <div className="sheet flex flex-wrap items-center justify-between gap-3 p-4 sm:p-5">
            <div>
              <div className="label">What to do next</div>
              <p className="mt-1 text-[14px]">{d.next_action.label}</p>
            </div>
            <Link to={d.next_action.route} className="btn btn-primary btn-lg">{d.next_action.label} <ArrowRight size={15} /></Link>
          </div>
          {d.rules.draft > 0 ? (
            <Notice tone="warn">
              {d.rules.active === 0
                ? `All ${d.rules.draft} rules are draft (pending approval). Findings that rely on them are decision support only until a named person approves the rules.`
                : `${d.rules.active} rule${d.rules.active === 1 ? " is" : "s are"} active; ${d.rules.draft} still draft and pending approval. Only active rules are used in scans.`}
            </Notice>
          ) : null}
        </div>
      ) : null}
    </>
  );
}
