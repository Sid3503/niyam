import * as React from "react";
import { ApiError, api } from "@/lib/api";

export type ExtractedFile = { filename: string; chars: number; pages: number | null; text: string; truncated: boolean };

/** Choose a PDF, DOCX, TXT or MD file. The server extracts the text; the parent shows it for review before anything is submitted. */
export function FilePicker({ onText, label = "Choose a file" }: { onText: (r: ExtractedFile) => void; label?: string }) {
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);
  const [name, setName] = React.useState<string | null>(null);
  const [drag, setDrag] = React.useState(false);
  const input = React.useRef<HTMLInputElement>(null);

  const pick = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true); setErr(null); setName(file.name);
    try {
      onText(await api.extractText(file));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not read that file.");
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  };

  return (
    <div
      className={`flex flex-col items-start gap-2 rounded-xl border border-dashed p-4 ${drag ? "bg-[var(--surface-2,#efe9e4)]" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); void pick(e.dataTransfer.files?.[0]); }}
    >
      <input ref={input} type="file" hidden accept=".pdf,.docx,.txt,.md,.markdown" onChange={(e) => void pick(e.target.files?.[0])} aria-label={label} />
      <button type="button" className="btn btn-sm" disabled={busy} onClick={() => input.current?.click()}>{busy ? "Reading file…" : label}</button>
      <p className="text-[12px] text-[var(--muted-foreground)]">PDF, DOCX, TXT or MD, up to 15 MB. You can also drop a file here. The text is shown for you to check before anything is submitted.</p>
      {name && !busy && !err ? <p className="text-[12px]">Loaded: {name}</p> : null}
      {err ? <p role="alert" className="text-[12px] text-[var(--bad,#a33)]">{err}</p> : null}
    </div>
  );
}
