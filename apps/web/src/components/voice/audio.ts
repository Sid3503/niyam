import type { Finding, VoiceSentence } from "@/lib/types";

/** Where to seek for a finding: audio_time[0], clamped into [0, duration]. Null when the finding has no timing. */
export function seekTarget(f: Pick<Finding, "audio_time">, duration?: number | null): number | null {
  const t = f.audio_time?.[0];
  if (typeof t !== "number" || !Number.isFinite(t)) return null;
  const max = duration && duration > 0 ? duration : Infinity;
  return Math.max(0, Math.min(t, max));
}

/** Minimal slice of HTMLAudioElement so the helper is testable without a browser. */
export interface SeekableAudio {
  currentTime: number;
  play: () => Promise<void> | void;
}

/** Seek to the finding and play. Returns the time sought to, or null when there is nothing to seek to. */
export function seekAndPlay(audio: SeekableAudio | null | undefined, f: Pick<Finding, "audio_time">, duration?: number | null): number | null {
  const t = seekTarget(f, duration);
  if (!audio || t === null) return null;
  audio.currentTime = t;
  try {
    const p = audio.play();
    if (p && typeof (p as Promise<void>).catch === "function") (p as Promise<void>).catch(() => undefined);
  } catch {
    /* autoplay blocked: the audio is positioned, the user can press play */
  }
  return t;
}

/** Sentence being spoken at time t (last sentence whose start <= t and, if it has an end, t < end), or -1. */
export function activeSentence(sentences: VoiceSentence[], t: number): number {
  for (let i = 0; i < sentences.length; i++) {
    const s = sentences[i];
    if (t >= s.start && t < s.end) return i;
  }
  return -1;
}

export function fmtClock(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** Split `text` (which begins at `offset` in the transcript) into runs, marking those covered by a finding span. */
export function spanRuns(text: string, offset: number, spans: { span: [number, number]; id: string }[]): { text: string; id?: string }[] {
  const end = offset + text.length;
  const hits = spans
    .filter((x) => x.span[1] > offset && x.span[0] < end)
    .map((x) => ({ s: Math.max(x.span[0], offset) - offset, e: Math.min(x.span[1], end) - offset, id: x.id }))
    .sort((a, b) => a.s - b.s);
  const out: { text: string; id?: string }[] = [];
  let cur = 0;
  for (const h of hits) {
    if (h.s < cur) continue;
    if (h.s > cur) out.push({ text: text.slice(cur, h.s) });
    out.push({ text: text.slice(h.s, h.e), id: h.id });
    cur = h.e;
  }
  if (cur < text.length) out.push({ text: text.slice(cur) });
  return out;
}
