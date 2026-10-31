import { describe, expect, it } from "vitest";
import { APPROVAL_TONE, DOC_TONE, FINDING_TONE } from "@/lib/format";
import { wordDiff } from "@/lib/redline";
import { clauseSegments, clauseTone } from "@/lib/clauses";
import { locateQuote } from "@/lib/highlight";
import type { Clause, Finding } from "@/lib/types";

const f = (over: Partial<Finding>): Finding => ({
  id: "f1", version_id: "v1", clause_idx: 0, locator: "§1", quote: null, span: null, status: "review", severity: "high", confidence: 0.8,
  reason: "r", rule_id: "R1", rule_version: 1, rule_status: "active", fact_id: null,
  source: { document: "d" }, tier: "A", suggested_fix: null, approval: null, decision: null, needs_human: false, ...over,
});

describe("status mapping", () => {
  it("only current is green; missing is never green", () => {
    expect(FINDING_TONE.current).toBe("ok");
    expect(Object.entries(FINDING_TONE).filter(([, t]) => t === "ok").map(([s]) => s)).toEqual(["current"]);
    expect(FINDING_TONE.missing).toBe("warn");
    expect(FINDING_TONE.outdated).toBe("bad");
    expect(FINDING_TONE.contradiction).toBe("bad");
  });
  it("document and approval statuses", () => {
    expect(DOC_TONE.reviewed).toBe("ok");
    expect(DOC_TONE.new).toBe("warn");
    expect(DOC_TONE.unchanged).toBe("neutral");
    expect(APPROVAL_TONE.pending).toBe("warn");
    expect(APPROVAL_TONE.approved).toBe("ok");
    expect(APPROVAL_TONE.rejected).toBe("bad");
  });
});

describe("wordDiff", () => {
  it("marks replaced words and keeps the rest", () => {
    const ops = wordDiff("Refund in 7 days.", "Refund in 5 days.");
    expect(ops.filter((o) => o.type === "del").map((o) => o.text)).toEqual(["7"]);
    expect(ops.filter((o) => o.type === "ins").map((o) => o.text)).toEqual(["5"]);
    expect(ops.map((o) => o.text).filter((_, i) => ops[i].type !== "ins").join("")).toBe("Refund in 7 days.");
    expect(ops.filter((o) => o.type !== "del").map((o) => o.text).join("")).toBe("Refund in 5 days.");
  });
  it("handles empty sides", () => {
    expect(wordDiff("", "new text")).toEqual([{ type: "ins", text: "new text" }]);
    expect(wordDiff("old", "")).toEqual([{ type: "del", text: "old" }]);
    expect(wordDiff("same", "same")).toEqual([{ type: "eq", text: "same" }]);
  });
});

describe("clause highlighting", () => {
  const content = "Intro. Settlement in T+3 days. Fees apply.";
  const clause: Clause = { idx: 0, locator: "§1", text: content, start: 0, end: content.length };
  it("highlights the quote by span and falls back to search", () => {
    const segs = clauseSegments(clause, content, [f({ quote: "T+3 days", span: [20, 28] })]);
    expect(segs.map((s) => s.text)).toEqual(["Intro. Settlement in ", "T+3 days", ". Fees apply."]);
    expect(segs[1].finding?.id).toBe("f1");
    const segs2 = clauseSegments(clause, content, [f({ quote: "T+3 days", span: [0, 3] })]);
    expect(segs2[1].text).toBe("T+3 days");
    expect(locateQuote(content, "nope", null).ok).toBe(false);
  });
  it("clause is green only when its worst finding is current", () => {
    expect(clauseTone(0, [f({ status: "current" })])).toBe("ok");
    expect(clauseTone(0, [f({ status: "current" }), f({ id: "f2", status: "outdated" })])).toBe("bad");
    expect(clauseTone(1, [f({ status: "current" })])).toBeNull();
    expect(clauseTone(null as unknown as number, [f({ clause_idx: null, status: "missing" })])).toBe("warn");
  });
});

import { fixStatusText, summarizeFixes } from "@/lib/fixStatus";
import type { Approval } from "@/lib/types";

describe("fix status derivation", () => {
  const mk = (id: string, doc: string | null, status: Approval["status"], kind: Approval["kind"] = "fix", by: string | null = null): Approval => ({
    id, kind, status, severity: "high", confidence: 0.5, title: "t", created_at: "x", decided_at: by ? "2026-10-31T09:00:00Z" : null, decided_by: by, reason: null,
    document: doc ? { id: doc, title: doc } : null, clause: null, finding_id: null, current_wording: null, proposed_wording: null, rule: null,
    source: { document: "d", quote_verified: true },
  });
  it("counts per document and ignores rules and document-less items", () => {
    const m = summarizeFixes([mk("1", "a", "pending"), mk("2", "a", "pending"), mk("3", "a", "approved", "fix", "asha.k"), mk("4", "b", "rejected"), mk("5", "a", "pending", "rule"), mk("6", null, "pending")]);
    expect(fixStatusText(m.get("a"))).toBe("2 waiting for approval · 1 approved");
    expect(m.get("a")!.approvals[0].by).toBe("asha.k");
    expect(fixStatusText(m.get("b"))).toBe("1 rejected");
    expect(fixStatusText(m.get("zzz"))).toBe("No fixes drafted");
  });
  it("tolerates a failed fetch", () => {
    expect(summarizeFixes(undefined).size).toBe(0);
  });
});
