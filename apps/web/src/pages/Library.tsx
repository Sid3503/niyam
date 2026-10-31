import * as React from "react";
import { titleFromFilename } from "@/lib/format";
import { FilePicker } from "@/components/FilePicker";
import { Link, useNavigate } from "react-router-dom";
import { FileText, FileType2, Mic, Plus, ScanSearch } from "lucide-react";
import { Drawer } from "@/components/Drawer";
import { DocStatusChip } from "@/components/Badges";
import { Hint, HintLabel } from "@/components/Hint";
import { HINT } from "@/lib/hints";
import { Notice } from "@/components/Notice";
import { Field, HereStrip, PageHeader } from "@/components/Page";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/States";
import { VoiceRecorder } from "@/components/voice/VoiceRecorder";
import { VoiceSamples } from "@/components/voice/VoiceSamples";
import { fmtClock } from "@/components/voice/audio";
import { useApprovals, useLibrary, useScan, useUpload, useUploadFile } from "@/lib/api";
import { fmtDate, fmtDateTime, humanize } from "@/lib/format";
import { fixStatusText, summarizeFixes, type FixSummary } from "@/lib/fixStatus";
import type { Document, DocFormat, ScanResult, UploadBody } from "@/lib/types";

const DOC_TYPES = ["proposal", "agreement", "order_form", "brochure", "pitch_deck", "onboarding"];

