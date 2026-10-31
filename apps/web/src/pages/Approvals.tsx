import * as React from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApprovalChip, Severity, Tag } from "@/components/Badges";
import { FilterSelect } from "@/components/Filters";
import { HereStrip, PageHeader } from "@/components/Page";
import { Redline } from "@/components/Redline";
import { RuleDrawer, ruleLink } from "@/components/RuleDrawer";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/States";
import { useApprovals, useDecision } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import type { Approval, ApprovalKind, ApprovalStatus, Decision } from "@/lib/types";

export function ApprovalCard({ a }: { a: Approval }) {
  const decide = useDecision();
  const search = useSearchParams()[0].toString();
  const [reason, setReason] = React.useState("");
  const pending = a.status === "pending" || a.status === "deferred";
  const go = (d: Decision) => decide.mutate({ id: a.id, decision: d, reason: reason.trim() || undefined });
  return (
    <article className="sheet p-4" aria-label={`Approval ${a.id}`} data-status={a.status}>
      <div className="flex flex-wrap items-center gap-1.5">
        <Tag>{a.kind === "rule" ? "Rule" : "Fix"}</Tag>
        <ApprovalChip status={a.status} />
        <Severity value={a.severity} />
        {a.confidence !== null ? <span className="chip chip-plain" title="How sure Niyam is. A person decides.">confidence {Math.round(a.confidence * 100)}%</span> : null}
        <span className="ml-auto text-[11px] text-[var(--muted-foreground)]">{fmtDateTime(a.created_at)}</span>
      </div>
      <h2 className="mt-2 text-[15px] font-medium leading-snug">{a.title}</h2>
      {a.document ? <p className="mt-0.5 text-[12px] text-[var(--muted-foreground)]">In <Link to={`/library/${a.document.id}`} className="underline underline-offset-2">{a.document.title}</Link>{a.clause ? ` · ${a.clause.locator}` : ""}</p> : null}
      {a.rule ? (
        <p className="mt-0.5 text-[12px] text-[var(--muted-foreground)]">
          <Link to={ruleLink(search, a.rule.id)} className="font-mono underline underline-offset-2">{a.rule.id} v{a.rule.version}</Link> · {a.rule.status === "active" ? "active" : `${a.rule.status}, not approved`}
        </p>
      ) : null}

      <div className="mt-3">
        <div className="label mb-1">Source</div>
        <blockquote className="border-l-2 border-[var(--taupe)] bg-[var(--background)] px-3 py-2 text-[12.5px] leading-relaxed">
          {a.source.quote ? <>“{a.source.quote}”</> : <span className="text-[var(--muted-foreground)]">No quote supplied</span>}
          <footer className="mt-1.5 text-[11.5px] text-[var(--muted-foreground)]">
            {[a.source.document, a.source.reference, a.source.locator].filter(Boolean).join(" · ")} · {a.source.quote_verified ? "quote verified in source" : "quote not verified"}
          </footer>
        </blockquote>
      </div>

      {a.rule ? (
        <div className="mt-3"><div className="label mb-1">Obligation</div><p className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-3 text-[12.5px] leading-relaxed">{a.rule.obligation}</p></div>
      ) : null}
      {a.kind === "fix" && a.proposed_wording ? (
        <div className="mt-3">
          {a.current_wording ? <Redline before={a.current_wording} after={a.proposed_wording} /> : <p className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-3 text-[12.5px]"><ins className="rl-ins">{a.proposed_wording}</ins></p>}
          <p className="mt-1.5 text-[11.5px] text-[var(--muted-foreground)]">Approving records this wording against the finding. A named person decides; the document is not changed.</p>
        </div>
      ) : null}

      {a.status !== "pending" && a.decided_by ? (
        <p className="mt-3 text-[12px] text-[var(--muted-foreground)]">{a.status === "approved" ? "Approved" : a.status === "rejected" ? "Rejected" : "Deferred"} by <span className="font-medium text-[var(--foreground)]">{a.decided_by}</span>, {fmtDateTime(a.decided_at)}{a.reason ? `. Reason: ${a.reason}` : ""}</p>
      ) : null}

      {pending ? (
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <div className="min-w-[14rem] flex-1">
            <label htmlFor={`reason-${a.id}`} className="label mb-1 block">Reason (optional)</label>
            <input id={`reason-${a.id}`} className="field !py-1.5 text-[12.5px]" value={reason} onChange={(e) => setReason(e.target.value)} />
          </div>
          <button type="button" className="btn btn-sm btn-primary" disabled={decide.isPending} onClick={() => go("approve")}>Approve</button>
          <button type="button" className="btn btn-sm" disabled={decide.isPending} onClick={() => go("reject")}>Reject</button>
          <button type="button" className="btn btn-sm" disabled={decide.isPending} onClick={() => go("defer")}>Defer</button>
        </div>
      ) : null}
      {decide.isError ? <p role="alert" className="mt-2 text-[12px] text-[var(--bad-ink)]">{decide.error.message}</p> : null}
    </article>
  );
}

export default function Approvals() {
  const [params, setParams] = useSearchParams();
  const status = (params.get("status") ?? "") as ApprovalStatus | "";
  const kind = (params.get("kind") ?? "") as ApprovalKind | "";
  const setF = (k: string) => (v: string) => setParams((p) => { if (v) p.set(k, v); else p.delete(k); return p; }, { replace: true });
  const q = useApprovals({ status, kind });
  const rows = q.data ?? [];

  return (
    <>
      <PageHeader eyebrow="Approvals" title="A name on every fix before it goes out" lede="Sales does not send a deck from this queue. A named person approves, rejects, or defers. Highest severity and lowest confidence come first. After a yes, the name and time sit on the document and in the proof pack." />
      <HereStrip here="Nothing ships without a name. Their name and the time are recorded on every decision." next="Next: put your name on the top item, or reject it." />
      <div className="sheet mb-4 flex flex-wrap items-end gap-3 p-3.5">
        <FilterSelect id="ap-status" label="Status" value={status} onChange={setF("status")} options={(["pending", "approved", "rejected", "deferred"] as const).map((v) => ({ value: v }))} />
        <FilterSelect id="ap-kind" label="Kind" value={kind} onChange={setF("kind")} options={[{ value: "rule", label: "Rule" }, { value: "fix", label: "Fix" }]} />
      </div>
      {q.isLoading ? <div className="sheet"><LoadingBlock rows={6} label="Loading approvals" /></div> : q.isError ? <div className="sheet"><ErrorState error={q.error} onRetry={() => void q.refetch()} /></div> : rows.length === 0 ? (
        <div className="sheet"><EmptyState title="Nothing waiting for a name" hint="Nothing matches these filters. Clear them, or scan the decks: new stale sentences with drafted wording arrive here before anyone sends the file." /></div>
      ) : (
        <div className="flex flex-col gap-3">{rows.map((a) => <ApprovalCard key={a.id} a={a} />)}</div>
      )}
      <p className="mt-2 text-[11.5px] text-[var(--muted-foreground)]">{rows.length} item{rows.length === 1 ? "" : "s"}</p>
      <RuleDrawer />
    </>
  );
}
