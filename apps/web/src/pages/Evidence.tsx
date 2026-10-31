import * as React from "react";
import { useSearchParams } from "react-router-dom";
import { Download, FileDown } from "lucide-react";
import { ApprovalChip, Chip, FindingChip } from "@/components/Badges";
import { Drawer } from "@/components/Drawer";
import { PageHeader } from "@/components/Page";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/States";
import { api, useDoc, useEvidence, useEvidenceList } from "@/lib/api";
import { HashRow } from "@/components/workbench/ApplyView";
import { CompareView } from "@/components/workbench/CompareView";
import { downloadBlob } from "@/components/workbench/useBlobUrl";
import { downloadText } from "@/lib/download";
import { fmtDateTime } from "@/lib/format";

function CompareSection({ id }: { id: string }) {
  const d = useDoc(id);
  if (d.isLoading) return <LoadingBlock rows={3} label="Loading versions" />;
  if (d.isError) return <ErrorState error={d.error} onRetry={() => void d.refetch()} />;
  return d.data ? <CompareView documentId={id} versions={d.data.versions} /> : null;
}

function EvidenceBody({ id }: { id: string }) {
  const q = useEvidence(id);
  const [busy, setBusy] = React.useState(false);
  const [packBusy, setPackBusy] = React.useState(false);
  const [err, setErr] = React.useState<unknown>(null);
  if (q.isLoading) return <LoadingBlock rows={8} label="Loading evidence" />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  const r = q.data!;
  const exportMd = async () => {
    setBusy(true); setErr(null);
    try { downloadText(`evidence-${id}.md`, await api.evidenceExport(id)); } catch (e) { setErr(e); } finally { setBusy(false); }
  };
  const format = r.format ?? r.document.format ?? "markdown";
  const pack = async () => {
    setPackBusy(true); setErr(null);
    try { downloadBlob(`evidence-pack-${id}.pdf`, await api.evidencePack(id)); } catch (e) { setErr(e); } finally { setPackBusy(false); }
  };
  return (
    <div className="flex flex-col gap-5">
      <div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="chip chip-plain" data-testid="evidence-format">{format === "pdf" ? "PDF" : format === "voice" ? "Voice note" : "Text"}</span>
          <Chip tone={r.chain_ok ? "ok" : "bad"} title="Each log entry is chained to the one before it. Intact means no entry was altered.">{r.chain_ok ? "audit log intact" : "audit log broken"}</Chip>
          <span className="chip chip-plain">{format === "voice" ? "Synthetic demo audio" : "Synthetic demo document"}</span>
        </div>
        <h2 className="mt-3 text-[22px] font-light leading-tight">{r.document.title}</h2>
        <div className="mt-3 flex flex-col gap-1.5" aria-label="SHA-256 fingerprints">
          <HashRow label={`original v${r.hashes?.original.version ?? r.original.version}`} sha={r.hashes?.original.sha256 ?? r.original.sha256} />
          {r.hashes ? <HashRow label={`current v${r.hashes.current.version}`} sha={r.hashes.current.sha256} /> : null}
          <p className="text-[11.5px] text-[var(--muted-foreground)]">SHA-256 of the file bytes. The original is never changed; each committed edit is a new version with its own hash.</p>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={() => void exportMd()}><Download size={13} /> {busy ? "Preparing…" : "Export record (.md)"}</button>
          {format === "pdf" ? <button type="button" className="btn btn-sm" disabled={packBusy} onClick={() => void pack()}><FileDown size={13} /> {packBusy ? "Building the pack…" : "Download evidence pack (PDF)"}</button> : null}
        </div>
        {format === "pdf" ? <p className="mt-1.5 text-[11.5px] text-[var(--muted-foreground)]">The pack has a cover with findings, approvals, re-tests, both hashes and chain status, then the latest PDF with metadata stripped. The pack is not encrypted and personal data is not redacted.</p> : null}
        {err ? <div className="mt-2"><ErrorState error={err} /></div> : null}
      </div>

      {format === "pdf" ? <section aria-label="Compare versions"><div className="label mb-2">Compare versions</div><CompareSection id={id} /></section> : null}

      <section><div className="label mb-2">Timeline ({r.events.length})</div>
        {r.events.length === 0 ? <p className="text-[12.5px] text-[var(--muted-foreground)]">Nothing has happened to this document yet.</p> : (
          <ol className="flex flex-col border-l border-[var(--border)]">
            {r.events.map((e) => (
              <li key={e.seq} className="relative -ml-px border-l-2 border-[var(--taupe)] py-1.5 pl-4 text-[12.5px]">
                <span className="font-mono text-[10.5px] text-[var(--muted-foreground)]">#{e.seq} · {fmtDateTime(e.ts)} · {e.actor}</span>
                <div><span className="font-medium">{e.action}</span> {e.summary}</div>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section><div className="label mb-2">Findings ({r.findings.length})</div>
        <ul className="flex flex-col gap-2">{r.findings.map((f) => <li key={f.id} className="flex flex-wrap items-center gap-2 text-[12.5px]"><FindingChip status={f.status} /><span className="min-w-0 flex-1">{f.reason}</span></li>)}</ul>
        {r.findings.length === 0 ? <p className="text-[12.5px] text-[var(--muted-foreground)]">No findings.</p> : null}
      </section>

      <section><div className="label mb-2">Approvals ({r.approvals.length})</div>
        <ul className="flex flex-col gap-2">{r.approvals.map((a) => <li key={a.id} className="flex flex-wrap items-center gap-2 text-[12.5px]"><ApprovalChip status={a.status} /><span className="min-w-0 flex-1">{a.title}{a.decided_by ? `, ${a.decided_by}, ${fmtDateTime(a.decided_at)}` : ""}</span></li>)}</ul>
        {r.approvals.length === 0 ? <p className="text-[12.5px] text-[var(--muted-foreground)]">No approvals yet. The name of whoever approves a fix will appear here.</p> : null}
      </section>

      <section><div className="label mb-2">Re-tests ({r.retests.length})</div>
        <ul className="flex flex-col gap-2">{r.retests.map((t, i) => <li key={i} className="flex flex-wrap items-center gap-2 text-[12.5px]"><Chip tone={t.passed ? "ok" : "bad"}>{t.passed ? "passed" : "not passed"}</Chip>{fmtDateTime(t.ts)} · {t.before.open} open before, {t.after.open} after</li>)}</ul>
        {r.retests.length === 0 ? <p className="text-[12.5px] text-[var(--muted-foreground)]">No re-test yet. Run one after a fix is approved.</p> : null}
      </section>

      <section><div className="label mb-2">Notifications ({r.notifications.length})</div>
        <ul className="flex flex-col gap-1.5 text-[12.5px]">{r.notifications.map((n, i) => <li key={i}>{fmtDateTime(n.ts)} · to {n.to} · {n.channel.replace("_", "-")} · {n.subject}</li>)}</ul>
        {r.notifications.length === 0 ? <p className="text-[12.5px] text-[var(--muted-foreground)]">No notifications sent.</p> : null}
      </section>
    </div>
  );
}

export default function Evidence() {
  const q = useEvidenceList();
  const [params, setParams] = useSearchParams();
  const open = params.get("document");
  const close = React.useCallback(() => setParams((p) => { p.delete("document"); return p; }, { replace: true }), [setParams]);
  const rows = q.data ?? [];
  return (
    <>
      <PageHeader eyebrow="Evidence" title="The proof pack" lede="For each document: what was out of date, which fix was approved and by whom, whether the re-test passed, and a tamper-evident log. Open a row to export it." />
      <div className="sheet overflow-hidden">
        {q.isLoading ? <LoadingBlock rows={6} label="Loading evidence" /> : q.isError ? <ErrorState error={q.error} onRetry={() => void q.refetch()} /> : rows.length === 0 ? <EmptyState title="No proof to show yet" hint="Scan a document and its evidence record starts here. It grows with every approval and re-test, and exports for audit." /> : (
          <div className="overflow-x-auto">
            <table className="tbl min-w-[760px]">
              <caption className="sr-only">Evidence per document. Select a row to open the record.</caption>
              <thead><tr><th scope="col">Document</th><th scope="col">Versions</th><th scope="col">Findings</th><th scope="col">Approvals</th><th scope="col">Last event</th><th scope="col">Re-test</th></tr></thead>
              <tbody>
                {rows.map((e) => (
                  <tr key={e.document_id} className="row" onClick={() => setParams({ document: e.document_id })}>
                    <td><button type="button" className="text-left font-medium" aria-label={`Open evidence for ${e.title}`} onClick={(ev) => { ev.stopPropagation(); setParams({ document: e.document_id }); }}>{e.title}</button></td>
                    <td className="num">{e.versions}</td><td className="num">{e.findings}</td><td className="num">{e.approvals}</td>
                    <td className="whitespace-nowrap">{fmtDateTime(e.last_event_at)}</td>
                    <td><Chip tone={e.retest === "passed" ? "ok" : e.retest === "failed" ? "bad" : "neutral"}>{e.retest === "none" ? "not yet" : e.retest}</Chip></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <Drawer open={!!open} onClose={close} eyebrow="Evidence record" label={open ?? ""}>{open ? <EvidenceBody id={open} /> : null}</Drawer>
    </>
  );
}