function ScanPanel({ r, onClose }: { r: ScanResult; onClose: () => void }) {
  return (
    <div className="sheet mb-4 p-4" role="status" aria-label="Scan result">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="label">Scan finished · {fmtDateTime(r.started_at)}</div>
          <p className="mt-2 text-[13px]">
            <span className="num font-medium">{r.discovered}</span> discovered · <span className="num font-medium">{r.reviewed}</span> reviewed · <span className="num font-medium">{r.skipped}</span> skipped (nothing changed since the last scan)
          </p>
        </div>
        <button type="button" className="btn btn-sm" onClick={onClose}>Dismiss</button>
      </div>
      {r.documents.length ? (
        <ul className="mt-3 flex flex-col gap-1 text-[12.5px]">
          {r.documents.map((d) => (
            <li key={d.document_id} className="flex flex-wrap items-center gap-2">
              <Link to={`/library/${d.document_id}`} className="underline-offset-2 hover:underline">{d.title}</Link>
              <span className="chip chip-plain">{humanize(d.outcome)}</span>
              <span className="text-[var(--muted-foreground)]">{d.findings} finding{d.findings === 1 ? "" : "s"}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function PasteForm({ onClose }: { onClose: () => void }) {
  const upload = useUpload();
  const navigate = useNavigate();
  const autoTitle = React.useRef("");
  const [f, setF] = React.useState<UploadBody>({ title: "", doc_type: "proposal", product: "", owner: "", content: "" });
  const set = (k: keyof UploadBody) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setF((o) => ({ ...o, [k]: e.target.value }));
  const valid = f.title.trim() && f.product.trim() && f.owner.trim() && f.content.trim();
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    upload.mutate(f, { onSuccess: (d) => { onClose(); navigate(`/library/${d.document.id}`); } });
  };
  return (
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Notice>Pasted text is saved as a new version and reviewed straight away. Document text is sent to a hosted language model to draft and judge, so use synthetic or approved text in this demo. To keep a PDF as the original and edit a copy, use Upload file.</Notice>
        <Field label="Title" htmlFor="up-title"><input id="up-title" className="field" value={f.title} onChange={set("title")} required /></Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Type" htmlFor="up-type">
            <select id="up-type" className="field" value={f.doc_type} onChange={set("doc_type")}>{DOC_TYPES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}</select>
          </Field>
          <Field label="Product" htmlFor="up-product"><input id="up-product" className="field" value={f.product} onChange={set("product")} placeholder="e.g. Payment gateway" required /></Field>
        </div>
        <Field label="Owner" htmlFor="up-owner"><input id="up-owner" className="field" value={f.owner} onChange={set("owner")} placeholder="Sales owner" required /></Field>
        <FilePicker label="Choose a document (PDF, DOCX, TXT, MD)" onText={(r) => setF((o) => ({ ...o, content: r.text, title: !o.title || o.title === autoTitle.current ? (autoTitle.current = titleFromFilename(r.filename)) : o.title }))} />
        <Field label="Document text" htmlFor="up-content"><textarea id="up-content" className="field min-h-[260px] font-mono text-[12px]" value={f.content} onChange={set("content")} required /></Field>
        {upload.isError ? <ErrorState error={upload.error} /> : null}
        <div className="flex gap-2">
          <button type="submit" className="btn btn-primary" disabled={!valid || upload.isPending}>{upload.isPending ? "Reviewing…" : "Add and review"}</button>
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
        </div>
      </form>
  );
}


const AUDIO_EXT = /\.(wav|mp3|m4a|ogg|webm)$/i;
const isAudioName = (n: string, type: string) => type.startsWith("audio/") || AUDIO_EXT.test(n);

function Meta({ f, set, idp, showType }: { f: { title: string; doc_type: string; product: string; owner: string; merchant: string }; set: (k: "title" | "doc_type" | "product" | "owner" | "merchant") => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void; idp: string; showType: boolean }) {
  return (
    <>
      <Field label="Title (optional)" htmlFor={`${idp}-title`}><input id={`${idp}-title`} className="field" value={f.title} onChange={set("title")} /></Field>
      <div className="grid gap-3 sm:grid-cols-2">
        {showType ? (
          <Field label="Type" htmlFor={`${idp}-type`}>
            <select id={`${idp}-type`} className="field" value={f.doc_type} onChange={set("doc_type")}>{DOC_TYPES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}</select>
          </Field>
        ) : null}
        <Field label="Product" htmlFor={`${idp}-product`}><input id={`${idp}-product`} className="field" value={f.product} onChange={set("product")} placeholder="e.g. Payment gateway" required /></Field>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Owner" htmlFor={`${idp}-owner`}><input id={`${idp}-owner`} className="field" value={f.owner} onChange={set("owner")} placeholder="Sales owner" required /></Field>
        <Field label="Merchant (optional)" htmlFor={`${idp}-merchant`}><input id={`${idp}-merchant`} className="field" value={f.merchant} onChange={set("merchant")} /></Field>
      </div>
    </>
  );
}

const blankMeta = { title: "", doc_type: "proposal", product: "", owner: "", merchant: "" };

function UploadFileForm({ onDone }: { onDone: (id: string) => void }) {
  const up = useUploadFile();
  const input = React.useRef<HTMLInputElement>(null);
  const [file, setFile] = React.useState<File | null>(null);
  const [m, setM] = React.useState(blankMeta);
  const set = (k: keyof typeof blankMeta) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setM((o) => ({ ...o, [k]: e.target.value }));
  const audio = file ? isAudioName(file.name, file.type) : false;
  const valid = !!file && m.product.trim() && m.owner.trim();
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !valid) return;
    up.mutate({ file, filename: file.name, doc_type: audio ? "voice_note" : m.doc_type, product: m.product.trim(), owner: m.owner.trim(), merchant: m.merchant.trim() || undefined, title: m.title.trim() || undefined }, { onSuccess: (d) => onDone(d.document.id) });
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <Notice>A PDF is kept as the original and never altered. Niyam reads its text, then reviews it. Audio is transcribed and reviewed. Scanned, image-only PDFs cannot be read yet.</Notice>
      <div className="flex flex-col items-start gap-2 rounded-xl border border-dashed p-4">
        <input ref={input} type="file" hidden accept=".pdf,application/pdf,.wav,.mp3,.m4a,.ogg,.webm,audio/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} aria-label="Choose a PDF or audio file" />
        <button type="button" className="btn btn-sm" onClick={() => input.current?.click()}>Choose a PDF or audio file</button>
        <p className="text-[12px] text-[var(--muted-foreground)]">PDF, or audio: WAV, MP3, M4A, OGG, WEBM.</p>
        {file ? <p className="text-[12px]">Selected: {file.name} ({audio ? "audio" : "PDF"}, {(file.size / 1024 / 1024).toFixed(1)} MB)</p> : null}
      </div>
      <Meta f={m} set={set} idp="uf" showType={!audio} />
      {up.isError ? <p role="alert" className="rounded-lg border border-[var(--bad-line)] bg-[var(--bad-bg)] px-3 py-2 text-[12.5px] text-[var(--bad-ink)]">{up.error.message}{(up.error as { code?: string }).code === "no_text" ? " This PDF has no selectable text (it looks like a scan). Niyam cannot read scanned pages yet." : ""}</p> : null}
      <div className="flex gap-2"><button type="submit" className="btn btn-primary" disabled={!valid || up.isPending}>{up.isPending ? "Reviewing…" : "Add and review"}</button></div>
    </form>
  );
}

function VoiceForm({ onDone }: { onDone: (id: string) => void }) {
  const up = useUploadFile();
  const [rec, setRec] = React.useState<{ blob: Blob; filename: string } | null>(null);
  const [m, setM] = React.useState({ ...blankMeta, doc_type: "voice_note" });
  const set = (k: keyof typeof blankMeta) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setM((o) => ({ ...o, [k]: e.target.value }));
  const valid = !!rec && m.product.trim() && m.owner.trim();
  return (
    <div className="flex flex-col gap-5">
      <Notice>Spoken promises are checked against the same rules as your documents. The clips below are synthetic demo audio. A recording from your microphone is sent to the server to be transcribed.</Notice>
      <section className="flex flex-col gap-3" aria-label="Record a voice note">
        <div className="label">Record</div>
        <VoiceRecorder onRecorded={setRec} disabled={up.isPending} />
        {rec ? (
          <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); if (!rec || !valid) return; up.mutate({ file: rec.blob, filename: rec.filename, doc_type: "voice_note", product: m.product.trim(), owner: m.owner.trim(), merchant: m.merchant.trim() || undefined, title: m.title.trim() || undefined }, { onSuccess: (d) => onDone(d.document.id) }); }}>
            <Meta f={m} set={set} idp="vr" showType={false} />
            {up.isError ? <p role="alert" className="rounded-lg border border-[var(--bad-line)] bg-[var(--bad-bg)] px-3 py-2 text-[12.5px] text-[var(--bad-ink)]">{up.error.message}</p> : null}
            <div><button type="submit" className="btn btn-primary" disabled={!valid || up.isPending}>{up.isPending ? "Reviewing…" : "Add recording and review"}</button></div>
          </form>
        ) : null}
      </section>
      <VoiceSamples onDone={(d) => onDone(d.document.id)} />
    </div>
  );
}

type Mode = "paste" | "file" | "voice";
const MODES: { id: Mode; label: string }[] = [{ id: "paste", label: "Paste text" }, { id: "file", label: "Upload file" }, { id: "voice", label: "Voice note" }];

function AddDocumentDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const [mode, setMode] = React.useState<Mode>("paste");
  const done = (id: string) => { onClose(); navigate(`/library/${id}`); };
  return (
    <Drawer open={open} onClose={onClose} eyebrow="Add document" label="Add a document to review">
      <div role="tablist" aria-label="How to add" className="mb-4 inline-flex rounded-lg border border-[var(--border)] p-0.5 text-[12.5px]">
        {MODES.map((x) => <button key={x.id} id={`tab-${x.id}`} role="tab" type="button" aria-selected={mode === x.id} aria-controls="add-panel" className={`rounded-md px-3 py-1.5 ${mode === x.id ? "bg-[var(--accent)] font-medium" : ""}`} onClick={() => setMode(x.id)}>{x.label}</button>)}
      </div>
      <div id="add-panel" role="tabpanel" aria-labelledby={`tab-${mode}`}>
        {mode === "paste" ? <PasteForm onClose={onClose} /> : mode === "file" ? <UploadFileForm onDone={done} /> : <VoiceForm onDone={done} />}
      </div>
    </Drawer>
  );
}

