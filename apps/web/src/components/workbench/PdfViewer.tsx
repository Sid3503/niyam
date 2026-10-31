import * as React from "react";
import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut } from "lucide-react";
import * as pdfjs from "pdfjs-dist";
import type { PDFDocumentProxy, PDFDocumentLoadingTask } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { ErrorState, LoadingBlock } from "@/components/States";
import { api } from "@/lib/api";
import { FINDING_TONE } from "@/lib/format";
import type { Finding } from "@/lib/types";
import { bboxToRect, pageAtOffset, scaleForZoom, stepZoom, type PageSize } from "./geometry";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

export interface FocusRequest {
  page: number;
  /** y in PDF points to bring into view (top of the finding). */
  y?: number;
  nonce: number;
}

const TONE_VAR = { ok: "--ok", warn: "--warn", bad: "--bad", neutral: "--taupe" } as const;

function PageCanvas({ pdf, pageNo, size, scale, root, overlays, selectedId, onSelect, pageRef }: {
  pdf: PDFDocumentProxy;
  pageNo: number;
  size: PageSize;
  scale: number;
  root: HTMLElement | null;
  overlays: Finding[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  pageRef: (el: HTMLDivElement | null) => void;
}) {
  const wrap = React.useRef<HTMLDivElement | null>(null);
  const canvas = React.useRef<HTMLCanvasElement>(null);
  const [visible, setVisible] = React.useState(pageNo <= 2);
  const [failed, setFailed] = React.useState<string | null>(null);

  React.useEffect(() => {
    const el = wrap.current;
    if (!el || typeof IntersectionObserver === "undefined") { setVisible(true); return; }
    const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) setVisible(true); }, { root, rootMargin: "800px 0px" });
    io.observe(el);
    return () => io.disconnect();
  }, [root]);

  React.useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    let task: { cancel: () => void; promise: Promise<unknown> } | null = null;
    void (async () => {
      try {
        const page = await pdf.getPage(pageNo);
        if (cancelled || !canvas.current) return;
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        const vp = page.getViewport({ scale: scale * dpr });
        const c = canvas.current;
        c.width = Math.floor(vp.width);
        c.height = Math.floor(vp.height);
        task = page.render({ canvas: c, viewport: vp });
        await task.promise;
        setFailed(null);
      } catch (e) {
        const name = (e as { name?: string } | null)?.name;
        if (!cancelled && name !== "RenderingCancelledException") setFailed("This page could not be drawn.");
      }
    })();
    return () => { cancelled = true; task?.cancel(); };
  }, [pdf, pageNo, scale, visible]);

  const w = size[0] * scale;
  const h = size[1] * scale;
  return (
    <div
      ref={(el) => { wrap.current = el; pageRef(el); }}
      className="relative mx-auto mb-4 bg-white shadow-[0_1px_3px_rgba(28,27,26,0.18)]"
      style={{ width: w, height: h }}
      data-page={pageNo}
    >
      <canvas ref={canvas} style={{ width: w, height: h, display: "block" }} aria-label={`Page ${pageNo}`} role="img" />
      {failed ? <p role="alert" className="absolute inset-0 grid place-items-center text-[12px] text-[var(--bad-ink)]">{failed}</p> : null}
      {overlays.map((f) => {
        const r = f.bbox ? bboxToRect(f.bbox, size, scale) : null;
        if (!r) return null;
        const tone = TONE_VAR[FINDING_TONE[f.status]];
        const sel = f.id === selectedId;
        return (
          <button
            key={f.id}
            type="button"
            data-finding-box={f.id}
            data-selected={sel ? "true" : undefined}
            aria-label={`Finding on page ${pageNo}: ${f.status}${f.quote ? `, ${f.quote}` : ""}`}
            aria-pressed={sel}
            onClick={() => onSelect(f.id)}
            className="absolute cursor-pointer rounded-[3px] p-0"
            style={{
              left: r.left - 2, top: r.top - 2, width: r.width + 4, height: r.height + 4,
              border: `${sel ? 2 : 1}px solid var(${tone})`,
              background: `color-mix(in srgb, var(${tone}) ${sel ? 30 : 16}%, transparent)`,
              boxShadow: sel ? `0 0 0 3px color-mix(in srgb, var(${tone}) 28%, transparent)` : undefined,
            }}
          />
        );
      })}
    </div>
  );
}

