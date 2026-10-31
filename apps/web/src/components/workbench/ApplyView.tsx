import * as React from "react";
import { Copy, Check, TriangleAlert } from "lucide-react";
import { FINDING_LABEL, humanize } from "@/lib/format";
import type { ApplyMethod, ApplyResult, Finding } from "@/lib/types";

export const METHOD_LABEL: Record<ApplyMethod, string> = {
  redact_rewrite: "redact and rewrite",
  rasterize_page: "rasterize page",
  append_text: "append text",
};

/** Red list of quotes that are still extractable after an apply. Covering words is not a fix. */
export function StaleTextList({ items, findings }: { items: { finding_id: string; quote: string }[]; findings?: Finding[] }) {
  if (!items.length) return null;
  return (
    <div role="alert" className="rounded-lg border border-[var(--bad-line)] bg-[var(--bad-bg)] p-3 text-[12.5px] text-[var(--bad-ink)]" data-testid="stale-text">
      <p className="flex items-start gap-2 font-medium">
        <TriangleAlert size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
        <span>Old wording is still in the file ({items.length}). Hiding or covering words is not a fix: the text must be gone from the extracted text, so this cannot be committed.</span>
      </p>
      <ul className="mt-2 flex flex-col gap-1.5">
        {items.map((s) => {
          const f = findings?.find((x) => x.id === s.finding_id);
          return (
            <li key={`${s.finding_id}:${s.quote}`} className="rounded border border-[var(--bad-line)] bg-[var(--card)] px-2 py-1.5">
              <span className="font-mono text-[10.5px]">{f ? `${f.locator || "finding"} · ${FINDING_LABEL[f.status]}` : s.finding_id}</span>
              <div className="text-[12.5px]">still extractable: <q>{s.quote}</q></div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Plain rendering of a failed commit (409 stale_text_remains or any other error). */
export function ApplyError({ error, stale, findings }: { error: unknown; stale?: { finding_id: string; quote: string }[]; findings?: Finding[] }) {
  const e = error as { status?: number; code?: string; message?: string } | null;
  const isStale = e?.code === "stale_text_remains" || e?.status === 409;
  return (
    <div role="alert" className="flex flex-col gap-2" data-testid="apply-error">
      <p className="rounded-lg border border-[var(--bad-line)] bg-[var(--bad-bg)] px-3 py-2 text-[12.5px] text-[var(--bad-ink)]">
        {isStale ? "Commit refused (409, stale text remains). " : "Could not apply. "}
        {e?.message ?? "Something went wrong."}
        {isStale ? " Nothing was saved; the original and the current version are unchanged." : ""}
      </p>
      {stale?.length ? <StaleTextList items={stale} findings={findings} /> : null}
    </div>
  );
}

export function CopyButton({ text, label }: { text: string; label: string }) {
  const [done, setDone] = React.useState(false);
  return (
    <button
      type="button"
      className="btn btn-sm !px-1.5 !py-0.5"
      aria-label={`Copy ${label}`}
      onClick={() => {
        void navigator.clipboard?.writeText(text).then(() => { setDone(true); window.setTimeout(() => setDone(false), 1500); }).catch(() => undefined);
      }}
    >
      {done ? <Check size={12} /> : <Copy size={12} />}
    </button>
  );
}

/** Full SHA-256 in monospace with a copy button. */
export function HashRow({ label, sha }: { label: string; sha: string | null | undefined }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="label min-w-[64px] shrink-0">{label}</span>
      {sha ? (
        <>
          <code className="min-w-0 break-all font-mono text-[11px]" data-testid={`hash-${label}`}>{sha}</code>
          <CopyButton text={sha} label={`${label} SHA-256`} />
        </>
      ) : <span className="text-[12px] text-[var(--muted-foreground)]">—</span>}
    </div>
  );
}

/** Before/after comparison with what resolves or remains. `mode` only changes the wording (preview vs committed). */
export function ComparisonView({ r, findings, mode }: { r: ApplyResult; findings: Finding[]; mode: "preview" | "committed" }) {
  const c = r.comparison;
  const name = (id: string) => {
    const f = findings.find((x) => x.id === id);
    return f ? `${f.locator || "finding"} · ${FINDING_LABEL[f.status]}${f.quote ? ` · “${f.quote.length > 60 ? f.quote.slice(0, 57) + "…" : f.quote}”` : ""}` : id;
  };
  const group = (title: string, ids: string[], tone: string) => (
    <div>
      <div className="label mb-1">{title} ({ids.length})</div>
      {ids.length ? <ul className="flex flex-col gap-1">{ids.map((id) => <li key={id} className={`rounded border px-2 py-1 text-[12px] ${tone}`}>{name(id)}</li>)}</ul> : <p className="text-[12px] text-[var(--muted-foreground)]">None</p>}
    </div>
  );
  return (
    <section aria-label={mode === "preview" ? "Preview comparison" : "Committed comparison"} className="flex flex-col gap-3" data-testid="comparison">
      <div className="grid grid-cols-2 gap-3 text-[12.5px]">
        <div className="rounded-lg border border-[var(--border)] p-3"><div className="label mb-1">Before, open</div><div className="num text-[22px] font-medium leading-none">{c.before.open}</div><div className="mt-1.5 flex flex-wrap gap-1">{Object.entries(c.before.by_status).filter(([, n]) => n).map(([s, n]) => <span key={s} className="chip chip-plain">{n} {s}</span>)}</div></div>
        <div className="rounded-lg border border-[var(--border)] p-3"><div className="label mb-1">{mode === "preview" ? "After, would be open" : "After, open"}</div><div className="num text-[22px] font-medium leading-none">{c.after.open}</div><div className="mt-1.5 flex flex-wrap gap-1">{Object.entries(c.after.by_status).filter(([, n]) => n).map(([s, n]) => <span key={s} className="chip chip-plain">{n} {s}</span>)}</div></div>
      </div>
      {group(mode === "preview" ? "Would resolve" : "Resolved", c.resolved, "border-[var(--ok-line)] bg-[var(--ok-bg)] text-[var(--ok-ink)]")}
      {group(mode === "preview" ? "Would remain" : "Remaining", c.remaining, "border-[var(--warn-line)] bg-[var(--warn-bg)] text-[var(--warn-ink)]")}
      {c.new.length ? group(mode === "preview" ? "Would be new" : "New", c.new, "border-[var(--bad-line)] bg-[var(--bad-bg)] text-[var(--bad-ink)]") : null}
    </section>
  );
}

/** Strategy per edit, with the rasterize warning. */
export function StrategyList({ r, findings }: { r: ApplyResult; findings: Finding[] }) {
  const raster = r.strategy.filter((s) => s.method === "rasterize_page");
  return (
    <section aria-label="How each edit was applied" className="flex flex-col gap-2">
      <div className="label">Strategy per edit</div>
      <ul className="flex flex-col gap-1">
        {r.strategy.map((s) => {
          const f = findings.find((x) => x.id === s.finding_id);
          return <li key={s.finding_id} className="flex flex-wrap items-center gap-2 text-[12.5px]"><span className="chip chip-plain">{METHOD_LABEL[s.method] ?? humanize(s.method)}</span><span className="min-w-0 flex-1">{f ? `${f.locator || "finding"}${f.page ? ` · page ${f.page}` : ""}` : s.finding_id}</span></li>;
        })}
      </ul>
      {raster.length ? (
        <p role="note" className="flex gap-2 rounded-lg border border-[var(--warn-line)] bg-[var(--warn-bg)] px-3 py-2 text-[12.5px] text-[var(--warn-ink)]">
          <TriangleAlert size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
          <span>Selectable text on {raster.length === 1 ? "this page" : "these pages"} is lost: the page was rasterized so the old wording could not be copied out of the file.</span>
        </p>
      ) : null}
    </section>
  );
}

/** Pull a stale_text_remains list out of an ApiError body, wherever the server put it. */
export function staleFromError(error: unknown): { finding_id: string; quote: string }[] {
  const body = (error as { body?: unknown } | null)?.body as Record<string, unknown> | undefined;
  const cand = (body?.stale_text_remains ?? (body?.error as Record<string, unknown> | undefined)?.stale_text_remains) as unknown;
  if (!Array.isArray(cand)) return [];
  return cand.filter((x): x is { finding_id: string; quote: string } => !!x && typeof (x as { quote?: unknown }).quote === "string").map((x) => ({ finding_id: String(x.finding_id ?? ""), quote: x.quote }));
}
