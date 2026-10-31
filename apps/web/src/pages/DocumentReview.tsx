import * as React from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { ArrowLeft, FlaskConical } from "lucide-react";
import { DocStatusChip, FindingChip } from "@/components/Badges";
import { Drawer } from "@/components/Drawer";
import { Notice } from "@/components/Notice";
import { PageHeader } from "@/components/Page";
import { RuleDrawer } from "@/components/RuleDrawer";
import { FindingCard } from "@/components/workbench/FindingCard";
import { PdfWorkbench } from "@/components/workbench/PdfWorkbench";
import { VoiceReview } from "@/components/voice/VoiceReview";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/States";
import { FilterSelect } from "@/components/Filters";
import { api, useDoc, useRetest } from "@/lib/api";
import { currentApiKey } from "@/lib/settings";
import { clauseSegments, clauseTone } from "@/lib/clauses";
import { FINDING_LABEL, FINDING_RANK, fmtDateTime, humanize, shortSha } from "@/lib/format";
import { type Clause, type DocumentDetail, type Finding, type FindingStatus, type RetestResult } from "@/lib/types";

const STATUSES: FindingStatus[] = ["contradiction", "outdated", "review", "missing", "current"];

function ClauseBlock({ clause, content, findings, selected, onSelect }: { clause: Clause; content: string; findings: Finding[]; selected: boolean; onSelect: () => void }) {
  const tone = clauseTone(clause.idx, findings);
  const segs = clauseSegments(clause, content, findings);
  return (
    <button type="button" className="clause" data-selected={selected} data-tone={tone ?? undefined} aria-pressed={selected} onClick={onSelect} aria-label={`Clause ${clause.locator}`}>
      <span className="mb-0.5 block font-mono text-[10.5px] text-[var(--muted-foreground)]">{clause.locator}</span>
      <span className="block whitespace-pre-wrap text-[13px] leading-relaxed">
        {segs.map((s, i) => (s.finding ? <mark key={i} className={`hl-${tone === "ok" || s.finding.status === "current" ? "ok" : s.finding.status === "outdated" || s.finding.status === "contradiction" ? "bad" : "warn"}`} data-finding={s.finding.id}>{s.text}</mark> : <span key={i}>{s.text}</span>))}
      </span>
    </button>
  );
}

function Counts({ side }: { side: RetestResult["comparison"]["before"] }) {
  return (
    <div>
      <div className="num text-[24px] font-medium leading-none">{side.open}</div>
      <div className="mt-1.5 flex flex-wrap gap-1">
        {Object.entries(side.by_status).filter(([, n]) => n).map(([s, n]) => <span key={s} className="chip chip-plain">{n} {FINDING_LABEL[s as FindingStatus] ?? s}</span>)}
      </div>
    </div>
  );
}

function RetestDrawer({ open, onClose, detail }: { open: boolean; onClose: () => void; detail: DocumentDetail }) {
  const editable = (detail.document.format ?? "markdown") === "markdown";
  const retest = useRetest();
  const [text, setText] = React.useState(detail.version.content);
  const r = retest.data;
  React.useEffect(() => setText(detail.version.content), [detail.version.id, detail.version.content]);
  return (
    <Drawer open={open} onClose={onClose} eyebrow="Re-test" label="Re-test an edited version">
      <div className="flex flex-col gap-4">
        {editable ? (
          <>
            <Notice>Edit a copy below, then re-test it. It is saved as a new version; the original is never changed.</Notice>
            <div>
              <label htmlFor="retest-text" className="label mb-1.5 block">Edited version (prefilled with the current text)</label>
              <textarea id="retest-text" className="field min-h-[240px] font-mono text-[12px]" value={text} onChange={(e) => setText(e.target.value)} />
            </div>
          </>
        ) : <Notice>Re-test checks the latest version against the rules that are active now. To change a PDF, use Apply wording in the workbench. The original file is never changed.</Notice>}
        <div className="flex flex-wrap gap-2">
          {editable ? (
            <button type="button" className="btn btn-primary" disabled={retest.isPending || !text.trim()} onClick={() => retest.mutate({ id: detail.document.id, content: text })}>
              {retest.isPending ? "Re-testing…" : "Re-test edited version"}
            </button>
          ) : null}
          <button type="button" className={editable ? "btn" : "btn btn-primary"} disabled={retest.isPending} onClick={() => retest.mutate({ id: detail.document.id })} title="Re-check the latest version against the rules that are active now">Re-test against current rules</button>
        </div>
        {retest.isError ? <ErrorState error={retest.error} /> : null}
        {r ? (
          <section aria-label="Re-test result" className="flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <span className={r.passed ? "chip chip-ok chip-dot" : "chip chip-bad chip-dot"}>{r.passed ? "passed" : "not passed"}</span>
              <span className="text-[12.5px] text-[var(--muted-foreground)]">{r.comparison.resolved.length} resolved · {r.comparison.remaining.length} remaining · {r.comparison.new.length} new</span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg border border-[var(--border)] p-3"><div className="label mb-2">Before, open findings</div><Counts side={r.comparison.before} /></div>
              <div className="rounded-lg border border-[var(--border)] p-3"><div className="label mb-2">After, open findings</div><Counts side={r.comparison.after} /></div>
            </div>
          </section>
        ) : null}
      </div>
    </Drawer>
  );
}

