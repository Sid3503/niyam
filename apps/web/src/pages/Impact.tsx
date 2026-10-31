import { Link, useSearchParams } from "react-router-dom";
import { FlaskConical } from "lucide-react";
import { FindingChip, StatusBadge, Tag } from "@/components/Badges";
import { HintLabel } from "@/components/Hint";
import { HINT } from "@/lib/hints";
import { Notice } from "@/components/Notice";
import { Field, HereStrip, PageHeader } from "@/components/Page";
import { RuleDrawer, ruleLink } from "@/components/RuleDrawer";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/States";
import { useImpact, useImpactList, useRetest } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { Impact as ImpactT } from "@/lib/types";

function RetestButton({ id }: { id: string }) {
  const m = useRetest();
  return (
    <div className="flex flex-col items-start gap-1">
      <button type="button" className="btn btn-sm" disabled={m.isPending} onClick={() => m.mutate({ id })}><FlaskConical size={13} /> {m.isPending ? "Re-testing…" : "Re-test"}</button>
      {m.data ? <Tag className={m.data.passed ? "chip-ok" : "chip-bad"} title={m.data.passed ? HINT.retestPass : HINT.retestFail}>{m.data.passed ? "passed" : `not passed, ${m.data.comparison.after.open} open`}</Tag> : null}
      {m.isError ? <span role="alert" className="text-[11px] text-[var(--bad-ink)]">{m.error.message}</span> : null}
    </div>
  );
}

