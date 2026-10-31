import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { ErrorState, LoadingBlock } from "@/components/States";
import { api } from "@/lib/api";
import { currentApiKey } from "@/lib/settings";
import type { VersionInfo } from "@/lib/types";
import { HashRow } from "./ApplyView";
import { useBlobUrl } from "./useBlobUrl";

function PageImage({ url, label }: { url: string; label: string }) {
  const m = useBlobUrl(url);
  if (m.error) return <p role="alert" className="p-3 text-[12px] text-[var(--bad-ink)]">Could not load {label}.</p>;
  if (!m.src) return <div className="skeleton h-64 w-full" role="status" aria-label={`Loading ${label}`} />;
  return <img src={m.src} alt={label} className="block w-full rounded border border-[var(--border)] bg-white" />;
}

/** Side-by-side page images for two versions of a PDF, changed pages flagged. */
export function CompareView({ documentId, versions }: { documentId: string; versions: VersionInfo[] }) {
  const sorted = [...versions].sort((a, b) => a.version - b.version);
  const [from, setFrom] = React.useState(sorted[0]?.id ?? "");
  const [to, setTo] = React.useState(sorted[sorted.length - 1]?.id ?? "");
  const [onlyChanged, setOnlyChanged] = React.useState(false);
  const same = from === to;
  const q = useQuery({
    queryKey: ["compare", documentId, from, to, currentApiKey()],
    queryFn: () => api.compare(documentId, from, to),
    enabled: !!from && !!to && !same,
    retry: false,
  });
  if (sorted.length < 2) return <p className="text-[12.5px] text-[var(--muted-foreground)]">Only one version exists. Commit an edit in the workbench to create a second version to compare.</p>;
  const opt = (v: VersionInfo) => <option key={v.id} value={v.id}>v{v.version} · {v.trigger}</option>;
  const pages = (q.data?.pages ?? []).filter((p) => !onlyChanged || p.changed);
  const nChanged = q.data?.pages.filter((p) => p.changed).length ?? 0;
  return (
    <div className="flex flex-col gap-3" data-testid="compare">
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-[12px]"><span className="label mb-1 block">From</span><select className="field" value={from} onChange={(e) => setFrom(e.target.value)}>{sorted.map(opt)}</select></label>
        <label className="text-[12px]"><span className="label mb-1 block">To</span><select className="field" value={to} onChange={(e) => setTo(e.target.value)}>{sorted.map(opt)}</select></label>
        <label className="flex items-center gap-1.5 pb-2 text-[12px]"><input type="checkbox" checked={onlyChanged} onChange={(e) => setOnlyChanged(e.target.checked)} /> Changed pages only</label>
      </div>
      {same ? <p role="note" className="text-[12.5px] text-[var(--muted-foreground)]">Pick two different versions.</p> : q.isLoading ? <LoadingBlock rows={4} label="Comparing versions" /> : q.isError ? <ErrorState error={q.error} onRetry={() => void q.refetch()} /> : q.data ? (
        <>
          <div className="flex flex-col gap-1.5">
            <HashRow label={`v${q.data.from.version}`} sha={q.data.from.sha256} />
            <HashRow label={`v${q.data.to.version}`} sha={q.data.to.sha256} />
          </div>
          <p className="text-[12.5px]" role="status">{nChanged} of {q.data.pages.length} page{q.data.pages.length === 1 ? "" : "s"} changed.</p>
          {pages.length === 0 ? <p className="text-[12.5px] text-[var(--muted-foreground)]">No changed pages.</p> : pages.map((p) => (
            <section key={p.page} aria-label={`Page ${p.page}`} className="rounded-lg border border-[var(--border)] p-3" data-changed={p.changed ? "true" : "false"}>
              <div className="mb-2 flex items-center gap-2"><span className="num text-[12.5px] font-medium">Page {p.page}</span>{p.changed ? <span className="chip chip-warn chip-plain">changed</span> : <span className="chip chip-plain">unchanged</span>}</div>
              <div className="grid grid-cols-2 gap-3">
                <div><div className="label mb-1">v{q.data.from.version}</div><PageImage url={p.from_url} label={`Page ${p.page}, version ${q.data.from.version}`} /></div>
                <div><div className="label mb-1">v{q.data.to.version}</div><PageImage url={p.to_url} label={`Page ${p.page}, version ${q.data.to.version}`} /></div>
              </div>
            </section>
          ))}
        </>
      ) : null}
    </div>
  );
}