function MissingPanel({ findings }: { findings: Finding[] }) {
  const missing = findings.filter((f) => f.clause_idx === null);
  return (
    <div className="sheet p-4" aria-label="Missing from this document">
      <h2 className="label mb-2">Missing from this document</h2>
      {missing.length ? (
        <ul className="flex flex-col gap-2">
          {missing.map((f) => (
            <li key={f.id} className="flex flex-wrap items-center gap-2 text-[12.5px]">
              <FindingChip status={f.status} /><span className="min-w-0 flex-1">{f.reason}</span>
            </li>
          ))}
        </ul>
      ) : <p className="text-[12.5px] text-[var(--muted-foreground)]">No required disclosure is missing.</p>}
    </div>
  );
}

function VersionsPanel({ d, latest }: { d: DocumentDetail; latest: number }) {
  const first = d.versions.reduce((a, b) => (b.version < a.version ? b : a), d.versions[0]);
  const link = (id: string | null) => (id ? `?version_id=${encodeURIComponent(id)}` : "?");
  return (
    <div className="sheet p-4" aria-label="Versions">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 className="label">Versions</h2>
        {d.versions.length > 1 ? (
          <div className="flex gap-1.5 text-[12px]">
            <Link to={link(first.id)} className="btn btn-sm" aria-current={d.version.id === first.id}>View original (v{first.version})</Link>
            <Link to={link(null)} className="btn btn-sm" aria-current={d.version.version === latest}>View current (v{latest})</Link>
          </div>
        ) : null}
      </div>
      <ul className="flex flex-col gap-1.5 text-[12.5px]">
        {d.versions.map((v) => (
          <li key={v.id} className="flex flex-wrap items-center gap-2">
            <span className="num font-medium">v{v.version}</span>
            <span className="chip chip-plain">{v.trigger}</span>
            <span>{fmtDateTime(v.created_at)}</span>
            <span className="font-mono text-[11px] text-[var(--muted-foreground)]" title={v.sha256}>{shortSha(v.sha256)}</span>
            <span className="ml-auto">{v.open_findings} open</span>
            {v.id === d.version.id ? <span className="chip chip-plain">shown</span> : <Link to={link(v.version === latest ? null : v.id)} className="text-[12px] underline underline-offset-2">View</Link>}
          </li>
        ))}
      </ul>
    </div>
  );
}

const FORMAT_LABEL = { markdown: "text", pdf: "PDF", voice: "voice note" } as const;