function ImpactBody({ d }: { d: ImpactT }) {
  const [params] = useSearchParams();
  const search = params.toString();
  return (
    <>
      {d.dry_run ? <Notice tone="warn" className="mb-4">Dry run: this rule is not approved yet. This shows what would break if a named person approved it. Nothing has changed.</Notice> : null}
      <div className="mb-5 grid gap-3 md:grid-cols-2">
        <section className="sheet p-4" aria-label="Previous version">
          <div className="label mb-2"><HintLabel label={d.previous ? `Before, v${d.previous.version}` : "Before"} hint="What this rule said on the previous version, if there was one." /></div>
          {d.previous ? (
            <>
              <p className="mb-2 text-[11.5px] text-[var(--muted-foreground)]">{d.previous.status} · effective {fmtDate(d.previous.effective_from)}</p>
              <p className="text-[13px] leading-relaxed">{d.previous.obligation}</p>
            </>
          ) : <p className="text-[13px] text-[var(--muted-foreground)]">This is a new rule. There is no earlier version.</p>}
        </section>
        <section className="sheet p-4" aria-label="New version">
          <div className="label mb-2"><HintLabel label={`After, v${d.rule.version}`} hint="The obligation this version of the rule now checks for." /></div>
          <p className="mb-2 flex flex-wrap items-center gap-1.5 text-[11.5px] text-[var(--muted-foreground)]"><StatusBadge status={d.rule.status} /> effective {fmtDate(d.rule.effective_from)} · <Link to={ruleLink(search, d.rule.id)} className="font-mono underline underline-offset-2">{d.rule.id}</Link></p>
          <p className="text-[13px] leading-relaxed">{d.rule.obligation}</p>
          {d.rule.source.quote ? <blockquote className="mt-2 border-l-2 border-[var(--taupe)] bg-[var(--background)] px-3 py-2 text-[12px] leading-relaxed">“{d.rule.source.quote}”<footer className="mt-1 text-[11px] text-[var(--muted-foreground)]">{[d.rule.source.document, d.rule.source.reference].filter(Boolean).join(" · ")}</footer></blockquote> : null}
        </section>
      </div>
      {d.previous?.changes.length ? (
        <div className="sheet mb-5 p-4"><div className="label mb-2">What changed</div><ul className="list-disc space-y-1 pl-5 text-[12.5px]">{d.previous.changes.map((c, i) => <li key={i}>{c}</li>)}</ul></div>
      ) : null}

      <h2 className="label mb-2"><HintLabel label={`Affected documents (${d.affected.length} of ${d.scanned_documents} scanned)`} hint={HINT.clockAffected} /></h2>
      {d.affected.length === 0 ? <div className="sheet"><EmptyState title="No document breaks this rule" hint={`${d.scanned_documents} documents were checked. Nothing to fix for this rule. Pick another rule, or scan the documents again.`} /></div> : (
        <div className="flex flex-col gap-3">
          {d.affected.map((a, i) => (
            <article key={`${a.document_id}-${i}`} className="sheet p-4" aria-label={`Affected ${a.title}`}>
              <div className="flex flex-wrap items-center gap-1.5">
                <FindingChip status={a.status} />
                {a.matched_on.map((m) => <span key={m} className="chip chip-plain">{m}</span>)}
              </div>
              <h3 className="mt-2 text-[14px] font-medium"><Link to={`/library/${a.document_id}`} className="underline-offset-2 hover:underline">{a.title}</Link> <span className="font-normal text-[var(--muted-foreground)]">v{a.version} · {a.clause_locator} · owner {a.owner}</span></h3>
              <p className="mt-1.5 text-[12.5px]">{a.reason}</p>
              <blockquote className="mt-2 border-l-2 border-[var(--border)] bg-[var(--background)] px-3 py-2 text-[12.5px] leading-relaxed">“{a.quote}”</blockquote>
              <p className="mt-2 text-[12.5px] text-[var(--muted-foreground)]">{a.change_note}</p>
              {a.proposed_wording ? <div className="mt-2"><div className="label mb-1"><HintLabel label="Corrected wording" hint={HINT.wording} /></div><p className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-3 text-[12.5px] leading-relaxed"><ins className="rl-ins">{a.proposed_wording}</ins></p></div> : null}
              <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                <p className="text-[12px]"><span className="label mr-2">Owner's task</span>{a.task.title} · {a.task.owner} · <span className="chip chip-plain">{a.task.state}</span></p>
                <RetestButton id={a.document_id} />
              </div>
            </article>
          ))}
        </div>
      )}
    </>
  );
}

export default function Impact() {
  const list = useImpactList();
  const [params, setParams] = useSearchParams();
  const pick = params.get("pick") ?? "";
  const [ruleId, ver] = pick.split("@");
  const version = ver ? Number(ver) : undefined;
  const q = useImpact(ruleId || null, version);

  return (
    <>
      <PageHeader eyebrow="What this circular breaks" title="Which of your proposals this circular hits" lede="Pick a rule. You get every affected deck with the stale sentence, the reason, and replacement wording. Draft rules run as a labelled dry run — nothing has gone out." />
      <HereStrip here="Each hit is a file sales would send, with the out-of-date sentence and the fix." next="Next: once a named person signs the fix, re-test that proposal." />
      <div className="sheet mb-5 p-3.5">
        <Field label="Rule" htmlFor="impact-pick">
          <select id="impact-pick" className="field" value={pick} onChange={(e) => setParams((p) => { if (e.target.value) p.set("pick", e.target.value); else p.delete("pick"); return p; }, { replace: true })}>
            <option value="">Choose a rule…</option>
            {(list.data ?? []).map((r) => <option key={`${r.rule_id}@${r.version}`} value={`${r.rule_id}@${r.version}`}>{r.title} (v{r.version}, {r.status}{r.affected_count !== null ? `, ${r.affected_count} affected` : ""})</option>)}
          </select>
        </Field>
        {list.isError ? <ErrorState error={list.error} onRetry={() => void list.refetch()} /> : null}
        {list.isLoading ? <p className="mt-2 text-[12px] text-[var(--muted-foreground)]">Loading rules…</p> : null}
      </div>
      {!ruleId ? <div className="sheet"><EmptyState title="Choose a rule to see which decks it hits" hint="Pick a rule above. Niyam lists every proposal and agreement that still says the old thing. No rules yet? Add a circular under Rules." /></div> : q.isLoading ? <div className="sheet"><LoadingBlock rows={6} label="Loading impact" /></div> : q.isError ? <div className="sheet"><ErrorState error={q.error} onRetry={() => void q.refetch()} /></div> : q.data ? <ImpactBody d={q.data} /> : null}
      <RuleDrawer />
    </>
  );
}
