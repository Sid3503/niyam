/** Geometry helpers for drawing finding overlays on rendered PDF pages. */

/** PyMuPDF-style box: [x0, y0, x1, y1] in PDF points, origin top-left. */
export type Bbox = [number, number, number, number];
export type PageSize = [number, number];
export interface ScreenRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** Convert a bbox in PDF points to a CSS rect on a page rendered at `scale` px per point. Clamped to the page; null when degenerate. */
export function bboxToRect(bbox: Bbox, pageSize: PageSize, scale: number): ScreenRect | null {
  const [pw, ph] = pageSize;
  if (!(scale > 0) || !(pw > 0) || !(ph > 0)) return null;
  const x0 = Math.max(0, Math.min(bbox[0], bbox[2]));
  const x1 = Math.min(pw, Math.max(bbox[0], bbox[2]));
  const y0 = Math.max(0, Math.min(bbox[1], bbox[3]));
  const y1 = Math.min(ph, Math.max(bbox[1], bbox[3]));
  if (x1 <= x0 || y1 <= y0) return null;
  return { left: x0 * scale, top: y0 * scale, width: (x1 - x0) * scale, height: (y1 - y0) * scale };
}

/** px per PDF point for a given zoom (1 = 100%, 96/72 css px per point). */
export const BASE_SCALE = 96 / 72;
export function scaleForZoom(zoom: number): number {
  return BASE_SCALE * zoom;
}

export const ZOOM_STEPS = [0.5, 0.75, 1, 1.25, 1.5, 2];
export function stepZoom(zoom: number, dir: 1 | -1): number {
  if (dir === 1) return ZOOM_STEPS.find((z) => z > zoom + 1e-6) ?? ZOOM_STEPS[ZOOM_STEPS.length - 1];
  return [...ZOOM_STEPS].reverse().find((z) => z < zoom - 1e-6) ?? ZOOM_STEPS[0];
}

/** Which page is "current" given page tops (px, ascending) and the scroll offset. */
export function pageAtOffset(tops: number[], scrollTop: number): number {
  let cur = 1;
  for (let i = 0; i < tops.length; i++) if (tops[i] <= scrollTop + 1) cur = i + 1;
  return cur;
}