function Body({ d }: { d: DocumentDetail }) {
  const [sel, setSel] = React.useState<number | null>(null);
  const [filter, setFilter] = React.useState("");
  const [retestOpen, setRetestOpen] = React.useState(false);
  const closeRetest = React.useCallback(() => setRetestOpen(false), []);
  const doc = d.document;
  const format = doc.format ?? "markdown";
  const latest = d.versions.reduce((m, v) => Math.max(m, v.version), d.version.version);
  const readOnly = d.version.version < latest;
  const visible = d.findings
    .filter((f) => (sel === null || f.clause_idx === sel) && (!filter || f.status === filter))
    .sort((a, b) => FINDING_RANK[a.status] - FINDING_RANK[b.status]);
  const selClause = sel === null ? null : d.clauses.find((c) => c.idx === sel) ?? null;
  const retest = React.useCallback(() => setRetestOpen(true), []);
  const size = format === "pdf" && doc.pages ? ` · ${doc.pages} page${doc.pages === 1 ? "" : "s"}` : format === "voice" && doc.duration_seconds ? ` · ${Math.round(doc.duration_seconds)} s` : "";

  return (
    <>
      <Link to="/library" className="mb-3 inline-flex items-center gap-1.5 text-[12px] text-[var(--muted-foreground)] hover:text-[var(--foreground)]"><ArrowLeft size={13} /> Documents</Link>
      <PageHeader
        eyebrow="A file sales would send"
        title={doc.title}
        lede={`${humanize(doc.doc_type)} · ${FORMAT_LABEL[format]}${size} · ${doc.product} · owner ${doc.owner} · version ${d.version.version}${readOnly ? ` of ${latest}` : ""} · reviewed ${fmtDateTime(doc.last_reviewed_at)}. Stale sentences are marked. The original is never changed.`}
        actions={<div className="flex items-center gap-2"><DocStatusChip status={doc.status} />{doc.demo_data ? <span className="chip chip-plain">{format === "voice" ? "Synthetic demo audio" : "Synthetic demo document"}</span> : null}<button type="button" className="btn btn-primary" onClick={retest}><FlaskConical size={14} /> Re-test</button></div>}
      />
      <details className="mb-4 text-[12.5px] text-[var(--muted-foreground)]">
        <summary className="cursor-pointer font-medium text-[var(--foreground)]">What do the statuses mean?</summary>
        <ul className="mt-2 grid gap-1 sm:grid-cols-2">
          <li><b>current</b>: matches the rule and your approved terms.</li>
          <li><b>outdated</b>: says something an older rule allowed and the current one does not.</li>
          <li><b>missing</b>: a required statement is not in the document.</li>
          <li><b>contradiction</b>: says something your approved terms do not allow.</li>
          <li><b>review</b>: Niyam is unsure or has no evidence. A person must look. Never a pass.</li>
        </ul>
      </details>
      {format === "markdown" ? <Notice className="mb-5">The original is never changed. Fixes go on a copy, and every re-test is saved as a new version.</Notice> : null}
      {readOnly && format === "markdown" ? <Notice tone="warn" className="mb-5">You are viewing version {d.version.version}; the current version is {latest}. <Link to="?" className="underline underline-offset-2">Open current</Link></Notice> : null}

      {format === "pdf" && d.workbench ? (
        <>
          {readOnly ? <Notice tone="warn" className="mb-4">You are viewing version {d.version.version}; the current version is {latest}. <Link to="?" className="underline underline-offset-2">Open current</Link></Notice> : null}
          <PdfWorkbench d={d} onRetest={retest} readOnly={readOnly} currentVersion={latest} />
          <div className="mt-5 grid gap-4 md:grid-cols-2"><MissingPanel findings={d.findings} /><VersionsPanel d={d} latest={latest} /></div>
        </>
      ) : format === "voice" && d.voice ? (
        <>
          <VoiceReview d={d} onRetest={retest} readOnly={readOnly} />
          <div className="mt-5 grid gap-4 md:grid-cols-2"><MissingPanel findings={d.findings} /><VersionsPanel d={d} latest={latest} /></div>
        </>
      ) : (
        <>
          {format !== "markdown" ? <Notice tone="warn" className="mb-4">This {FORMAT_LABEL[format]} has no {format === "pdf" ? "page data" : "audio data"} in this version, so the extracted text is shown instead.</Notice> : null}
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <section aria-label="Document text" className="min-w-0">
              <div className="mb-2 flex items-center justify-between">
                <h2 className="label">Document text</h2>
                {sel !== null ? <button type="button" className="text-[12px] underline underline-offset-2" onClick={() => setSel(null)}>Show all findings</button> : null}
              </div>
              <div className="sheet flex flex-col gap-1 p-2">
                {d.clauses.length ? d.clauses.map((c) => <ClauseBlock key={c.idx} clause={c} content={d.version.content} findings={d.findings} selected={sel === c.idx} onSelect={() => setSel(sel === c.idx ? null : c.idx)} />) : <pre className="whitespace-pre-wrap p-3 text-[13px]">{d.version.content}</pre>}
              </div>
              <div className="mt-4"><MissingPanel findings={d.findings} /></div>
              <div className="mt-4"><VersionsPanel d={d} latest={latest} /></div>
            </section>

            <section aria-label="Findings" className="min-w-0">
              <div className="mb-2 flex flex-wrap items-end justify-between gap-3">
                <h2 className="label">Findings{selClause ? ` for ${selClause.locator}` : ""} ({visible.length})</h2>
                <FilterSelect id="fs" label="Status" value={filter} onChange={setFilter} options={STATUSES.map((s) => ({ value: s, label: FINDING_LABEL[s] }))} />
              </div>
              <div className="flex flex-col gap-3">
                {visible.length ? visible.map((f) => <FindingCard key={f.id} f={f} clause={d.clauses.find((c) => c.idx === f.clause_idx)} onRetest={retest} docId={doc.id} readOnly={readOnly} />) : <div className="sheet"><EmptyState title="No stale claims on this version" hint={d.findings.length ? "Clear the clause selection or the status filter to see the rest." : "If sales sent this file today, Niyam did not find a stale promise. Add a circular under Rules and re-test to check it against new rules."} /></div>}
              </div>
            </section>
          </div>
        </>
      )}
      <RetestDrawer open={retestOpen} onClose={closeRetest} detail={d} />
      <RuleDrawer />
    </>
  );
}

export default function DocumentReview() {
  const { documentId } = useParams();
  const [params] = useSearchParams();
  const versionId = params.get("version_id");
  const latestQ = useDoc(versionId ? null : documentId ?? null);
  const verQ = useQuery({
    queryKey: ["document", documentId, currentApiKey(), versionId],
    queryFn: () => api.docVersion(documentId as string, versionId as string),
    enabled: !!documentId && !!versionId,
    placeholderData: keepPreviousData,
  });
  const q = versionId ? verQ : latestQ;
  if (q.isLoading) return <div className="sheet"><LoadingBlock rows={10} label="Loading document" /></div>;
  if (q.isError) return <div className="sheet"><ErrorState error={q.error} onRetry={() => void q.refetch()} /></div>;
  return q.data ? <Body d={q.data} /> : null;
}
