import type { ApprovalStatus, DocStatus, FindingStatus, RuleStatus } from "./types";

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.length <= 10 ? `${iso}T00:00:00` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function humanize(s: string): string {
  return s.replace(/_/g, " ");
}

export const STATUS_LABEL: Record<RuleStatus, string> = {
  draft: "draft",
  in_review: "in review",
  active: "active",
  superseded: "superseded",
  retired: "retired",
  rejected: "rejected",
};

export type Tone = "ok" | "warn" | "bad" | "neutral";

/** Finding status to chip tone. Only `current` is ever green. */
export const FINDING_TONE: Record<FindingStatus, Tone> = {
  current: "ok",
  outdated: "bad",
  contradiction: "bad",
  missing: "warn",
  review: "warn",
};
export const FINDING_LABEL: Record<FindingStatus, string> = {
  current: "current",
  outdated: "outdated",
  contradiction: "contradiction",
  missing: "missing",
  review: "needs review",
};
/** Worst first; used to pick a clause colour and sort findings. */
export const FINDING_RANK: Record<FindingStatus, number> = { contradiction: 0, outdated: 1, review: 2, missing: 3, current: 4 };

export const DOC_TONE: Record<DocStatus, Tone> = { new: "warn", changed: "warn", unchanged: "neutral", reviewed: "ok" };
export const APPROVAL_TONE: Record<ApprovalStatus, Tone> = { pending: "warn", approved: "ok", rejected: "bad", deferred: "neutral" };

export function shortSha(s: string | undefined | null): string {
  return s ? s.slice(0, 8) : "—";
}

export function pct(n: number): string {
  return `${Math.round(n * 100)}%`;
}

export const FOOTER_TEXT = "Decision support, not legal advice. Demo documents and product facts are synthetic.";

/** 3725 -> "1h 02m 05s", 125 -> "2m 05s", 9 -> "9s". Negative / non-finite -> "0s". */
export function fmtElapsed(totalSeconds: number | null | undefined): string {
  const t = typeof totalSeconds === "number" && Number.isFinite(totalSeconds) && totalSeconds > 0 ? Math.floor(totalSeconds) : 0;
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = t % 60;
  const two = (n: number) => String(n).padStart(2, "0");
  if (h > 0) return `${h}h ${two(m)}m ${two(s)}s`;
  if (m > 0) return `${m}m ${two(s)}s`;
  return `${s}s`;
}


/** "SEBI_2022-09-02_returns-claimed-by-unregulated-algo-platforms.pdf" -> "SEBI 2022-09-02 returns claimed by unregulated algo platforms" */
export function titleFromFilename(name: string): string {
  const base = name.replace(/\.[^.]+$/, "").replace(/_/g, " ");
  return base.replace(/(?<!\d)-|-(?!\d)/g, " ").replace(/\s+/g, " ").trim();
}
