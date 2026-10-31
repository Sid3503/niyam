import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "@/App";
import { setActor } from "@/lib/settings";

const pending = {
  id: "ap1", kind: "fix", status: "pending", severity: "high", confidence: 0.7, title: "Fix settlement timeline wording",
  created_at: "2026-10-30T10:00:00Z", decided_at: null, decided_by: null, reason: null,
  document: { id: "d1", title: "Acme proposal" }, clause: { locator: "§3.2", text: "Settlement in T+3 days." }, finding_id: "f1",
  current_wording: "Settlement in T+3 days.", proposed_wording: "Settlement in T+1 days.", rule: null,
  source: { document: "RBI circular", quote: "settle within T+1", quote_verified: true },
};
const decided = { ...pending, status: "approved", decided_by: "asha.k", decided_at: "2026-10-31T09:00:00Z" };

describe("Approvals decision flow (mocked fetch)", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("approves an item, sends actor header and body, then shows who decided", async () => {
    setActor("asha.k");
    let state: unknown[] = [pending];
    const calls: { url: string; init?: RequestInit }[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url.startsWith("/api/v1/approvals/ap1/decision")) { state = [decided]; return new Response(JSON.stringify(decided), { status: 200 }); }
      if (url.startsWith("/api/v1/approvals")) return new Response(JSON.stringify(state), { status: 200 });
      if (url.startsWith("/api/v1/overview")) return new Response(JSON.stringify({ fixes_awaiting_approval: 1, rules_pending_approval: 0 }), { status: 200 });
      return new Response(JSON.stringify({ error: { code: "nf", message: "nope" } }), { status: 404 });
    }));
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={qc}><MemoryRouter initialEntries={["/approvals"]}><App /></MemoryRouter></QueryClientProvider>);

    await screen.findByText("Fix settlement timeline wording");
    expect(screen.getByTestId("redline")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Reason (optional)"), { target: { value: "matches circular" } });
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => expect(screen.getByText("asha.k")).toBeTruthy());
    const post = calls.find((c) => c.url.includes("/decision"))!;
    expect(post.init?.method).toBe("POST");
    expect(JSON.parse(post.init?.body as string)).toEqual({ decision: "approve", reason: "matches circular" });
    expect((post.init?.headers as Record<string, string>)["X-Actor"]).toBe("asha.k");
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
    expect(screen.getByText(/Decision support, not legal advice/)).toBeTruthy();
    setActor("");
  });

  it("shows an error state when the API fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ error: { code: "boom", message: "backend down" } }), { status: 500 })));
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={qc}><MemoryRouter initialEntries={["/approvals"]}><App /></MemoryRouter></QueryClientProvider>);
    expect(await screen.findByText("backend down")).toBeTruthy();
  });
});
