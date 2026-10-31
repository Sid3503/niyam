import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "@/App";
import { HERO_LINE } from "@/pages/Landing";
import { fmtElapsed } from "@/lib/format";
import { liveElapsed, packSteps } from "@/lib/overview";
import type { Overview } from "@/lib/types";

const base: Overview = {
  documents_scanned: 5, open_findings: 20, fixes_awaiting_approval: 0, rules_pending_approval: 2, citation_coverage: 1,
  rules: { active: 0, draft: 2 }, next_action: { label: "Approve the rules", route: "/approvals", kind: "approve_rules" },
};
function renderAt(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></QueryClientProvider>);
}

describe("landing", () => {
  it("shows the line, both CTAs, the FAQ and the disclaimer without the app shell", () => {
    renderAt("/");
    expect(HERO_LINE).toBe("Proposals and brochures stop shipping claims that are out of date, and you can see when a fix is approved.");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toMatch(/Proposals and brochures stop shipping claims that are out of date/);
    expect(screen.getAllByText(/and you can see when a fix is approved/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Fix approved").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /Open the demo workspace/ })[0].getAttribute("href")).toBe("/overview");
    expect(screen.getAllByRole("link", { name: "See how it works" })[0].getAttribute("href")).toBe("#how");
    for (const q of ["Will it slow my deals down?", "Who decides what is out of date?", "Does the AI approve anything?", "Does it change my original file?", "What does it check against?", "What if it is unsure?", "Where does our data go?"]) {
      expect(screen.getByText(q)).toBeTruthy();
    }
    expect(screen.getAllByText("Decision support, not legal advice. Demo documents and product facts are synthetic.").length).toBe(1);
    expect(screen.getAllByText(/Auto-reversal within T \+ 5 days/).length).toBeGreaterThan(0);
    expect(screen.queryByLabelText("Niyam sections")).toBeNull();
  });
  it("makes none of the banned claims", () => {
    renderAt("/");
    const t = (document.body.textContent ?? "").toLowerCase();
    for (const bad of ["71%", "96%", "11 minutes", "60 conversations", "ai-powered", "guarantee compliance", "replaces counsel", "trusted by", "soc 2", "soc2", "iso 27001"]) {
      expect(t).not.toContain(bad);
    }
  });
});

describe("overview", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders six steps with exactly one current, from the backend steps", async () => {
    const steps = ["circular", "rules", "scan", "fixes", "retest", "evidence"].map((key, i) => ({
      key, label: key, state: i < 2 ? "done" : i === 2 ? "current" : "todo", detail: `detail ${key}`, route: "/library",
    }));
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ ...base, steps, pack: { circular_title: "UPI circular", started_at: null, approved_at: "2026-10-31T10:00:00Z", elapsed_seconds: 3725, documents_total: 5, documents_affected: 3, documents_clear: 2 } }), { status: 200 })));
    renderAt("/overview");
    const list = await screen.findByRole("list", { name: "Circular to approved pack" });
    expect(list.querySelectorAll("li").length).toBe(6);
    expect(list.querySelectorAll('[aria-current="step"]').length).toBe(1);
    expect(screen.getByText("1h 02m 05s")).toBeTruthy();
    expect(screen.getByText(/Approved in 1h 02m 05s/)).toBeTruthy();
  });

  it("falls back to derived steps when the backend has no steps", () => {
    const s = packSteps(base);
    expect(s).toHaveLength(6);
    expect(s.filter((x) => x.state === "current")).toHaveLength(1);
  });
});

describe("clock helpers", () => {
  it("formats h/m/s", () => {
    expect(fmtElapsed(9)).toBe("9s");
    expect(fmtElapsed(125)).toBe("2m 05s");
    expect(fmtElapsed(3725)).toBe("1h 02m 05s");
    expect(fmtElapsed(null)).toBe("0s");
    expect(fmtElapsed(-4)).toBe("0s");
  });
  it("ticks only while not approved", () => {
    const run = { circular_title: null, started_at: "x", approved_at: null, elapsed_seconds: 10, documents_total: 1, documents_affected: 0, documents_clear: 1 };
    expect(liveElapsed(run, 1000, 6000)).toBe(15);
    expect(liveElapsed({ ...run, approved_at: "y" }, 1000, 6000)).toBe(10);
    expect(liveElapsed({ ...run, elapsed_seconds: null }, 1000, 6000)).toBeNull();
  });
});