const FORMAT_META: Record<DocFormat, { label: string; Icon: typeof FileText }> = {
  markdown: { label: "Text", Icon: FileText },
  pdf: { label: "PDF", Icon: FileType2 },
  voice: { label: "Voice", Icon: Mic },
};
/** asha.verma@demo.paytm.example -> Asha Verma (full address stays in the tooltip) */
function ownerName(o: string): string {
  return o.split("@")[0].split(/[._]/).filter(Boolean).map((w) => w[0].toUpperCase() + w.slice(1)).join(" ") || o;
}

function FixCell({ s, failed }: { s: FixSummary | undefined; failed: boolean }) {
  if (failed) return <span className="text-[var(--muted-foreground)]" aria-label="Fix status unavailable">—</span>;
  const named = s?.approvals.length ? s.approvals.map((a) => `Approved by ${a.by ?? "approver not recorded"}${a.at ? `, ${fmtDateTime(a.at)}` : ""}`).join(". ") : "";
  const tip = named || HINT.fixStatus;
  return <Hint text={tip}><span className="text-[12.5px]">{fixStatusText(s)}</span></Hint>;
}

function FormatCell({ d }: { d: Document }) {
  const { label, Icon } = FORMAT_META[d.format ?? "markdown"];
  const size = d.format === "pdf" && d.pages ? `${d.pages} p` : d.format === "voice" && d.duration_seconds ? fmtClock(d.duration_seconds) : null;
  return <span className="inline-flex items-center gap-1.5 whitespace-nowrap"><Icon size={14} aria-hidden="true" className="text-[var(--taupe)]" />{label}{size ? <span className="text-[var(--muted-foreground)]"> · {size}</span> : null}</span>;
}

