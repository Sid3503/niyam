import { FOOTER_TEXT } from "@/lib/format";
import { parseSnippet } from "@/lib/highlight";

export function PageHeader({ eyebrow, title, lede, actions }: { eyebrow: string; title: string; lede?: string; actions?: React.ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <span className="eyebrow">{eyebrow}</span>
        <h1 className="page-title mt-3">{title}</h1>
        {lede ? <p className="lede mt-3">{lede}</p> : null}
      </div>
      {actions}
    </header>
  );
}

/** One-line "what happens here / what to do next" strip under every page header. */
export function HereStrip({ here, next }: { here: string; next: string }) {
  return (
    <p className="here-strip" data-testid="here-strip">
      <span>{here}</span> <strong>{next}</strong>
    </p>
  );
}

export function Footer() {
  return (
    <footer className="mt-10 border-t border-[var(--border)] py-5 text-[11.5px] text-[var(--muted-foreground)]">
      {FOOTER_TEXT}
    </footer>
  );
}

export function Field({ label, htmlFor, children, className }: { label: string; htmlFor: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={className}>
      <label htmlFor={htmlFor} className="label mb-1.5 block">
        {label}
      </label>
      {children}
    </div>
  );
}

export function KV({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[110px_1fr] gap-3 py-1.5 text-[12.5px] sm:grid-cols-[130px_1fr]">
      <dt className="label pt-0.5">{k}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  );
}

/** Highlights `<mark>` runs from a backend snippet without ever injecting HTML. */
export function Snippet({ html }: { html: string }) {
  return (
    <>
      {parseSnippet(html).map((p, i) => (p.mark ? <mark key={i} className="hl">{p.text}</mark> : <span key={i}>{p.text}</span>))}
    </>
  );
}
