import * as React from "react";
import { useSearchParams } from "react-router-dom";
import { CheckCircle2, ChevronDown, TriangleAlert } from "lucide-react";
import { Drawer } from "@/components/Drawer";
import { EnforceChip, OcrBadge, ProvenanceBadge, Severity, StatusBadge, Tag } from "@/components/Badges";
import { HintLabel } from "@/components/Hint";
import { HINT, tierHint } from "@/lib/hints";
import { KV } from "@/components/Page";
import { ErrorState, LoadingBlock } from "@/components/States";
import { useRule } from "@/lib/api";
import { fmtDate, fmtDateTime, humanize } from "@/lib/format";
import type { RuleDetail } from "@/lib/types";

/** YAML-ish, read-only rendering of the check config. Mono, no parsing, no HTML injection. */
function toYaml(v: unknown, indent = 0): string {
  const pad = "  ".repeat(indent);
  if (Array.isArray(v)) return v.map((x) => (typeof x === "object" && x !== null ? `${pad}-\n${toYaml(x, indent + 1)}` : `${pad}- ${String(x)}`)).join("\n");
  if (v && typeof v === "object") {
    return Object.entries(v as Record<string, unknown>)
      .map(([k, x]) => (typeof x === "object" && x !== null ? `${pad}${k}:\n${toYaml(x, indent + 1)}` : `${pad}${k}: ${x === null ? "null" : String(x)}`))
      .join("\n");
  }
  return `${pad}${String(v)}`;
}

