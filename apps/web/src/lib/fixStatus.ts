import type { Approval } from "./types";

export interface FixSummary {
  pending: number;
  approved: number;
  rejected: number;
  deferred: number;
  approvals: { by: string | null; at: string | null }[];
}

/** Groups fix approvals by document. Pure; never invents a document or a status. */
export function summarizeFixes(list: Approval[] | undefined | null): Map<string, FixSummary> {
  const m = new Map<string, FixSummary>();
  if (!Array.isArray(list)) return m;
  for (const a of list) {
    if (a.kind !== "fix" || !a.document) continue;
    const s = m.get(a.document.id) ?? { pending: 0, approved: 0, rejected: 0, deferred: 0, approvals: [] };
    s[a.status] += 1;
    if (a.status === "approved") s.approvals.push({ by: a.decided_by, at: a.decided_at });
    m.set(a.document.id, s);
  }
  return m;
}

/** "2 waiting for approval · 3 approved". Empty summary reads "No fixes drafted". */
export function fixStatusText(s: FixSummary | undefined): string {
  if (!s) return "No fixes drafted";
  const parts: string[] = [];
  if (s.pending) parts.push(`${s.pending} waiting for approval`);
  if (s.approved) parts.push(`${s.approved} approved`);
  if (s.rejected) parts.push(`${s.rejected} rejected`);
  if (s.deferred) parts.push(`${s.deferred} deferred`);
  return parts.length ? parts.join(" · ") : "No fixes drafted";
}