/** pdf.js canvas viewer. Fetches the file with auth headers (the API may need X-API-Key), draws pages lazily, overlays finding boxes. */
export function PdfViewer({ url, pageSizes, findings, selectedId, onSelect, focus, showOverlays = true, badge, onPages }: {
  url: string;
  pageSizes?: PageSize[];
  findings: Finding[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  focus: FocusRequest | null;
  showOverlays?: boolean;
  badge?: React.ReactNode;
  onPages?: (n: number) => void;
}) {
  const [pdf, setPdf] = React.useState<PDFDocumentProxy | null>(null);
  const [sizes, setSizes] = React.useState<PageSize[]>([]);
  const [err, setErr] = React.useState<unknown>(null);
  const [loading, setLoading] = React.useState(true);
  const [zoom, setZoom] = React.useState(1);
  const [cur, setCur] = React.useState(1);
  const [scroller, setScroller] = React.useState<HTMLDivElement | null>(null);
  const pageEls = React.useRef<(HTMLDivElement | null)[]>([]);
  const [attempt, setAttempt] = React.useState(0);

  React.useEffect(() => {
    let dead = false;
    let doc: PDFDocumentProxy | null = null;
    let task: PDFDocumentLoadingTask | null = null;
    setLoading(true); setErr(null); setPdf(null);
    void (async () => {
      try {
        const buf = await (await api.blob(url)).arrayBuffer();
        task = pdfjs.getDocument({ data: buf });
        doc = await task.promise;
        const ps: PageSize[] = [];
        for (let i = 1; i <= doc.numPages; i++) {
          const v = (await doc.getPage(i)).getViewport({ scale: 1 });
          ps.push([v.width, v.height]);
        }
        if (dead) { void task.destroy(); return; }
        setSizes(ps); setPdf(doc); setCur(1); onPages?.(doc.numPages);
      } catch (e) {
        if (!dead) setErr(e);
      } finally {
        if (!dead) setLoading(false);
      }
    })();
    return () => { dead = true; if (task) void task.destroy(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, attempt]);

  const fitted = React.useRef<string>("");
  React.useEffect(() => {          // fit the page width to the panel once per document, so no clause is clipped; the zoom buttons still work afterwards
    if (!scroller || !sizes.length || fitted.current === url) return;
    const avail = scroller.clientWidth - 40;
    if (avail > 100) {
      fitted.current = url;
      setZoom(Math.max(0.4, Math.min(2, Math.floor((avail / (sizes[0][0] * scaleForZoom(1))) * 20) / 20)));
    }
  }, [scroller, sizes, url]);

  const scale = scaleForZoom(zoom);
  const n = sizes.length;
  const sizeOf = (i: number): PageSize => pageSizes?.[i] ?? sizes[i];

  const goTo = React.useCallback((page: number, y = 0) => {
    const el = pageEls.current[page - 1];
    if (!el || !scroller) return;
    scroller.scrollTo({ top: Math.max(0, el.offsetTop + y * scale - 90), behavior: "smooth" });
  }, [scroller, scale]);

  React.useEffect(() => {
    if (focus && pdf) goTo(Math.min(Math.max(1, focus.page), pdf.numPages), focus.y ?? 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus?.nonce, pdf]);

  const onScroll = () => {
    if (!scroller) return;
    setCur(pageAtOffset(pageEls.current.map((e) => e?.offsetTop ?? 0), scroller.scrollTop + 40));
  };

  return (
    <div className="flex min-w-0 flex-col" data-testid="pdf-viewer">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1" role="group" aria-label="Page navigation">
          <button type="button" className="btn btn-sm" aria-label="Previous page" disabled={cur <= 1} onClick={() => goTo(cur - 1)}><ChevronLeft size={14} /></button>
          <label className="flex items-center gap-1 text-[12px]">
            <span className="sr-only">Page number</span>
            <input
              className="field !w-12 !px-1.5 !py-1 text-center"
              inputMode="numeric"
              value={cur}
              onChange={(e) => { const v = Number(e.target.value); if (Number.isInteger(v) && v >= 1 && v <= n) goTo(v); }}
              aria-label="Page number"
            />
            <span className="text-[var(--muted-foreground)]">of {n || "—"}</span>
          </label>
          <button type="button" className="btn btn-sm" aria-label="Next page" disabled={cur >= n} onClick={() => goTo(cur + 1)}><ChevronRight size={14} /></button>
        </div>
        <div className="flex items-center gap-1" role="group" aria-label="Zoom">
          <button type="button" className="btn btn-sm" aria-label="Zoom out" onClick={() => setZoom((z) => stepZoom(z, -1))}><ZoomOut size={14} /></button>
          <span className="num w-10 text-center text-[12px]" aria-live="polite">{Math.round(zoom * 100)}%</span>
          <button type="button" className="btn btn-sm" aria-label="Zoom in" onClick={() => setZoom((z) => stepZoom(z, 1))}><ZoomIn size={14} /></button>
        </div>
        {badge ? <div className="ml-auto">{badge}</div> : null}
      </div>
      <div ref={setScroller} onScroll={onScroll} className="relative max-h-[78vh] min-h-[320px] overflow-auto rounded-xl border border-[var(--border)] bg-[var(--muted)] p-4" tabIndex={0} aria-label="PDF pages">
        {loading ? <LoadingBlock rows={6} label="Loading PDF" /> : err ? <ErrorState error={err} onRetry={() => setAttempt((a) => a + 1)} /> : pdf ? sizes.map((_, i) => (
          <PageCanvas
            key={i}
            pdf={pdf}
            pageNo={i + 1}
            size={sizeOf(i)}
            scale={scale}
            root={scroller}
            overlays={showOverlays ? findings.filter((f) => f.page === i + 1 && f.bbox) : []}
            selectedId={selectedId}
            onSelect={onSelect}
            pageRef={(el) => { pageEls.current[i] = el; }}
          />
        )) : null}
      </div>
    </div>
  );
}
