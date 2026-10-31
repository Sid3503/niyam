import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Eye, GitCommitHorizontal, Plus } from "lucide-react";
import { Notice } from "@/components/Notice";
import { EmptyState, LoadingBlock } from "@/components/States";
import { FilterSelect } from "@/components/Filters";
import { api } from "@/lib/api";
import { FINDING_LABEL, FINDING_RANK } from "@/lib/format";
import { currentApiKey } from "@/lib/settings";
import type { ApplyResult, DocumentDetail, Finding, FindingStatus } from "@/lib/types";
import { ApplyError, ComparisonView, HashRow, StaleTextList, staleFromError, StrategyList } from "./ApplyView";
import { FindingCard } from "./FindingCard";
import { editsReducer, emptyEdits, isAppendEdit, toApplyEdits } from "./pendingEdits";
import type { FocusRequest } from "./PdfViewer";

// pdf.js is large: load it only when a PDF is opened.
const PdfViewer = React.lazy(() => import("./PdfViewer").then((m) => ({ default: m.PdfViewer })));

const STATUSES: FindingStatus[] = ["contradiction", "outdated", "review", "missing", "current"];
const REVIEW_KEYS = ["overview", "library", "document", "evidence-list", "evidence", "impact", "impact-list"];

function ApplyToggle({ f, on, wording, onToggle, onChange }: { f: Finding; on: boolean; wording: string; onToggle: () => void; onChange: (v: string) => void }) {
  const append = isAppendEdit(f);
  const id = `apply-${f.id}`;
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-3">
      <label className="flex cursor-pointer items-center gap-2 text-[12.5px] font-medium">
        <input type="checkbox" checked={on} onChange={onToggle} aria-label="Apply wording" />
        Apply wording
        <span className="chip chip-plain">{append ? "appended as new text" : "replaces text on the page"}</span>
      </label>
      {append ? <p className="mt-1 text-[11.5px] text-[var(--muted-foreground)]">No location on a page. It is added as an “Additional terms” block on the last page.</p> : null}
      {on ? (
        <div className="mt-2">
          <label htmlFor={id} className="label mb-1 block">Wording to write into the copy (editable)</label>
          <textarea id={id} className="field min-h-[84px] text-[12.5px]" value={wording} onChange={(e) => onChange(e.target.value)} />
          {!wording.trim() ? <p role="alert" className="mt-1 text-[11.5px] text-[var(--bad-ink)]">Empty wording is skipped: deleting text is not a fix.</p> : null}
        </div>
      ) : null}
    </div>
  );
}

