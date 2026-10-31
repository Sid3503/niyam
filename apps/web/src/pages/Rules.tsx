import * as React from "react";
import { titleFromFilename } from "@/lib/format";
import { FilePicker } from "@/components/FilePicker";
import { Link, useSearchParams } from "react-router-dom";
import { FilePlus2 } from "lucide-react";
import { Drawer } from "@/components/Drawer";
import { EnforceChip, ProvenanceBadge, Severity, StatusBadge } from "@/components/Badges";
import { FilterSelect, uniq } from "@/components/Filters";
import { Notice } from "@/components/Notice";
import { Field, HereStrip, PageHeader } from "@/components/Page";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/States";
import { RuleDrawer } from "@/components/RuleDrawer";
import { useCreateCircular, useFacts, useRules } from "@/lib/api";
import { fmtDate, fmtDateTime, humanize } from "@/lib/format";
import type { CircularBody, CircularResult, RuleSummary } from "@/lib/types";

function Period({ r }: { r: RuleSummary }) {
  return (
    <>
      <div className="whitespace-nowrap text-[12px]">{fmtDate(r.effective_from)}{r.effective_to ? ` to ${fmtDate(r.effective_to)}` : " onward"}</div>
      <div className="mt-1"><EnforceChip enforceability={r.enforceability} effective={r.effective_from} /></div>
    </>
  );
}

function ApproverCell({ r }: { r: RuleSummary }) {
  if (r.status === "active") return <span className="text-[12px]">{r.approved_by ?? "approver not recorded"}<span className="block text-[11px] text-[var(--muted-foreground)]">{fmtDateTime(r.approved_at)}</span></span>;
  if (r.status === "draft" || r.status === "in_review") {
    return r.approval_id ? <Link to="/approvals" className="chip chip-warn chip-plain underline-offset-2 hover:underline">pending approval</Link> : <span className="chip chip-warn chip-plain">pending approval</span>;
  }
  return <span className="text-[12px] text-[var(--muted-foreground)]">{r.approved_by ?? "—"}</span>;
}