export default function Library() {
  const q = useLibrary();
  const scan = useScan();
  const navigate = useNavigate();
  const [result, setResult] = React.useState<ScanResult | null>(null);
  const [uploadOpen, setUploadOpen] = React.useState(false);
  const closeUpload = React.useCallback(() => setUploadOpen(false), []);
  const rows = q.data ?? [];
  const fixesQ = useApprovals({ kind: "fix" });
  const fixes = React.useMemo(() => summarizeFixes(fixesQ.data), [fixesQ.data]);

  return (
    <>
      <PageHeader
        eyebrow="Documents"
        title="The decks you would send today"
        lede="Every proposal, agreement, brochure and voice note in the BlueCart pack. Open findings are sentences a merchant could still read. Scan re-checks what is new or changed and skips the rest."
        actions={
          <div className="flex gap-2">
            <button type="button" className="btn" onClick={() => setUploadOpen(true)}><Plus size={14} /> Add a document</button>
            <button type="button" className="btn btn-primary" disabled={scan.isPending} onClick={() => scan.mutate(undefined, { onSuccess: setResult })}>
              <ScanSearch size={14} /> {scan.isPending ? "Scanning…" : "Scan documents"}
            </button>
          </div>
        }
      />
      <HereStrip here="Fix status is the only thing that makes a deck safe to send: drafted, waiting for a name, or approved." next="Next: open BlueCart’s payment-gateway proposal — look for “7 working days”." />
      {scan.isError ? <div className="sheet mb-4"><ErrorState error={scan.error} /></div> : null}
      {result ? <ScanPanel r={result} onClose={() => setResult(null)} /> : null}

      <div className="sheet overflow-hidden">
        {q.isLoading ? <LoadingBlock rows={8} label="Loading documents" /> : q.isError ? <ErrorState error={q.error} onRetry={() => void q.refetch()} /> : rows.length === 0 ? (
          <EmptyState title="No decks in this pack yet" hint="Press Scan documents to pull in the BlueCart / Sunrise files, or add a proposal: paste text, upload a PDF, or drop a voice note. Stale sentences show up as soon as a file is reviewed." />
        ) : (
          <div className="overflow-x-auto">
            <table className="tbl min-w-[880px]">
              <caption className="sr-only">Documents. Select a row to open the review.</caption>
              <thead><tr><th scope="col">Document</th><th scope="col">Type</th><th scope="col"><HintLabel label="Owner" hint={HINT.owner} /></th><th scope="col">Updated</th><th scope="col"><HintLabel label="Review status" hint={HINT.reviewStatus} /></th><th scope="col"><HintLabel label="Fix status" hint={HINT.fixStatus} /></th><th scope="col" className="text-right"><HintLabel label="Open findings" hint={HINT.openFindings} /></th></tr></thead>
              <tbody>
                {rows.map((d) => (
                  <tr key={d.id} className="row" onClick={() => navigate(`/library/${d.id}`)}>
                    <td className="min-w-[250px] max-w-[340px]">
                      <Link to={`/library/${d.id}`} className="block font-medium underline-offset-2 hover:underline" onClick={(e) => e.stopPropagation()}>{d.title}</Link>
                      <span className="mt-1 flex flex-wrap items-center gap-x-2 text-[11px] font-normal text-[var(--muted-foreground)]"><FormatCell d={d} /><span>{d.product}</span>{d.demo_data ? <Hint text={HINT.synthetic}><span>{d.format === "voice" ? "Synthetic demo audio" : "Synthetic demo document"}</span></Hint> : null}</span>
                    </td>
                    <td className="whitespace-nowrap">{humanize(d.doc_type)}</td>
                    <td className="whitespace-nowrap"><Hint text={d.owner} label={d.owner}><span>{ownerName(d.owner)}</span></Hint></td>
                    <td className="whitespace-nowrap">v{d.version}<span className="block text-[11px] text-[var(--muted-foreground)]">{fmtDate(d.last_modified)}</span></td>
                    <td><DocStatusChip status={d.status} /></td>
                    <td><FixCell s={fixes.get(d.id)} failed={fixesQ.isError || fixesQ.isLoading} /></td>
                    <td className="num text-right">{d.open_findings}{d.open_findings === 0 ? <span className="block text-[11px] font-normal text-[var(--muted-foreground)]">No open findings</span> : null}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <AddDocumentDrawer open={uploadOpen} onClose={closeUpload} />
    </>
  );
}
