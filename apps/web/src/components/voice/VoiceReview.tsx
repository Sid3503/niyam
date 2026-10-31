import * as React from "react";
import { Play } from "lucide-react";
import { Notice } from "@/components/Notice";
import { EmptyState, ErrorState } from "@/components/States";
import { FilterSelect } from "@/components/Filters";
import { FindingCard } from "@/components/workbench/FindingCard";
import { Hint } from "@/components/Hint";
import { HINT } from "@/lib/hints";
import { useBlobUrl } from "@/components/workbench/useBlobUrl";
import { FINDING_LABEL, FINDING_RANK, FINDING_TONE, humanize } from "@/lib/format";
import type { DocumentDetail, Finding, FindingStatus } from "@/lib/types";
import { activeSentence, fmtClock, seekAndPlay, seekTarget, spanRuns } from "./audio";

const STATUSES: FindingStatus[] = ["contradiction", "outdated", "review", "missing", "current"];

export function VoiceReview({ d, onRetest, readOnly }: { d: DocumentDetail; onRetest: () => void; readOnly: boolean }) {
  const v = d.voice!;
  const audioRef = React.useRef<HTMLAudioElement>(null);
  const media = useBlobUrl(v.audio_url);
  const [sel, setSel] = React.useState<string | null>(null);
  const [t, setT] = React.useState(0);
  const [filter, setFilter] = React.useState("");
  const [seekNote, setSeekNote] = React.useState<string | null>(null);

  const spans = d.findings.filter((f): f is Finding & { span: [number, number] } => !!f.span).map((f) => ({ span: f.span, id: f.id }));
  const active = activeSentence(v.sentences, t);
  const visible = d.findings.filter((f) => !filter || f.status === filter).sort((a, b) => FINDING_RANK[a.status] - FINDING_RANK[b.status]);

  const play = (f: Finding) => {
    setSel(f.id);
    const at = seekAndPlay(audioRef.current, f, v.duration_seconds);
    setSeekNote(at === null ? "This finding has no timing to seek to." : null);
  };
  const seekTo = (sec: number) => {
    if (audioRef.current) { audioRef.current.currentTime = sec; void audioRef.current.play()?.catch?.(() => undefined); }
  };
  const markTone = (id: string) => {
    const f = d.findings.find((x) => x.id === id);
    const tone = f ? FINDING_TONE[f.status] : "neutral";
    return tone === "ok" ? "hl-ok" : tone === "bad" ? "hl-bad" : "hl-warn";
  };

  return (
    <div className="flex flex-col gap-4">
      <Notice>Promises made out loud on calls are checked against the same rules as documents. The original recording is never changed. Each re-test is saved as a new version.</Notice>
      {readOnly ? <Notice tone="warn">You are viewing an earlier version.</Notice> : null}
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <section aria-label="Voice note" className="flex min-w-0 flex-col gap-4">
          <div className="sheet p-4">
            <div className="mb-2 flex flex-wrap items-center gap-1.5">
              <span className="chip chip-warn chip-plain" data-testid="synthetic-audio">Synthetic demo audio</span>
              <span className="chip chip-plain">{humanize(v.language)}</span>
              <span className="chip chip-plain">{fmtClock(v.duration_seconds)} long</span>
              <Hint text={HINT.stt}><span className="chip chip-plain">STT: {v.stt.provider} · {v.stt.model}</span></Hint>
            </div>
            {media.loading ? <p role="status" className="text-[12.5px] text-[var(--muted-foreground)]">Loading audio…</p> : media.error ? <ErrorState error={media.error} /> : (
              <audio ref={audioRef} controls preload="metadata" src={media.src ?? undefined} className="w-full" onTimeUpdate={(e) => setT(e.currentTarget.currentTime)} aria-label="Voice note audio" />
            )}
            <p className="mt-2 text-[11.5px] text-[var(--muted-foreground)]" data-testid="timing-note">{v.timing_note}</p>
            {seekNote ? <p role="status" className="mt-1 text-[11.5px] text-[var(--warn-ink)]">{seekNote}</p> : null}
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="sheet p-4" aria-label="Original transcript">
              <h2 className="label mb-2">Original transcript (as spoken)</h2>
              <p className="whitespace-pre-wrap text-[13px] leading-relaxed" lang={v.language}>{v.transcript_original || "No transcript was returned."}</p>
              <p className="mt-2 text-[11px] text-[var(--muted-foreground)]">Shown for reading only. Findings are checked against the English text.</p>
            </div>
            <div className="sheet p-4" aria-label="Normalised English transcript">
              <h2 className="label mb-2">English text (this is what is checked)</h2>
              {v.sentences.length ? (
                <ol className="flex flex-col gap-1.5">
                  {v.sentences.map((s, i) => (
                    <li key={s.idx} className={`rounded-md border px-2 py-1.5 text-[13px] leading-relaxed ${i === active ? "border-[var(--taupe)] bg-[var(--hover)]" : "border-transparent"}`} data-active={i === active ? "true" : undefined}>
                      <button type="button" className="mr-2 font-mono text-[10.5px] text-[var(--muted-foreground)] underline-offset-2 hover:underline" onClick={() => seekTo(s.start)} aria-label={`Play from ${fmtClock(s.start)}`}>
                        {fmtClock(s.start)}–{fmtClock(s.end)}
                      </button>
                      {spanRuns(s.text, s.start_char, spans).map((r, j) => r.id ? (
                        <mark key={j} className={markTone(r.id)} data-finding={r.id} onClick={() => { const f = d.findings.find((x) => x.id === r.id); if (f) play(f); }} style={{ cursor: "pointer" }}>{r.text}</mark>
                      ) : <span key={j}>{r.text}</span>)}
                    </li>
                  ))}
                </ol>
              ) : <p className="whitespace-pre-wrap text-[13px] leading-relaxed">{v.transcript_en}</p>}
            </div>
          </div>
        </section>

        <section aria-label="Findings" className="flex min-w-0 flex-col gap-3 lg:max-h-[86vh] lg:overflow-y-auto lg:pr-1">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h2 className="label">Findings ({visible.length})</h2>
            <FilterSelect id="fs" label="Status" value={filter} onChange={setFilter} options={STATUSES.map((s) => ({ value: s, label: FINDING_LABEL[s] }))} />
          </div>
          {visible.length ? visible.map((f) => {
            const at = seekTarget(f, v.duration_seconds);
            return (
              <FindingCard
                key={f.id}
                f={f}
                clause={d.clauses.find((c) => c.idx === f.clause_idx)}
                onRetest={onRetest}
                docId={d.document.id}
                selected={sel === f.id}
                onSelect={() => play(f)}
                readOnly={readOnly}
                extra={at !== null ? <button type="button" className="btn btn-sm" onClick={() => play(f)}><Play size={12} /> Play at {fmtClock(at)}</button> : <p className="text-[11.5px] text-[var(--muted-foreground)]">No timing for this finding.</p>}
              />
            );
          }) : <div className="sheet"><EmptyState title="No findings here" hint={d.findings.length ? "Clear the status filter." : "Nothing was flagged in this recording."} /></div>}
        </section>
      </div>
    </div>
  );
}
