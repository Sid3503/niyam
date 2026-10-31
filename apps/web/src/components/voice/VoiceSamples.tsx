import { Play } from "lucide-react";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/States";
import { useBlobUrl } from "@/components/workbench/useBlobUrl";
import { useCheckVoiceSample, useVoiceSamples } from "@/lib/api";
import { humanize } from "@/lib/format";
import type { DocumentDetail, VoiceSample } from "@/lib/types";
import { fmtClock } from "./audio";

function Sample({ s, busy, onCheck }: { s: VoiceSample; busy: boolean; onCheck: () => void }) {
  const media = useBlobUrl(s.audio_url);
  return (
    <li className="rounded-lg border border-[var(--border)] p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[13px] font-medium">{s.title}</span>
        <span className="chip chip-warn chip-plain">Synthetic demo audio</span>
        <span className="chip chip-plain">{humanize(s.language)} · {fmtClock(s.duration_seconds)}</span>
      </div>
      {s.expected ? <p className="mt-1 text-[12px] text-[var(--muted-foreground)]">What it should surface: {s.expected}</p> : null}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {media.src ? <audio controls preload="none" src={media.src} className="h-8 max-w-[280px]" aria-label={`Preview ${s.title}`} /> : <span className="text-[11.5px] text-[var(--muted-foreground)]">{media.loading ? "Loading audio…" : "Preview unavailable"}</span>}
        <button type="button" className="btn btn-sm btn-primary ml-auto" disabled={busy} onClick={onCheck}><Play size={12} /> {busy ? "Checking…" : "Check this clip"}</button>
      </div>
    </li>
  );
}

/** Synthetic demo clips shipped with the repo (GET /voice/samples), each runnable through the same pipeline. */
export function VoiceSamples({ onDone }: { onDone: (d: DocumentDetail) => void }) {
  const q = useVoiceSamples();
  const check = useCheckVoiceSample();
  return (
    <div className="flex flex-col gap-2">
      <div className="label">Try a synthetic sample</div>
      {q.isLoading ? <LoadingBlock rows={3} label="Loading samples" /> : q.isError ? <ErrorState error={q.error} onRetry={() => void q.refetch()} /> : !q.data?.length ? <EmptyState title="No samples available" hint="The server did not list any demo clips." /> : (
        <ul className="flex flex-col gap-2">
          {q.data.map((s) => <Sample key={s.name} s={s} busy={check.isPending && check.variables === s.name} onCheck={() => check.mutate(s.name, { onSuccess: onDone })} />)}
        </ul>
      )}
      {check.isError ? <p role="alert" className="text-[12px] text-[var(--bad-ink)]">{check.error.message}</p> : null}
    </div>
  );
}
