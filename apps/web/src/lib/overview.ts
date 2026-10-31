import type { Overview, PackClock, PackStep } from "./types";

/** Six steps from the v0.3 contract, or a fallback derived from the pre-v0.3 fields. Exactly one is current. */
export function packSteps(o: Overview): PackStep[] {
  if (o.steps && o.steps.length === 6) return o.steps;
  const hasRules = o.rules.active + o.rules.draft > 0;
  const rulesDone = hasRules && o.rules_pending_approval === 0;
  const scanned = o.documents_scanned > 0;
  const fixesDone = scanned && o.fixes_awaiting_approval === 0;
  const raw: [PackStep["key"], string, boolean, string, string][] = [
    ["circular", "Circular", hasRules, hasRules ? "Rules were drafted from a circular." : "Add the RBI or NPCI circular.", "/rules"],
    ["rules", "Rule approved", rulesDone, o.rules_pending_approval ? `${o.rules_pending_approval} rule${o.rules_pending_approval === 1 ? "" : "s"} waiting for counsel.` : "Counsel has approved the rules.", "/approvals?kind=rule&status=pending"],
    ["scan", "Scan", scanned, scanned ? `${o.documents_scanned} documents scanned.` : "Scan the document library.", "/library"],
    ["fixes", "Counsel approves", fixesDone, o.fixes_awaiting_approval ? `${o.fixes_awaiting_approval} fix${o.fixes_awaiting_approval === 1 ? "" : "es"} waiting for counsel.` : "No fix is waiting.", "/approvals?kind=fix&status=pending"],
    ["retest", "Re-test", fixesDone && o.open_findings === 0, o.open_findings ? `${o.open_findings} findings still open.` : "No open findings.", "/impact"],
    ["evidence", "Evidence", false, "Export the audit file.", "/evidence"],
  ];
  let currentSet = false;
  return raw.map(([key, label, done, detail, route]) => {
    const state: PackStep["state"] = done ? "done" : !currentSet ? (currentSet = true, "current") : "todo";
    return { key, label, state, detail, route };
  });
}

/** Clock fields, or a fallback with no elapsed time (never invented). */
export function packClock(o: Overview): PackClock {
  if (o.pack) return o.pack;
  const total = o.documents_total ?? o.documents_scanned;
  return { circular_title: null, started_at: null, approved_at: null, elapsed_seconds: null, documents_total: total, documents_affected: 0, documents_clear: 0 };
}

/** Seconds to show now: frozen once approved, else the server value plus time since it was fetched. */
export function liveElapsed(p: PackClock, fetchedAt: number, now: number): number | null {
  if (p.elapsed_seconds === null) return null;
  if (p.approved_at) return p.elapsed_seconds;
  return p.elapsed_seconds + Math.max(0, (now - fetchedAt) / 1000);
}
