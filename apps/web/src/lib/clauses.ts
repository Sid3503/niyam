import { locateQuote } from "./highlight";
import { FINDING_RANK, FINDING_TONE, type Tone } from "./format";
import type { Clause, Finding } from "./types";

export interface Segment {
  text: string;
  finding?: Finding;
}

/** Position of a finding's quote inside its clause (relative offsets), or null when it cannot be located. */
export function locateInClause(clause: Clause, content: string, f: Finding): { start: number; end: number } | null {
  if (!f.quote) return null;
  const g = locateQuote(content, f.quote, f.span);
  if (g.ok) {
    const rel = g.start - clause.start;
    if (rel >= 0 && clause.text.slice(rel, rel + f.quote.length) === f.quote) return { start: rel, end: rel + f.quote.length };
  }
  const idx = clause.text.indexOf(f.quote);
  return idx >= 0 ? { start: idx, end: idx + f.quote.length } : null;
}

/** Split clause text into plain and highlighted runs. Overlapping spans: the first (worst) wins. */
export function clauseSegments(clause: Clause, content: string, findings: Finding[]): Segment[] {
  const placed = findings
    .filter((f) => f.clause_idx === clause.idx)
    .map((f) => ({ f, pos: locateInClause(clause, content, f) }))
    .filter((x): x is { f: Finding; pos: { start: number; end: number } } => x.pos !== null)
    .sort((a, b) => a.pos.start - b.pos.start || FINDING_RANK[a.f.status] - FINDING_RANK[b.f.status]);
  const out: Segment[] = [];
  let cur = 0;
  for (const { f, pos } of placed) {
    if (pos.start < cur) continue;
    if (pos.start > cur) out.push({ text: clause.text.slice(cur, pos.start) });
    out.push({ text: clause.text.slice(pos.start, pos.end), finding: f });
    cur = pos.end;
  }
  if (cur < clause.text.length) out.push({ text: clause.text.slice(cur) });
  return out;
}

/** Tone of a clause: its worst finding. Green only when the clause has a `current` finding and nothing worse. */
export function clauseTone(clauseIdx: number, findings: Finding[]): Tone | null {
  const own = findings.filter((f) => f.clause_idx === clauseIdx);
  if (!own.length) return null;
  const worst = own.reduce((a, b) => (FINDING_RANK[b.status] < FINDING_RANK[a.status] ? b : a));
  return FINDING_TONE[worst.status];
}