export function PdfWorkbench({ d, onRetest, readOnly, currentVersion }: { d: DocumentDetail; onRetest: () => void; readOnly: boolean; currentVersion: number }) {
  const wb = d.workbench!;
  const qc = useQueryClient();
  const [sel, setSel] = React.useState<string | null>(null);
  const [focus, setFocus] = React.useState<FocusRequest | null>(null);
  const [filter, setFilter] = React.useState("");
  const [edits, dispatch] = React.useReducer(editsReducer, emptyEdits);
  const [preview, setPreview] = React.useState<{ r: ApplyResult; key: string } | null>(null);
  const [committed, setCommitted] = React.useState<ApplyResult | null>(null);
  const [showPreviewPdf, setShowPreviewPdf] = React.useState(false);
  const [confirming, setConfirming] = React.useState(false);
  const nonce = React.useRef(0);

  // A different version (or a new commit) invalidates anything built from the old one.
  React.useEffect(() => { setPreview(null); setShowPreviewPdf(false); dispatch({ type: "clear" }); setConfirming(false); }, [d.version.id]);

  const editKey = JSON.stringify(toApplyEdits(edits));
  const nEdits = toApplyEdits(edits).length;
  const previewCurrent = preview !== null && preview.key === editKey;

  const run = useMutation<ApplyResult, unknown, { commit: boolean }>({
    mutationFn: ({ commit }) => api.apply(d.document.id, toApplyEdits(edits), commit),
    onSuccess: (r, { commit }) => {
      setConfirming(false);
      if (commit) {
        setCommitted(r);
        setPreview(null);
        setShowPreviewPdf(false);
        dispatch({ type: "clear" });
        if (r.document) qc.setQueryData(["document", d.document.id, currentApiKey()], r.document);
        for (const key of REVIEW_KEYS) void qc.invalidateQueries({ queryKey: [key] });
      } else {
        setCommitted(null);
        setPreview({ r, key: editKey });
        setShowPreviewPdf(!!r.preview_url);
      }
    },
    onError: () => setConfirming(false),
  });

  const select = (f: Finding, scrollCard: boolean) => {
    setSel(f.id);
    setShowPreviewPdf(false);
    if (f.page) setFocus({ page: f.page, y: f.bbox?.[1], nonce: ++nonce.current });
    if (scrollCard) document.querySelector(`[data-finding-card="${CSS.escape(f.id)}"]`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  };

  const visible = d.findings.filter((f) => !filter || f.status === filter).sort((a, b) => FINDING_RANK[a.status] - FINDING_RANK[b.status]);
  const viewingPreview = showPreviewPdf && preview?.r.preview_url;
  const viewerUrl = viewingPreview ? (preview!.r.preview_url as string) : wb.pdf_url;
  const stale = run.isError ? staleFromError(run.error) : preview?.r.stale_text_remains ?? [];
  const canApply = !readOnly && nEdits > 0 && !run.isPending;

  return (
    <div className="flex flex-col gap-4">
      <Notice>The original file is never changed. Commit creates a new version.</Notice>
      {readOnly ? <Notice tone="warn">You are viewing an earlier version. Open the current version to apply wording.</Notice> : null}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <section aria-label="PDF viewer" className="min-w-0">
          {preview?.r.preview_url ? (
            <div className="mb-2 inline-flex rounded-lg border border-[var(--border)] p-0.5 text-[12px]" role="group" aria-label="Which file to show">
              <button type="button" className={`rounded-md px-2.5 py-1 ${!viewingPreview ? "bg-[var(--accent)] font-medium" : ""}`} aria-pressed={!viewingPreview} onClick={() => setShowPreviewPdf(false)}>Version {d.version.version}</button>
              <button type="button" className={`rounded-md px-2.5 py-1 ${viewingPreview ? "bg-[var(--accent)] font-medium" : ""}`} aria-pressed={!!viewingPreview} onClick={() => setShowPreviewPdf(true)}>Working copy (preview)</button>
            </div>
          ) : null}
          <React.Suspense fallback={<LoadingBlock rows={6} label="Loading PDF viewer" />}>
          <PdfViewer
            url={viewerUrl}
            pageSizes={viewingPreview ? undefined : wb.page_sizes}
            findings={d.findings}
            selectedId={sel}
            onSelect={(id) => { const f = d.findings.find((x) => x.id === id); if (f) select(f, true); }}
            focus={focus}
            showOverlays={!viewingPreview}
            badge={viewingPreview
              ? <span className="chip chip-warn chip-plain" data-testid="working-copy-badge">Working copy - not saved</span>
              : <span className="chip chip-plain">v{d.version.version} · {wb.pages} page{wb.pages === 1 ? "" : "s"}</span>}
          />
          </React.Suspense>
          {viewingPreview ? <p className="mt-2 text-[11.5px] text-[var(--muted-foreground)]">Finding boxes are hidden on the working copy: they mark positions in the saved version. Nothing here is stored until you commit.</p> : null}
        </section>

        <section aria-label="Findings" className="flex min-w-0 flex-col gap-3 lg:max-h-[86vh] lg:overflow-y-auto lg:pr-1">
          <div className="sheet p-4" aria-label="Pending edits">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="label">Pending edits ({nEdits})</h2>
              {nEdits ? <button type="button" className="text-[12px] underline underline-offset-2" onClick={() => dispatch({ type: "clear" })}>Clear all</button> : null}
            </div>
            {nEdits === 0 ? (
              <p className="mt-2 text-[12.5px] text-[var(--muted-foreground)]">Turn on “Apply wording” on a finding with drafted wording. Nothing is written until you preview or commit, and never to the original.</p>
            ) : (
              <ul className="mt-2 flex flex-col gap-1.5 text-[12.5px]">
                {toApplyEdits(edits).map((e) => {
                  const f = d.findings.find((x) => x.id === e.finding_id);
                  return <li key={e.finding_id} className="flex items-center gap-2"><Plus size={12} aria-hidden="true" /><span className="min-w-0 flex-1 truncate">{f ? `${f.locator || "finding"}${f.page ? ` · p${f.page}` : ""}: ${e.wording}` : e.wording}</span><button type="button" className="text-[11.5px] underline" onClick={() => dispatch({ type: "remove", id: e.finding_id })}>Remove</button></li>;
                })}
              </ul>
            )}
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <button type="button" className="btn btn-sm" disabled={!canApply} onClick={() => run.mutate({ commit: false })}><Eye size={13} /> {run.isPending && !run.variables?.commit ? "Building preview…" : "Preview apply"}</button>
              {confirming ? (
                <>
                  <button type="button" className="btn btn-sm btn-primary" disabled={!canApply} onClick={() => run.mutate({ commit: true })}>{run.isPending ? "Committing…" : `Confirm: commit version ${currentVersion + 1}`}</button>
                  <button type="button" className="btn btn-sm" onClick={() => setConfirming(false)}>Cancel</button>
                </>
              ) : (
                <button type="button" className="btn btn-sm btn-primary" disabled={!canApply} onClick={() => setConfirming(true)}><GitCommitHorizontal size={13} /> Commit as version {currentVersion + 1}</button>
              )}
            </div>
            {confirming ? <p className="mt-2 text-[11.5px] text-[var(--muted-foreground)]">This stores version {currentVersion + 1} with its SHA-256 on the evidence record. It is refused if any old wording is still extractable. The original and earlier versions stay as they are.</p> : null}
            {preview && !previewCurrent ? <p role="note" className="mt-2 text-[11.5px] text-[var(--warn-ink)]">Edits changed since this preview. Preview again before relying on it.</p> : null}
          </div>

          {run.isError ? <ApplyError error={run.error} stale={stale} findings={d.findings} /> : null}

          {preview ? (
            <div className="sheet flex flex-col gap-3 p-4" aria-label="Preview result">
              <div className="flex flex-wrap items-center gap-2"><h2 className="label">Preview</h2><span className="chip chip-warn chip-plain">Working copy - not saved</span></div>
              <StrategyList r={preview.r} findings={d.findings} />
              <StaleTextList items={preview.r.stale_text_remains} findings={d.findings} />
              {preview.r.stale_text_remains.length === 0 ? <p className="text-[12px] text-[var(--ok-ink)]">No old wording remains extractable in this working copy.</p> : null}
              <ComparisonView r={preview.r} findings={d.findings} mode="preview" />
            </div>
          ) : null}

          {committed ? (
            <div className="sheet flex flex-col gap-3 p-4" aria-label="Commit result" data-testid="commit-result">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="label">Committed</h2>
                <span className={committed.committed ? "chip chip-ok chip-dot" : "chip chip-bad chip-dot"}>{committed.committed ? `version ${committed.document?.version.version ?? currentVersion} saved` : "not saved"}</span>
                <span className={committed.comparison.after.open === 0 && committed.comparison.remaining.length === 0 ? "chip chip-ok chip-dot" : "chip chip-warn chip-dot"}>{committed.comparison.after.open === 0 && committed.comparison.remaining.length === 0 ? "re-test passed" : "re-test not passed"}</span>
              </div>
              <p className="text-[12px] text-[var(--muted-foreground)]">Niyam re-tested the new file's text. Approving the wording is a separate step that only a named person can take.</p>
              <div className="flex flex-col gap-1.5">
                <HashRow label="before" sha={committed.sha256_before} />
                <HashRow label="after" sha={committed.sha256_after} />
              </div>
              <StrategyList r={committed} findings={d.findings} />
              <ComparisonView r={committed} findings={d.findings} mode="committed" />
            </div>
          ) : null}

          <div className="flex flex-wrap items-end justify-between gap-3">
            <h2 className="label">Findings ({visible.length})</h2>
            <FilterSelect id="fs" label="Status" value={filter} onChange={setFilter} options={STATUSES.map((s) => ({ value: s, label: FINDING_LABEL[s] }))} />
          </div>
          {visible.length ? visible.map((f) => (
            <FindingCard
              key={f.id}
              f={f}
              clause={d.clauses.find((c) => c.idx === f.clause_idx)}
              onRetest={onRetest}
              docId={d.document.id}
              selected={sel === f.id}
              onSelect={() => select(f, false)}
              readOnly={readOnly}
              extra={f.suggested_fix && !readOnly ? (
                <ApplyToggle
                  f={f}
                  on={f.id in edits.wording}
                  wording={edits.wording[f.id] ?? ""}
                  onToggle={() => dispatch({ type: "toggle", id: f.id, wording: f.suggested_fix!.wording })}
                  onChange={(v) => dispatch({ type: "set", id: f.id, wording: v })}
                />
              ) : !f.page && !f.bbox ? <p className="text-[11.5px] text-[var(--muted-foreground)]">No location on a page for this finding.</p> : null}
            />
          )) : <div className="sheet"><EmptyState title="No findings here" hint={d.findings.length ? "Clear the status filter." : "Nothing was flagged in this version."} /></div>}
        </section>
      </div>
    </div>
  );
}
