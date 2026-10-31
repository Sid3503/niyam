"""PDF in, text + geometry out; and the writer used by the workbench.

Extraction turns each PDF text block into one paragraph of `content` (blank-line separated, so segment() sees clauses) and records
`page_map = [{start, end, page, bbox}]` for every block, with offsets into `content`. A finding's quote is located back on the page from that map.

Writing (workbench) uses PyMuPDF REAL redaction: the old text is removed from the page's content stream, then the replacement is inserted. Covering words
with a white box is never used as the fix (the old text would still extract). If the new wording cannot fit its block, even after growing into free space below it,
the edit is REFUSED (WordingDoesNotFit). We do not rasterize the page: that would drop every other clause on it from the engine's view and cause false passes.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import pymupdf

from niyam.kb.extract import norm
from niyam.review.segment import Clause, sentences


def _clean(s: str) -> str:
    s = s.replace("­", "").replace("​", "")
    s = re.sub(r"[ \t]*\n[ \t]*", " ", s)           # line wraps inside a block are not paragraph breaks
    return re.sub(r"[ \t]{2,}", " ", s).strip()


@dataclass
class Extracted:
    content: str
    page_map: list[dict]
    page_sizes: list[list[float]]
    pages: int


def extract(data: bytes) -> Extracted:
    doc = pymupdf.open(stream=data, filetype="pdf")
    parts: list[str] = []
    pmap: list[dict] = []
    sizes: list[list[float]] = []
    pos = 0
    for pno, page in enumerate(doc, start=1):
        sizes.append([round(page.rect.width, 2), round(page.rect.height, 2)])
        blocks = [b for b in page.get_text("blocks", sort=True) if b[6] == 0]       # text blocks only
        for b in blocks:
            txt = _clean(b[4])
            if not txt:
                continue
            # a block that holds several numbered clauses (common in generated PDFs) is split so each clause is its own paragraph
            lines = [ln.strip() for ln in b[4].split("\n") if ln.strip()]
            start_idx = [i for i, ln in enumerate(lines) if re.match(r"^(\d+(\.\d+)*[.)]\s+|[-•*]\s+)", ln)]
            chunks = []
            if len(start_idx) > 1:
                bounds = start_idx + [len(lines)]
                if start_idx[0] > 0:
                    chunks.append((0, start_idx[0]))
                chunks += [(bounds[i], bounds[i + 1]) for i in range(len(start_idx))]
            else:
                chunks.append((0, len(lines)))
            n_lines = max(1, len(lines))
            h = (b[3] - b[1]) / n_lines
            for a, z in chunks:
                t = _clean("\n".join(lines[a:z]))
                if not t:
                    continue
                if parts:
                    pos += 2
                    parts.append("\n\n")
                start = pos
                parts.append(t)
                pos += len(t)
                bbox = [round(b[0], 2), round(b[1] + a * h, 2), round(b[2], 2), round(b[1] + z * h, 2)]
                pmap.append({"start": start, "end": pos, "page": pno, "bbox": bbox})
    return Extracted("".join(parts), pmap, sizes, doc.page_count)


def locate(data: bytes, ex_map: list[dict], start: int, end: int, quote: str) -> tuple[int, list[float]] | None:
    """Page + bbox for a span of content. Tries the exact text on the page; falls back to the covering block."""
    cover = [m for m in ex_map if m["end"] > start and m["start"] < end]
    if not cover:
        return None
    first = cover[0]
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
        page = doc[first["page"] - 1]
        words = quote.split()
        for n in (len(words), 12, 8, 5):                    # long quotes wrap lines; search_for matches a shorter head
            if n > len(words) or n < 2:
                continue
            rects = page.search_for(" ".join(words[:n]), clip=pymupdf.Rect(first["bbox"]) + (-3, -3, 3, 3))
            if rects:
                r = rects[0]
                for x in rects[1:]:
                    r |= x
                tail = page.search_for(" ".join(words[-min(5, len(words)):]), clip=pymupdf.Rect(first["bbox"]) + (-3, -3, 3, 3))
                for x in tail:
                    r |= x
                return first["page"], [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)]
    except Exception:  # noqa: BLE001
        pass
    return first["page"], first["bbox"]


# ------------------------------------------------------------------ writer
class WordingDoesNotFit(ValueError):
    def __init__(self, finding_id: str):
        super().__init__(finding_id)
        self.finding_id = finding_id


@dataclass
class Edit:
    finding_id: str
    wording: str
    quote: str | None
    page: int | None
    bbox: list[float] | None
    span: tuple[int, int] | None


def _fit(page, rect, text: str, size: float):
    """Largest font size (down to 8pt) that fits `text` in `rect`; returns the size or None."""
    s = size
    while s >= 8:
        probe = pymupdf.open()
        pg = probe.new_page(width=page.rect.width, height=page.rect.height)
        if pg.insert_textbox(rect, text, fontsize=s, fontname="helv") >= 0:
            return s
        s -= 0.5
    return None



def _new_clause(ex: "Extracted", block: dict, grp: list[Edit]) -> str:
    """The clause text with each quoted SENTENCE replaced (a quote can be just the tail of a sentence)."""
    clause = ex.content[block["start"]:block["end"]]
    sents = sentences(Clause(0, "", clause, block["start"], block["end"]))
    repl = []
    for e in grp:
        hit = next((x for x in sents if x[0] <= e.span[0] < x[1] or (x[0] < e.span[1] <= x[1])), None)
        if hit is None:
            raise WordingDoesNotFit(e.finding_id)
        repl.append((hit[0] - block["start"], hit[1] - block["start"], e.wording, e.finding_id))
    repl.sort(reverse=True)
    out, last = clause, None
    for a0, a1, w, fid in repl:
        if last is not None and a1 > last:
            raise WordingDoesNotFit(fid)                          # two edits fighting over one sentence
        out = out[:a0] + w + out[a1:]
        last = a0
    return out


def _font_for(page, rect) -> tuple[float, str]:
    try:
        spans = [sp for b in page.get_text("dict", clip=rect)["blocks"] if b.get("type") == 0 for ln in b["lines"] for sp in ln["spans"]]
        if spans:
            sp = spans[0]
            bold = bool(sp["flags"] & 16) or "bold" in sp["font"].lower()
            return max(8.0, min(24.0, sp["size"])), ("hebo" if bold else "helv")
    except Exception:  # noqa: BLE001
        pass
    return 10.0, "helv"


def _try_fit(page, block: dict, new_clause: str):
    rect = pymupdf.Rect(block["bbox"]) + (-1, -1, 1, 1)
    size, _ = _font_for(page, rect)
    below = [b[1] for b in page.get_text("blocks") if b[6] == 0 and b[1] >= rect.y1 - 1 and abs(b[0] - rect.x0) < 400]
    limit = min([y - 2 for y in below] + [rect.y1 + 40, page.rect.height - 36])
    grown = pymupdf.Rect(rect.x0, rect.y0, rect.x1, max(rect.y1, limit))
    fitted = _fit(page, grown, new_clause, size)
    return None if fitted is None else (rect, grown, fitted)


def _used_height(width: float, text: str, size: float, font: str) -> float:
    probe = pymupdf.open()
    pg = probe.new_page(width=width + 20, height=3000)
    rc = pg.insert_textbox(pymupdf.Rect(0, 0, width, 3000), text, fontsize=size, fontname=font)
    return (3000 - rc) if rc >= 0 else 3000


def _reflow_page(doc, page, ex: "Extracted", pno: int, items) -> None:
    """Re-typeset the page's text units top to bottom so that longer wording pushes the content below it down. Fail closed if it does not fit.
    Only text-only pages are reflowed: a page with images or vector graphics would need real layout, so the edit is refused instead of corrupted."""
    if page.get_images() or page.get_drawings():
        raise WordingDoesNotFit(items[0][2][0].finding_id)
    units = sorted([m for m in ex.page_map if m["page"] == pno], key=lambda m: m["bbox"][1])
    edited = {b["start"]: n for b, n, _g in items}
    prepared = []
    for m in units:
        rect = pymupdf.Rect(m["bbox"])
        size, font = _font_for(page, rect + (-1, -1, 1, 1))
        txt = edited.get(m["start"], ex.content[m["start"]:m["end"]])
        prepared.append((m, rect, txt, size, font))
    for _m, rect, *_ in prepared:
        page.add_redact_annot(rect + (-1.5, -1.5, 1.5, 1.5))
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
    shift = 0.0
    bottom_limit = page.rect.height - 36
    for m, rect, txt, size, font in prepared:
        h_old = rect.height
        h_new = _used_height(rect.width, txt, size, font) + 2
        top = rect.y0 + shift
        r = pymupdf.Rect(rect.x0, top, rect.x1, top + max(h_old, h_new) + 2)
        if r.y1 > bottom_limit:
            raise WordingDoesNotFit(items[0][2][0].finding_id)
        page.insert_textbox(r, txt, fontsize=size, fontname=font)
        if h_new > h_old:
            shift += h_new - h_old


def apply_edits(data: bytes, ex: Extracted, edits: list[Edit]) -> tuple[bytes, list[dict]]:
    doc = pymupdf.open(stream=data, filetype="pdf")
    strategies: list[dict] = []
    append: list[Edit] = []
    # group edits by the block (clause) they land in, so two edits to one clause are applied together and the clause is rewritten once
    groups: dict[tuple[int, int], list[Edit]] = {}
    for e in edits:
        if not (e.page and e.bbox and e.span and e.quote):
            append.append(e)                                  # a missing-disclosure finding: no existing text to replace
            continue
        block = next((m for m in ex.page_map if m["page"] == e.page and m["start"] <= e.span[0] < m["end"]), None)
        if block is None:
            raise WordingDoesNotFit(e.finding_id)
        groups.setdefault((block["page"], block["start"]), []).append(e)
    # Plan every group first (no page is touched yet): which fit in place, which need the page re-typeset downward
    plans: dict[int, list[tuple[dict, str, list[Edit]]]] = {}
    for (pno, bstart), grp in groups.items():
        block = next(m for m in ex.page_map if m["page"] == pno and m["start"] == bstart)
        plans.setdefault(pno, []).append((block, _new_clause(ex, block, grp), grp))
    for pno, items in plans.items():
        page = doc[pno - 1]
        in_place = all(_try_fit(page, block, new_clause) is not None for block, new_clause, _g in items)
        if in_place:
            for block, new_clause, grp in items:
                rect, grown, fitted = _try_fit(page, block, new_clause)
                page.add_redact_annot(rect)                       # REAL removal of the text under the rect
                page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
                page.insert_textbox(grown, new_clause, fontsize=fitted, fontname="helv")
                strategies += [{"finding_id": e.finding_id, "method": "redact_rewrite"} for e in grp]
        else:
            _reflow_page(doc, page, ex, pno, items)
            strategies += [{"finding_id": e.finding_id, "method": "redact_rewrite"} for _b, _n, grp in items for e in grp]
    if append:
        page = doc[-1]
        y = page.rect.height - 40
        last = [b for b in page.get_text("blocks") if b[6] == 0]
        top = max((b[3] for b in last), default=60) + 18
        need = 30 + sum(14 * (len(a.wording) // 85 + 2) for a in append)
        if top + need > page.rect.height - 40:
            page = doc.new_page(width=page.rect.width, height=page.rect.height)
            top = 60
        page.insert_text((54, top), "Additional terms", fontsize=12, fontname="hebo")
        yy = top + 18
        for i, a in enumerate(append, start=1):
            h = 14 * (len(a.wording) // 85 + 2)
            page.insert_textbox(pymupdf.Rect(54, yy, page.rect.width - 54, yy + h), f"{i}. {a.wording}", fontsize=10, fontname="helv")
            yy += h
            strategies.append({"finding_id": a.finding_id, "method": "append_text"})
    doc.set_metadata({})                                       # no author/producer/dates carried into the new version
    out = doc.tobytes(garbage=4, deflate=True)
    return out, strategies


def render_page(data: bytes, page: int, dpi: int = 110) -> bytes:
    doc = pymupdf.open(stream=data, filetype="pdf")
    if page < 1 or page > doc.page_count:
        raise IndexError("page out of range")
    return doc[page - 1].get_pixmap(dpi=dpi).tobytes("png")


def page_hash(data: bytes, page: int) -> str:
    import hashlib
    doc = pymupdf.open(stream=data, filetype="pdf")
    if page > doc.page_count:
        return "absent"
    return hashlib.sha256(doc[page - 1].get_pixmap(dpi=60).tobytes("png")).hexdigest()


def stale(quote: str | None, new_content: str) -> bool:
    return bool(quote and quote.strip() and norm(quote) in norm(new_content))