function RuleCards() {
  const q = useRules();
  const [, setParams] = useSearchParams();
  const [search, setSearch] = React.useState("");
  const [f, setF] = React.useState({ status: "", severity: "", tier: "" });
  const setFilter = (k: keyof typeof f) => (v: string) => setF((o) => ({ ...o, [k]: v }));
  const data = q.data ?? [];
  const open = (id: string) => setParams((p) => { p.set("rule", id); return p; });
  const rows = data.filter((r) =>
    (!f.status || r.status === f.status) && (!f.severity || r.severity === f.severity) && (!f.tier || r.tier === f.tier) &&
    (!search.trim() || `${r.id} ${r.title} ${r.aliases.join(" ")}`.toLowerCase().includes(search.trim().toLowerCase())),
  );
  const draft = data.filter((r) => r.status === "draft" || r.status === "in_review").length;

  return (
    <>
      {draft > 0 ? <Notice tone="warn" className="mb-4">{draft} of {data.length} rules are draft and waiting for approval. Only active rules are used in scans.</Notice> : null}
      <div className="sheet mb-4 flex flex-wrap items-end gap-3 p-3.5">
        <div className="min-w-[12rem] flex-1">
          <label htmlFor="rules-search" className="label mb-1 block">Search</label>
          <input id="rules-search" className="field !py-1.5 text-[12.5px]" type="search" placeholder="Id or title" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <FilterSelect id="rf-status" label="Status" value={f.status} onChange={setFilter("status")} options={uniq(data.map((r) => r.status))} />
        <FilterSelect id="rf-sev" label="Severity" value={f.severity} onChange={setFilter("severity")} options={uniq(data.map((r) => r.severity))} />
        <FilterSelect id="rf-tier" label="Checked by" value={f.tier} onChange={setFilter("tier")} options={uniq(data.map((r) => r.tier))} />
      </div>
      <div className="sheet overflow-hidden">
        {q.isLoading ? <LoadingBlock rows={8} label="Loading rules" /> : q.isError ? <ErrorState error={q.error} onRetry={() => void q.refetch()} /> : rows.length === 0 ? (
          <EmptyState title="No rules match" hint={data.length ? "Clear a filter or the search box to see the rules again." : "No rules yet. Add a circular and Niyam will draft them for counsel to approve."} />
        ) : (
          <div className="overflow-x-auto">
            <table className="tbl min-w-[1000px]">
              <caption className="sr-only">Rule cards. Select a row to open its details.</caption>
              <thead><tr><th scope="col">Rule</th><th scope="col">Status</th><th scope="col">Severity</th><th scope="col" title="Tier A is checked by code. Tier B is checked by a language model.">Checked by</th><th scope="col">Effective period</th><th scope="col">Approver</th><th scope="col">In scans</th><th scope="col">Source</th></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="row" onClick={() => open(r.id)}>
                    <td className="max-w-[320px]">
                      <button type="button" className="block text-left" aria-label={`Open ${r.id}`} onClick={(e) => { e.stopPropagation(); open(r.id); }}>
                        <span className="block font-mono text-[11.5px] font-medium">{r.id} · v{r.version}</span>
                        <span className="mt-0.5 block text-[12.5px] leading-snug">{r.title}</span>
                      </button>
                    </td>
                    <td><StatusBadge status={r.status} /></td>
                    <td><Severity value={r.severity} /></td>
                    <td><span className="chip chip-plain" title={String(r.tier) === "A" ? "Tier A: checked by code" : String(r.tier) === "B" ? "Tier B: checked by a language model" : undefined}>{r.tier}</span></td>
                    <td><Period r={r} /></td>
                    <td><ApproverCell r={r} /></td>
                    <td><span className="chip chip-plain" title={r.scan_active ? "Niyam uses this rule when it scans documents" : "Not live yet: this rule is not used in scans"}>{r.scan_active ? "Used in scans" : "Not live yet"}</span></td>
                    <td><ProvenanceBadge provenance={r.source.provenance} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <p className="mt-2 text-[11.5px] text-[var(--muted-foreground)]">{rows.length} of {data.length} rules</p>
    </>
  );
}

function fmtValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return Object.entries(v as Record<string, unknown>).map(([k, x]) => `${humanize(k)}: ${String(x)}`).join(", ");
  return String(v);
}

function Facts() {
  const q = useFacts();
  const rows = q.data ?? [];
  return (
    <>
      <Notice className="mb-4">Your approved product terms, which documents are checked against. These facts are synthetic demo data and stand in for your product team's source of truth.</Notice>
      <div className="sheet overflow-hidden">
        {q.isLoading ? <LoadingBlock rows={6} label="Loading product facts" /> : q.isError ? <ErrorState error={q.error} onRetry={() => void q.refetch()} /> : rows.length === 0 ? <EmptyState title="No product facts yet" hint="Product facts are your approved terms. Without them Niyam can only check documents against circulars." /> : (
          <div className="overflow-x-auto">
            <table className="tbl min-w-[860px]">
              <thead><tr><th scope="col">Fact</th><th scope="col">Category</th><th scope="col">Statement</th><th scope="col">Value</th><th scope="col">Owner</th></tr></thead>
              <tbody>
                {rows.map((x) => (
                  <tr key={x.id}>
                    <td><span className="block font-mono text-[11.5px] font-medium">{x.id}</span><span className="text-[12.5px]">{x.title}</span></td>
                    <td>{humanize(x.category)}</td>
                    <td className="max-w-[360px]">{x.statement}<span className="mt-1 block text-[11px] text-[var(--muted-foreground)]">{x.source_label}</span></td>
                    <td className="max-w-[220px] text-[12px]">{fmtValue(x.value)}{x.unit ? ` ${x.unit}` : ""}</td>
                    <td>{x.owner}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}

function CircularResultView({ r }: { r: CircularResult }) {
  return (
    <section aria-label="Draft rules created" className="flex flex-col gap-4">
      <Notice tone="warn">{r.drafts.length} draft rule{r.drafts.length === 1 ? "" : "s"} ready for a named approver. None is active: each waits for a named approver in Approvals.</Notice>
      <p className="text-[12.5px] text-[var(--muted-foreground)]">Source: {r.source.title} · {r.source.institution} · {r.source.chars.toLocaleString()} characters · retrieved {fmtDateTime(r.source.retrieved_at)}</p>
      {r.drafts.map((d) => (
        <article key={d.rule_id} className="rounded-lg border border-[var(--border)] p-3.5">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="chip chip-warn chip-dot">draft, pending approval</span><Severity value={d.severity} /><span className="chip chip-plain" title="Tier A: checked by code. Tier B: checked by a language model.">tier {d.tier}</span>
            <span className={d.quote_verified ? "chip chip-ok chip-plain" : "chip chip-warn chip-plain"}>{d.quote_verified ? "quote verified in source" : "quote not verified"}</span>
          </div>
          <h3 className="mt-2 text-[14px] font-medium">{d.title}</h3>
          <p className="font-mono text-[11px] text-[var(--muted-foreground)]">{d.rule_id}</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <div><div className="label mb-1">Source quote</div><blockquote className="border-l-2 border-[var(--taupe)] bg-[var(--background)] px-3 py-2 text-[12.5px] leading-relaxed">“{d.source_quote}”</blockquote></div>
            <div><div className="label mb-1">Obligation drafted from it</div><p className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-3 text-[12.5px] leading-relaxed">{d.obligation}</p></div>
          </div>
        </article>
      ))}
      {r.notes.length ? <ul className="list-disc pl-5 text-[12.5px] text-[var(--muted-foreground)]">{r.notes.map((n, i) => <li key={i}>{n}</li>)}</ul> : null}
      <Link to="/approvals?kind=rule&status=pending" className="btn btn-primary self-start">Send for approval</Link>
    </section>
  );
}

function CircularDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const m = useCreateCircular();
  const autoTitle = React.useRef("");
  const [mode, setMode] = React.useState<"file" | "url" | "text">("file");
  const [f, setF] = React.useState({ url: "", text: "", title: "", institution: "", product_area: "", effective_date: "" });
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF((o) => ({ ...o, [k]: e.target.value }));
  const valid = f.institution.trim() && f.product_area.trim() && (mode === "url" ? f.url.trim() : f.text.trim());
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    const body: CircularBody = { institution: f.institution.trim(), product_area: f.product_area.trim() };
    if (mode === "url") body.url = f.url.trim(); else body.text = f.text;
    if (f.title.trim()) body.title = f.title.trim();
    if (f.effective_date) body.effective_date = f.effective_date;
    m.mutate(body);
  };
  return (
    <Drawer open={open} onClose={onClose} eyebrow="Add circular" label="Add a regulatory circular">
      <div className="flex flex-col gap-4">
        {m.data ? <CircularResultView r={m.data} /> : (
          <form onSubmit={submit} className="flex flex-col gap-4">
            <Notice>Rules drafted from a circular start as drafts. They are not used in scans until a named person approves them. The circular text is sent to a hosted language model to draft them.</Notice>
            <div role="tablist" aria-label="Circular input" className="flex gap-1.5">
              {(["file", "text", "url"] as const).map((t) => <button key={t} type="button" role="tab" aria-selected={mode === t} className={mode === t ? "btn btn-sm btn-primary" : "btn btn-sm"} onClick={() => setMode(t)}>{t === "file" ? "Upload file" : t === "url" ? "From URL" : "Paste text"}</button>)}
            </div>
            {mode === "file" ? <FilePicker label="Choose a circular (PDF, DOCX, TXT)" onText={(r) => { setF((o) => ({ ...o, text: r.text, title: !o.title || o.title === autoTitle.current ? (autoTitle.current = titleFromFilename(r.filename)) : o.title })); setMode("text"); }} /> : null}
            {mode === "url" ? <Field label="Circular URL" htmlFor="c-url"><input id="c-url" className="field" type="url" value={f.url} onChange={set("url")} placeholder="https://" /></Field> : mode === "text" ? <Field label="Circular text" htmlFor="c-text"><textarea id="c-text" className="field min-h-[200px] text-[12.5px]" value={f.text} onChange={set("text")} /></Field> : null}
            <Field label="Title (optional)" htmlFor="c-title"><input id="c-title" className="field" value={f.title} onChange={set("title")} /></Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Institution" htmlFor="c-inst"><input id="c-inst" className="field" value={f.institution} onChange={set("institution")} placeholder="e.g. RBI" required /></Field>
              <Field label="Product area" htmlFor="c-area"><input id="c-area" className="field" value={f.product_area} onChange={set("product_area")} placeholder="e.g. UPI merchant payments" required /></Field>
            </div>
            <Field label="Effective date (optional)" htmlFor="c-eff"><input id="c-eff" className="field" type="date" value={f.effective_date} onChange={set("effective_date")} /></Field>
            {m.isError ? <ErrorState error={m.error} /> : null}
            <div className="flex gap-2">
              <button type="submit" className="btn btn-primary" disabled={!valid || m.isPending}>{m.isPending ? "Reading circular…" : "Draft rules"}</button>
              <button type="button" className="btn" onClick={onClose}>Cancel</button>
            </div>
          </form>
        )}
      </div>
    </Drawer>
  );
}

export default function Rules() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "facts" ? "facts" : "rules";
  const [addOpen, setAddOpen] = React.useState(false);
  const closeAdd = React.useCallback(() => setAddOpen(false), []);
  const setTab = (t: "rules" | "facts") => setParams((p) => { if (t === "facts") p.set("tab", "facts"); else p.delete("tab"); return p; }, { replace: true });

  return (
    <>
      <PageHeader
        eyebrow="Rules"
        title="What your documents are checked against"
        lede="Each rule card is one duty from a circular, with the quote it came from. Only active rules are used in scans; drafts wait for a named approver."
        actions={<button type="button" className="btn btn-primary" onClick={() => setAddOpen(true)}><FilePlus2 size={14} /> Add a circular</button>}
      />
      <HereStrip here="Add a circular and Niyam drafts the rules. Nothing counts until a named person approves." next="Next: add a circular, then send its rules for approval." />
      <div role="tablist" aria-label="Rules sections" className="mb-4 flex gap-1.5">
        <button type="button" role="tab" aria-selected={tab === "rules"} className={tab === "rules" ? "btn btn-sm btn-primary" : "btn btn-sm"} onClick={() => setTab("rules")}>Rules</button>
        <button type="button" role="tab" aria-selected={tab === "facts"} className={tab === "facts" ? "btn btn-sm btn-primary" : "btn btn-sm"} onClick={() => setTab("facts")}>Product facts</button>
      </div>
      {tab === "rules" ? <RuleCards /> : <Facts />}
      <CircularDrawer open={addOpen} onClose={closeAdd} />
      <RuleDrawer />
    </>
  );
}
