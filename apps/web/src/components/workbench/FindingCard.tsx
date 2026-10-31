import { Link, useLocation } from "react-router-dom";
import { FlaskConical, Send } from "lucide-react";
import { ApprovalChip, FindingChip, Tag } from "@/components/Badges";
import { Redline } from "@/components/Redline";
import { ruleLink } from "@/components/RuleDrawer";
import { useApprovals, useSendForApproval } from "@/lib/api";
import { fmtDateTime, humanize } from "@/lib/format";
import type { Approval, ApprovalStatus } from "@/lib/types";
import { isFactSource, type Clause, type Finding } from "@/lib/types";

function fixLine(status: ApprovalStatus, a: Approval | undefined): string {
  const who = a?.decided_by ? ` by ${a.decided_by}${a.decided_at ? `, ${fmtDateTime(a.decided_at)}` : ""}` : "";
  if (status === "approved") return `Fix approved${who || ""}`;
  if (status === "rejected") return `Fix rejected${who}`;
  if (status === "deferred") return `Fix deferred${who}`;
  return "Fix waiting for approval";
}

/** One finding: status, confidence, quote/source, rule link, suggested wording as a redline, send-for-approval. Shared by the text, PDF and voice views. */
export function FindingCard({ f, clause, onRetest, docId, selected, onSelect, extra, readOnly }: {
  f: Finding;
  clause: Clause | undefined;
  onRetest: () => void;
  docId: string;
  selected?: boolean;
  onSelect?: () => void;
  /** Format-specific controls (apply toggle, play-at button) rendered under the wording. */
  extra?: React.ReactNode;
  /** Viewing an older version: no send-for-approval. */
  readOnly?: boolean;
}) {
  const send = useSendForApproval();
  const fixes = useApprovals({ kind: "fix" });
  const loc = useLocation();
  const approval = send.data ? { id: send.data.id, status: send.data.status } : f.approval;
  const decided = Array.isArray(fixes.data) && approval ? fixes.data.find((a) => a.id === approval.id) : undefined;
  const src = f.source;
  return (
    <article
      className={`sheet p-4 ${selected ? "ring-2 ring-[var(--ring)]" : ""}`}
      aria-label={`Finding ${f.id}`}
      data-status={f.status}
      data-finding-card={f.id}
      data-selected={selected ? "true" : undefined}
      onClick={onSelect}
    >
      <div className="flex flex-wrap items-center gap-1.5">
        <FindingChip status={f.status} />
        <span className="chip chip-plain">{humanize(f.severity)} severity</span>
        <span className="chip chip-plain" title="How sure Niyam is about this finding. A person decides.">confidence {Math.round(f.confidence * 100)}%</span>
        <span className="chip chip-plain" title="Tier A: checked by code. Tier B: checked by a language model.">tier {f.tier}</span>
        {f.page ? <Tag>page {f.page}</Tag> : null}
        <span className="ml-auto font-mono text-[11px] text-[var(--muted-foreground)]">{clause ? clause.locator : f.locator || "no clause"}</span>
      </div>
      <p className="mt-2.5 text-[13px] leading-relaxed"><span className="label mr-1.5">Why it is flagged</span>{f.reason}</p>
      {f.quote ? <p className="mt-2 border-l-2 border-[var(--border)] pl-2.5 text-[12.5px] italic text-[var(--muted-foreground)]">“{f.quote}”</p> : null}

      <div className="mt-3">
        <div className="label mb-1">Source</div>
        {isFactSource(src) ? (
          <blockquote className="border-l-2 border-[var(--taupe)] bg-[var(--background)] px-3 py-2 text-[12.5px] leading-relaxed">
            {src.statement}
            <footer className="mt-1.5 text-[11.5px] text-[var(--muted-foreground)]">Product fact <span className="font-mono">{src.fact_id}</span> · {src.title} · {src.label}</footer>
          </blockquote>
        ) : (
          <blockquote className="border-l-2 border-[var(--taupe)] bg-[var(--background)] px-3 py-2 text-[12.5px] leading-relaxed">
            {src.quote ? <>“{src.quote}”</> : <span className="text-[var(--muted-foreground)]">No quote supplied</span>}
            <footer className="mt-1.5 text-[11.5px] text-[var(--muted-foreground)]">
              {[src.document, src.reference, src.locator, src.regulator].filter(Boolean).join(" · ")}
              {f.rule_id ? (
                <>
                  {" · "}
                  <Link to={ruleLink(loc.search, f.rule_id)} className="font-mono underline underline-offset-2" onClick={(e) => e.stopPropagation()}>{f.rule_id} v{f.rule_version}</Link>
                  {f.rule_status && f.rule_status !== "active" ? <span className="ml-1.5 chip chip-warn chip-plain">{f.rule_status}, not approved</span> : null}
                </>
              ) : null}
            </footer>
          </blockquote>
        )}
        {isFactSource(src) ? null : f.fact_id ? <p className="mt-1 text-[11.5px] text-[var(--muted-foreground)]">Also checked against product fact <span className="font-mono">{f.fact_id}</span> (synthetic demo data)</p> : null}
      </div>

      {f.suggested_fix ? (
        <div className="mt-3">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <div className="label">Corrected wording</div>
            <span className={f.suggested_fix.validated ? "chip chip-ok chip-plain" : "chip chip-warn chip-plain"}>{f.suggested_fix.validated ? "re-check passed" : "not re-checked"}</span>
          </div>
          {clause ? <Redline before={f.quote ?? clause.text} after={f.suggested_fix.wording} /> : <p className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-3 text-[12.5px] leading-relaxed"><ins className="rl-ins">{f.suggested_fix.wording}</ins></p>}
          <p className="mt-1.5 text-[11.5px] text-[var(--muted-foreground)]">{f.suggested_fix.rationale}</p>
        </div>
      ) : null}

      {extra ? <div className="mt-3" onClick={(e) => e.stopPropagation()}>{extra}</div> : null}

      {send.isError ? <p role="alert" className="mt-2 text-[12px] text-[var(--bad-ink)]">{send.error.message}</p> : null}
      <div className="mt-3 flex flex-wrap items-center gap-2" onClick={(e) => e.stopPropagation()}>
        {approval ? (
          <>
            <ApprovalChip status={approval.status} />
            <span className="text-[12px]" data-testid="fix-status">{fixLine(approval.status, decided)}</span>
            <Link to="/approvals" className="text-[12px] underline underline-offset-2">Open in approvals</Link>
          </>
        ) : (
          <button type="button" className="btn btn-sm btn-primary" disabled={!f.suggested_fix || send.isPending || readOnly} title={readOnly ? "Open the latest version to send this for approval" : f.suggested_fix ? undefined : "No suggested wording to send yet"} onClick={() => send.mutate(f.id)}>
            <Send size={13} /> {send.isPending ? "Sending…" : "Send for approval"}
          </button>
        )}
        {!approval && f.suggested_fix ? <span className="text-[12px] text-[var(--muted-foreground)]" data-testid="fix-status">Fix drafted, not yet sent for approval</span> : null}
        <button type="button" className="btn btn-sm" onClick={onRetest} data-doc={docId}><FlaskConical size={13} /> Re-test</button>
        {f.needs_human ? <span className="text-[11.5px] text-[var(--muted-foreground)]">Needs a person to decide</span> : null}
      </div>
    </article>
  );
}
