import * as React from "react";
import { Mic, Square } from "lucide-react";
import { fmtClock } from "./audio";

const MIMES = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];

export function extForMime(mime: string): string {
  if (mime.includes("webm")) return "webm";
  if (mime.includes("ogg")) return "ogg";
  if (mime.includes("mp4") || mime.includes("m4a")) return "m4a";
  if (mime.includes("wav")) return "wav";
  if (mime.includes("mpeg") || mime.includes("mp3")) return "mp3";
  return "webm";
}

type Phase = "idle" | "recording" | "recorded";

/** Record from the microphone with MediaRecorder. Hands the recorded Blob to `onRecorded`; the parent decides when to upload. */
export function VoiceRecorder({ onRecorded, disabled }: { onRecorded: (r: { blob: Blob; filename: string } | null) => void; disabled?: boolean }) {
  const [phase, setPhase] = React.useState<Phase>("idle");
  const [elapsed, setElapsed] = React.useState(0);
  const [error, setError] = React.useState<string | null>(null);
  const [preview, setPreview] = React.useState<string | null>(null);
  const rec = React.useRef<MediaRecorder | null>(null);
  const stream = React.useRef<MediaStream | null>(null);
  const chunks = React.useRef<Blob[]>([]);
  const timer = React.useRef<number | null>(null);
  const supported = typeof window !== "undefined" && typeof MediaRecorder !== "undefined" && !!navigator.mediaDevices?.getUserMedia;

  const cleanup = React.useCallback(() => {
    if (timer.current) window.clearInterval(timer.current);
    timer.current = null;
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
  }, []);
  React.useEffect(() => () => { cleanup(); if (rec.current && rec.current.state !== "inactive") rec.current.stop(); }, [cleanup]);
  React.useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const start = async () => {
    setError(null);
    onRecorded(null);
    setPreview(null);
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.current = s;
      const mime = MIMES.find((m) => MediaRecorder.isTypeSupported?.(m));
      const r = new MediaRecorder(s, mime ? { mimeType: mime } : undefined);
      chunks.current = [];
      r.ondataavailable = (e) => { if (e.data.size) chunks.current.push(e.data); };
      r.onstop = () => {
        const type = r.mimeType || mime || "audio/webm";
        const blob = new Blob(chunks.current, { type });
        cleanup();
        if (!blob.size) { setError("Nothing was recorded. Try again."); setPhase("idle"); return; }
        setPreview(URL.createObjectURL(blob));
        setPhase("recorded");
        onRecorded({ blob, filename: `voice-note.${extForMime(type)}` });
      };
      rec.current = r;
      r.start();
      setElapsed(0);
      setPhase("recording");
      const t0 = Date.now();
      timer.current = window.setInterval(() => setElapsed((Date.now() - t0) / 1000), 250);
    } catch (e) {
      cleanup();
      const name = (e as { name?: string } | null)?.name;
      setError(name === "NotAllowedError" || name === "SecurityError" ? "Microphone permission was denied. Allow it in the browser's site settings, or upload an audio file or use a sample instead." : name === "NotFoundError" ? "No microphone was found on this device." : "Could not start recording.");
      setPhase("idle");
    }
  };
  const stop = () => { if (rec.current && rec.current.state !== "inactive") rec.current.stop(); };

  if (!supported) return <p role="note" className="text-[12.5px] text-[var(--muted-foreground)]">This browser cannot record audio. Upload an audio file or use a sample instead.</p>;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        {phase === "recording" ? (
          <button type="button" className="btn btn-sm" onClick={stop}><Square size={13} /> Stop</button>
        ) : (
          <button type="button" className="btn btn-sm" disabled={disabled} onClick={() => void start()}><Mic size={13} /> {phase === "recorded" ? "Record again" : "Record"}</button>
        )}
        {phase === "recording" ? <span className="chip chip-bad chip-dot" role="status" aria-live="off">recording {fmtClock(elapsed)}</span> : null}
        {phase === "recorded" ? <span className="text-[12px] text-[var(--muted-foreground)]">Recorded {fmtClock(elapsed)}</span> : null}
      </div>
      {preview ? <audio controls src={preview} className="w-full" aria-label="Recording preview" /> : null}
      {error ? <p role="alert" className="text-[12px] text-[var(--bad-ink)]">{error}</p> : null}
    </div>
  );
}