function RuleDrawerBody({ id }: { id: string }) {
  const q = useRule(id);
  const [showRaw, setShowRaw] = React.useState(false);
  if (q.isLoading) return <LoadingBlock rows={8} label="Loading rule" />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  const r: RuleDetail = q.data!;
  const cfg = r.check.config ?? {};
  const scalars = Object.entries(cfg).filter(([, v]) => v === null || ["string", "number", "boolean"].includes(typeof v));
  const enforce = r.enforceability ?? (r.effective_from && r.effective_from > new Date().toISOString().slice(0, 10) ? "not_yet_enforceable" : "live");
  const v = r.validation;

  return (
    <div className="flex flex-col gap-5">
      <div>
        <div className="flex flex-wrap items-center gap-1.5">
          <StatusBadge status={r.status} />
          <Severity value={r.severity} />
          <Tag title={tierHint(r.check.tier)}>tier {r.check.tier}</Tag>
          <Tag>{humanize(r.check.type)}</Tag>
        </div>
        <h2 className="mt-3 text-[22px] font-light leading-tight tracking-[-0.01em]">{r.title}</h2>
        <p className="mt-1.5 font-mono text-[11px] text-[var(--muted-foreground)]">{r.id} · v{r.version}</p>
      </div>

      {r.status === "draft" ? (
        <p role="note" className="flex gap-2 rounded-lg border border-[var(--warn-line)] bg-[var(--warn-bg)] px-3 py-2 text-[12.5px] text-[var(--warn-ink)]">
          <TriangleAlert size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
          Draft, pending approval. Approved by: {r.approved_by ?? "no one"}. A named human must approve this card before it counts in scans.
        </p>
      ) : null}

      {r.versions?.length ? (
        <section>
          <div className="label mb-2">Versions</div>
          <ul className="flex flex-wrap gap-1.5">{r.versions.map((x) => <li key={x.version} className="chip chip-plain">v{x.version} · {x.status} · {fmtDate(x.effective_from)}</li>)}</ul>
        </section>
      ) : null}

      <section>
        <div className="label mb-2">Obligation</div>
        <blockquote className="border-l-2 border-[var(--taupe)] bg-[var(--background)] px-4 py-3 text-[14px] leading-relaxed">{r.obligation}</blockquote>
      </section>

      <section>
        <div className="label mb-1">Applicability</div>
        <dl>
          <KV k="Effective"><span className="mr-2">{fmtDate(r.effective_from)}{r.effective_to ? ` – ${fmtDate(r.effective_to)}` : ""}</span><EnforceChip enforceability={enforce} effective={r.effective_from} /></KV>
          <KV k="Owner">{r.owner ?? "—"}</KV>
          {r.approved_by ? <KV k="Approved">{r.approved_by}{r.approved_at ? `, ${fmtDateTime(r.approved_at)}` : ""}</KV> : null}
          <KV k="Threshold">{r.confidence_threshold !== undefined ? `confidence ≥ ${r.confidence_threshold.toFixed(2)}` : "—"}{r.evidence_required ? ` · evidence: ${humanize(r.evidence_required)}` : ""}</KV>
          {r.scope ? Object.entries(r.scope).map(([k, vals]) => <KV key={k} k={k}>{vals.join(", ")}</KV>) : null}
        </dl>
      </section>

      <section>
        <div className="label mb-2"><HintLabel label="How it is checked" hint={HINT.checkedBy} /></div>
        {scalars.length ? (
          <dl className="mb-2 rounded-lg border border-[var(--border)] px-3 py-1.5">
            {scalars.map(([k, val]) => <KV key={k} k={humanize(k)}><span className="font-mono text-[12px]">{String(val)}</span></KV>)}
          </dl>
        ) : null}
        <button type="button" className="flex items-center gap-1.5 text-[12.5px] font-medium" aria-expanded={showRaw} onClick={() => setShowRaw((s) => !s)}>
          <ChevronDown size={14} className={showRaw ? "rotate-180" : ""} /> {showRaw ? "Hide" : "Show"} technical detail
        </button>
        {showRaw ? <pre className="mt-2 max-h-[340px] overflow-auto rounded-lg bg-[var(--background)] p-3 font-mono text-[11.5px] leading-relaxed" tabIndex={0} aria-label="Check configuration">{toYaml(cfg)}</pre> : null}
        {cfg["authored_by_niyam"] === true ? <p className="mt-2 text-[11.5px] text-[var(--muted-foreground)]">Test logic marked authored_by_niyam is Niyam's design, not regulation, and needs review.</p> : null}
      </section>

      <section>
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <div className="label">Source</div>
          <ProvenanceBadge provenance={r.source.provenance} />
          <OcrBadge basis={r.source.text_basis} />
          <Tag className={v.quotes_verified ? "chip-ok" : "chip-warn"} title={v.quotes_verified ? HINT.quoteVerified : HINT.quoteUnverified}>
            {v.quotes_verified ? <><CheckCircle2 size={13} aria-hidden="true" /> quotes verified</> : <><TriangleAlert size={13} aria-hidden="true" /> quotes not verified</>}
          </Tag>
        </div>
        <p className="text-[13px] font-medium">{r.source.document}</p>
        <p className="text-[12px] text-[var(--muted-foreground)]">{[r.source.reference, r.source.locator, r.source.issue_date ? fmtDate(r.source.issue_date) : null].filter(Boolean).join(" · ")}</p>
        {r.source.quotes?.length ? (
          <div className="mt-3 flex flex-col gap-2">
            {r.source.quotes.map((qt, i) => (
              <blockquote key={i} className="border-l-2 border-[var(--border)] bg-[var(--background)] px-3 py-2 text-[12.5px] leading-relaxed">“{qt}”</blockquote>
            ))}
          </div>
        ) : null}
        <p className="mt-2 break-all font-mono text-[11px] text-[var(--muted-foreground)]">{r.source.file}{r.source.sha256 ? ` · sha256 ${r.source.sha256.slice(0, 12)}…` : ""}</p>
        <p className="mt-1 text-[11.5px] text-[var(--muted-foreground)]">“Quotes verified” means the validator found each quote as an exact substring of the stored source text. It does not mean the obligation is a correct reading, or that a person has approved it.</p>
      </section>

      {v.errors.length || v.warnings.length ? (
        <section>
          <div className="label mb-2">Validation</div>
          <ul className="flex flex-col gap-1.5 text-[12.5px]">
            {v.errors.map((e, i) => <li key={`e${i}`} className="flex gap-2"><span className="chip chip-bad">error</span><span>{e}</span></li>)}
            {v.warnings.map((e, i) => <li key={`w${i}`} className="flex gap-2"><span className="chip chip-warn">warning</span><span>{e}</span></li>)}
          </ul>
        </section>
      ) : null}

      {r.open_issues?.length ? (
        <section>
          <div className="label mb-2">Open issues ({r.open_issues.length})</div>
          <ul className="list-disc space-y-1.5 pl-5 text-[12.5px] leading-relaxed">{r.open_issues.map((o, i) => <li key={i}>{o}</li>)}</ul>
        </section>
      ) : null}

      {r.notes?.length ? (
        <section>
          <div className="label mb-2">Notes</div>
          <ul className="list-disc space-y-1.5 pl-5 text-[12.5px] leading-relaxed text-[var(--muted-foreground)]">{r.notes.map((o, i) => <li key={i}>{o}</li>)}</ul>
        </section>
      ) : null}

      {r.aliases?.length ? (
        <section>
          <div className="label mb-2">Earlier demo ids</div>
          <div className="flex flex-wrap gap-1.5">{r.aliases.map((a) => <span key={a} className="chip chip-plain font-mono">{a}</span>)}</div>
        </section>
      ) : null}
    </div>
  );
}


/** Deep-linkable rule drawer: open when `?rule=<id>` is present on the current route. */
export function RuleDrawer() {
  const [params, setParams] = useSearchParams();
  const open = params.get("rule");
  const close = React.useCallback(() => setParams((p) => { p.delete("rule"); return p; }, { replace: true }), [setParams]);
  return (
    <Drawer open={!!open} onClose={close} eyebrow="Rule card" label={open ?? ""}>
      {open ? <RuleDrawerBody id={open} /> : null}
    </Drawer>
  );
}

/** Link target that opens the rule drawer on whichever page the user is on. */
export function ruleLink(search: string, id: string): string {
  const p = new URLSearchParams(search);
  p.set("rule", id);
  return `?${p.toString()}`;
}
