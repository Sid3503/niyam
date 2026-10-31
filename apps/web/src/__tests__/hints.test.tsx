import { describe, expect, it, vi, afterEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "@/App";
import { FindingChip, StatusBadge, ApprovalChip } from "@/components/Badges";
import { Hint, HintsProvider } from "@/components/Hint";
import { HINT } from "@/lib/hints";
import type { Overview } from "@/lib/types";

const base: Overview = {
  documents_scanned: 5, open_findings: 20, fixes_awaiting_approval: 0, rules_pending_approval: 2, citation_coverage: 1,
  rules: { active: 0, draft: 2 }, next_action: { label: "Approve the rules", route: "/approvals", kind: "approve_rules" },
};

function renderAt(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></QueryClientProvider>);
}

async function openHint(el: HTMLElement) {
  fireEvent.pointerMove(el);
  fireEvent.pointerEnter(el);
  fireEvent.mouseEnter(el);
  fireEvent.focus(el);
  return waitFor(() => expect(screen.getByTestId("hint")).toBeTruthy());
}

describe("hint copy", () => {
  it("explains the clock, finding statuses, and the rule/fix chips", () => {
    expect(HINT.clock).toMatch(/Starts when a circular is added/);
    expect(HINT.clock).toMatch(/no open findings/);
    expect(HINT.finding.outdated).toMatch(/older rule/);
    expect(HINT.finding.current).toMatch(/clear to send/);
    expect(HINT.finding.review).toMatch(/Never a pass/);
    expect(HINT.approval.pending).toMatch(/Do not send/);
    expect(HINT.rule.draft).toMatch(/Not used in scans/);
    expect(HINT.confidence).toMatch(/named person still decides/);
    expect(HINT.step.fixes).toMatch(/named person must sign/);
  });
});

describe("Hint", () => {
  it("opens the explanation on focus", async () => {
    render(
      <HintsProvider>
        <Hint text={HINT.finding.outdated} label="outdated">
          <span>outdated</span>
        </Hint>
      </HintsProvider>,
    );
    await openHint(screen.getByText("outdated"));
    expect(screen.getByTestId("hint").textContent).toMatch(/older rule/);
  });

  it("puts the meaning on status chips", async () => {
    render(
      <HintsProvider>
        <FindingChip status="outdated" />
        <StatusBadge status="draft" />
        <ApprovalChip status="pending" />
      </HintsProvider>,
    );
    await openHint(screen.getByText("outdated"));
    expect(screen.getByTestId("hint").textContent).toBe(HINT.finding.outdated);
  });
});

describe("overview hints", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("puts a ? on the clock and the pack counts", async () => {
    const steps = ["circular", "rules", "scan", "fixes", "retest", "evidence"].map((key, i) => ({
      key, label: key, state: i < 2 ? "done" : i === 2 ? "current" : "todo", detail: `detail ${key}`, route: "/library",
    }));
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
      ...base, steps,
      pack: { circular_title: "UPI circular", started_at: null, approved_at: "2026-10-31T10:00:00Z", elapsed_seconds: 3725, documents_total: 5, documents_affected: 3, documents_clear: 2 },
    }), { status: 200 })));
    renderAt("/overview");
    await screen.findByText("1h 02m 05s");
    expect(screen.getByLabelText(/What “Time from circular to a pack you can send” means/)).toBeTruthy();
    expect(screen.getByLabelText(/What “Affected” means/)).toBeTruthy();
    expect(screen.getByLabelText(/What “Clear” means/)).toBeTruthy();
    await openHint(screen.getByLabelText(/What “Time from circular to a pack you can send” means/));
    expect(screen.getByTestId("hint").textContent).toBe(HINT.clock);
  });
});
