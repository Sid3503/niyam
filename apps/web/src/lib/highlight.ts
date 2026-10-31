/**
 * Locating a verdict quote inside the checked text.
 *
 * The contract says `span` is "char offsets into the checked text". A Python
 * backend counts code points; JS strings count UTF-16 units. They differ as
 * soon as the text holds an emoji. We therefore try, in order:
 *   1. span as UTF-16 offsets
 *   2. span as code-point offsets
 *   3. the first exact occurrence of the quote
 * and report which one matched, or `none` so the UI can say the quote could not
 * be located instead of highlighting the wrong characters.
 */
export type Located =
  | { ok: true; start: number; end: number; how: "span" | "span-codepoints" | "search" }
  | { ok: false };

export function locateQuote(text: string, quote: string | null, span: [number, number] | null): Located {
  if (!quote) return { ok: false };
  if (span && Array.isArray(span) && span.length === 2) {
    const [s, e] = span;
    if (Number.isInteger(s) && Number.isInteger(e) && s >= 0 && e > s && e <= text.length && text.slice(s, e) === quote) {
      return { ok: true, start: s, end: e, how: "span" };
    }
    const cps = Array.from(text);
    if (Number.isInteger(s) && Number.isInteger(e) && s >= 0 && e > s && e <= cps.length) {
      if (cps.slice(s, e).join("") === quote) {
        const start = cps.slice(0, s).join("").length;
        return { ok: true, start, end: start + quote.length, how: "span-codepoints" };
      }
    }
  }
  const idx = text.indexOf(quote);
  if (idx >= 0) return { ok: true, start: idx, end: idx + quote.length, how: "search" };
  return { ok: false };
}

export interface SnippetPart {
  text: string;
  mark: boolean;
}

/** Split a backend snippet on <mark>…</mark>. Everything else is plain text (never injected as HTML). */
export function parseSnippet(snippet: string): SnippetPart[] {
  const parts: SnippetPart[] = [];
  const re = /<mark>([\s\S]*?)<\/mark>/gi;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(snippet))) {
    if (m.index > last) parts.push({ text: snippet.slice(last, m.index), mark: false });
    parts.push({ text: m[1], mark: true });
    last = m.index + m[0].length;
  }
  if (last < snippet.length) parts.push({ text: snippet.slice(last), mark: false });
  return parts.map((p) => ({ ...p, text: p.text.replace(/<\/?mark>/gi, "") }));
}
