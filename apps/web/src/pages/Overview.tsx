import * as React from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Check } from "lucide-react";
import { HereStrip, PageHeader } from "@/components/Page";
import { Notice } from "@/components/Notice";
import { ErrorState, LoadingBlock } from "@/components/States";
import { useApprovals, useOverview } from "@/lib/api";
import { fmtElapsed, pct } from "@/lib/format";
import { liveElapsed, packClock, packSteps } from "@/lib/overview";
import { HINT } from "@/lib/hints";
import { HintLabel } from "@/components/Hint";
import type { Overview as OverviewT, PackStep } from "@/lib/types";

function Stat({ label, value, note, hint }: { label: string; value: React.ReactNode; note?: string; hint: string }) {
  return (
    <div className="sheet px-4 py-3.5">
      <div className="label"><HintLabel label={label} hint={hint} /></div>
      <div className="num mt-2 text-[30px] font-medium leading-none">{value}</div>
      {note ? <div className="mt-2 text-[11.5px] text-[var(--muted-foreground)]">{note}</div> : null}
    </div>
  );
}

export function StepRibbon({ steps }: { steps: PackStep[] }) {
  return (
    <ol aria-label="From circular to a pack you can send" className="ribbon grid gap-2 sm:grid-cols-2 lg:grid-cols-6">
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
    <section className="sheet clock-card grid gap-6 p-5 sm:p-6 lg:grid-cols-[1.3fr_1fr]" aria-label="From circular to a pack you can send">
      <div>
        <div className="label"><HintLabel label="Time from circular to a pack you can send" hint={HINT.clock} /></div>
        <p className="mt-2 text-[13px] text-[var(--muted-foreground)]">{pack.circular_title ?? "No circular added yet. Add the one that landed this morning to start the clock."}</p>
        <div className="clock-num num mt-3" aria-live="off">{secs === null ? "Not started" : fmtElapsed(secs)}</div>
        <p className="mt-2 text-[12px] text-[var(--muted-foreground)]">
          {pack.approved_at ? `Approved in ${fmtElapsed(pack.elapsed_seconds)}. ` : running ? "The clock runs until a named person has signed the pack. " : ""}
          Timed on the synthetic BlueCart / Sunrise sales pack.
        </p>
      </div>
      <dl className="grid grid-cols-3 gap-3 self-end">
        {([["Documents", pack.documents_total, HINT.clockDocuments], ["Affected", pack.documents_affected, HINT.clockAffected], ["Clear", pack.documents_clear, HINT.clockClear]] as const).map(([k, v, hint]) => (
          <div key={k} className="rounded-xl border border-[var(--border)] bg-[var(--background)] px-3 py-3">
            <dt className="label"><HintLabel label={k} hint={hint} /></dt>
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
      <PageHeader eyebrow="Overview" title="What’s clear to send" lede="This is the BlueCart sales pack. See which proposals still say something out of date, which fixes wait for a name, and which a named person has already signed. Check Documents before a merchant sees the file." />
      <HereStrip here="Six steps take a circular to a pack you can send. One step always waits for a named person." next={d ? `Next: ${d.next_action.label}.` : "Next: see below."} />
      {q.isLoading ? <div className="sheet"><LoadingBlock rows={4} label="Loading overview" /></div> : q.isError ? <div className="sheet"><ErrorState error={q.error} onRetry={() => void q.refetch()} /></div> : d ? (
        <div className="flex flex-col gap-5">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <Stat label="Decks scanned" value={d.documents_scanned} note="Proposals, agreements, brochures in this pack" hint={HINT.statScanned} />
            <Stat label="Stale claims still in the pack" value={d.open_findings} note="Sentences a merchant could still read" hint={HINT.statOpen} />
            <Stat label="Fixes a named person signed" value={approved.isError || !Array.isArray(approved.data) ? "—" : approved.data.length} note="Clear to send, with a name on them" hint={HINT.statSigned} />
            <Stat label="Fixes waiting for a name" value={d.fixes_awaiting_approval} note="Wording is drafted. Do not send yet." hint={HINT.statWaitingFix} />
            <Stat label="Rules waiting for a name" value={d.rules_pending_approval} note="Draft checks are not used on decks" hint={HINT.statWaitingRule} />
            <Stat label="Every finding has a quote" value={pct(d.citation_coverage)} note="The sentence plus the rule behind it" hint={HINT.statQuote} />
          </div>
          <StepRibbon steps={packSteps(d)} />
          <ClockCard o={d} fetchedAt={q.dataUpdatedAt || Date.now()} />
          <div className="sheet flex flex-wrap items-center justify-between gap-3 p-4 sm:p-5">
            <div>
              <div className="label">What to do before you send</div>
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
