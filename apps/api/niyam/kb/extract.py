"""Turn a source file into ordered text blocks (paragraphs, headings, table rows) with page numbers.

Design notes
- Tables matter: in the RBI TAT circular one table ROW is one obligation (UPI row 4a vs 4b), so rows are
  emitted as their own blocks with row-spans expanded (a UPI row keeps its 'Unified Payments Interface' label).
- Extraction never "summarises": block text is the source text, whitespace-normalised only.
- No network, no LLM. Anything that cannot be extracted is reported (status=empty/failed), never silently dropped.
"""
from __future__ import annotations

import html as htmllib
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

WS = re.compile(r"\s+")


def norm(s: str) -> str:
    return WS.sub(" ", s).strip()


@dataclass
class Block:
    kind: str                 # paragraph | table_row
    text: str
    page: int | None = None


@dataclass
class Extracted:
    blocks: list[Block] = field(default_factory=list)
    pages: int | None = None
    status: str = "ok"        # ok | empty | failed
    note: str = ""
    meta: dict = field(default_factory=dict)   # e.g. source_url, title from front-matter / header comment

    @property
    def chars(self) -> int:
        return sum(len(b.text) for b in self.blocks)


# ----------------------------------------------------------------------------- PDF

def _drop_running_headers(blocks: list[Block], pages: int) -> list[Block]:
    """Remove short lines repeated on many pages (page headers/footers, copyright lines)."""
    if pages < 4:
        return blocks
    counts: Counter = Counter()
    seen_on: dict[str, set] = {}
    for b in blocks:
        if b.kind != "paragraph" or len(b.text) > 160 or b.page is None:
            continue
        key = re.sub(r"\d+", "#", b.text.lower())
        seen_on.setdefault(key, set()).add(b.page)
    for k, s in seen_on.items():
        counts[k] = len(s)
    limit = max(3, int(0.4 * pages))
    drop = {k for k, n in counts.items() if n >= limit}
    return [b for b in blocks if not (b.kind == "paragraph" and len(b.text) <= 160 and re.sub(r"\d+", "#", b.text.lower()) in drop)]


def extract_pdf(path: Path) -> Extracted:
    import pymupdf as fitz  # PyMuPDF

    out = Extracted()
    try:
        doc = fitz.open(path)
    except Exception as e:  # noqa: BLE001
        return Extracted(status="failed", note=f"cannot open PDF: {e}")
    out.pages = doc.page_count
    use_tables = doc.page_count <= 150  # table detection is slow on very long documents
    for pno in range(doc.page_count):
        page = doc[pno]
        table_boxes: list[tuple] = []
        rows_here: list[Block] = []
        if use_tables:
            try:
                for t in page.find_tables().tables:
                    data = t.extract()
                    if not data or len(data) < 2 or max(len(r) for r in data) < 2:
                        continue
                    table_boxes.append(tuple(t.bbox))
                    header = [norm(c or "") for c in data[0]]
                    carry = [""] * len(header)
                    for r in data[1:]:
                        cells = []
                        for i, c in enumerate(r):
                            c = norm(c or "")
                            if not c and i < len(carry):
                                c = carry[i]          # merged (row-spanned) cell: inherit the label above
                            elif i < len(carry):
                                carry[i] = c
                            cells.append(c)
                        txt = " | ".join(f"{h}: {c}" if h else c for h, c in zip(header, cells) if c)
                        if len(txt) > 8:
                            rows_here.append(Block("table_row", txt, pno + 1))
            except Exception:  # noqa: BLE001
                table_boxes, rows_here = [], []
        for b in page.get_text("blocks", sort=True):
            if b[6] != 0:
                continue
            # Text blocks inside detected tables are KEPT: table detection can garble columns, and we never drop source text.
            t = norm(b[4])
            if t:
                out.blocks.append(Block("paragraph", t, pno + 1))
        out.blocks.extend(rows_here)
    out.blocks = _drop_running_headers(out.blocks, out.pages)
    if out.chars < 200:
        out.status, out.note = "empty", "no usable text layer (scanned?); use OCR sidecar"
    return out


def raw_pdf_text(path: Path) -> str:
    import pymupdf as fitz

    with fitz.open(path) as doc:
        return norm(" ".join(p.get_text() for p in doc))


# ----------------------------------------------------------------------------- HTML

def _expand_table(tbl) -> list[list[str]]:
    """Expand rowspan/colspan into a rectangular grid of cell texts."""
    grid: list[list[str]] = []
    pending: dict[tuple[int, int], str] = {}
    for ri, tr in enumerate(tbl.find_all("tr")):
        row: list[str] = []
        ci = 0
        for cell in tr.find_all(["td", "th"], recursive=False):
            while (ri, ci) in pending:
                row.append(pending.pop((ri, ci)))
                ci += 1
            txt = norm(cell.get_text(" "))
            rs = int(cell.get("rowspan", 1) or 1) if str(cell.get("rowspan", "1")).isdigit() else 1
            cs = int(cell.get("colspan", 1) or 1) if str(cell.get("colspan", "1")).isdigit() else 1
            for k in range(cs):
                row.append(txt)
                for r2 in range(1, rs):
                    pending[(ri + r2, ci + k)] = txt
            ci += cs
        while (ri, ci) in pending:
            row.append(pending.pop((ri, ci)))
            ci += 1
        if row:
            grid.append(row)
    return grid


def extract_html(path: Path) -> Extracted:
    from bs4 import BeautifulSoup

    raw = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(raw, "lxml")
    out = Extracted()
    if soup.title and soup.title.string:
        out.meta["title"] = norm(soup.title.string)
    # NOTE: never strip <form>: RBI's ASP.NET pages wrap the entire body in one.
    for t in soup(["script", "style", "noscript", "svg"]):
        t.decompose()
    tables = soup.find_all("table")
    table_rows: list[list[Block]] = []
    for i, tbl in enumerate(tables):
        if tbl.find("table"):         # layout table wrapping other tables: leave the text, handle inner ones
            continue
        grid = _expand_table(tbl)
        if len(grid) < 2 or max(len(r) for r in grid) < 2:
            continue
        header = grid[0]
        rows: list[Block] = []
        group = ""
        for r in grid[1:]:
            distinct = [c for i, c in enumerate(r) if c and (i == 0 or c != r[i - 1])]
            if len(distinct) == 2 and re.fullmatch(r"\d{1,3}", distinct[0]):
                group = distinct[1]                    # group-header row: remember its label for the sub-rows below
            elif group and distinct and not re.fullmatch(r"\d{1,3}", distinct[0]):
                pass
            else:
                group = "" if distinct and re.fullmatch(r"\d{1,3}", distinct[0]) else group
            cells, last = [], None
            for h, c in zip(header, r):
                if c and c != last:
                    cells.append(f"{h}: {c}" if h and h != c else c)
                last = c
            txt = " | ".join(cells)
            if group and not (len(distinct) == 2 and re.fullmatch(r"\d{1,3}", distinct[0])):
                txt = f"{group} | {txt}"
            if len(txt) > 8:
                rows.append(Block("table_row", txt))
        tbl.replace_with(soup.new_string(f"\n@@TABLE{len(table_rows)}@@\n"))
        table_rows.append(rows)
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for tag in soup.find_all(["p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "blockquote", "pre"]):
        tag.insert_before("\n")
        tag.insert_after("\n")
    text = htmllib.unescape(soup.get_text(""))
    for line in text.split("\n"):
        line = norm(line)
        if not line:
            continue
        m = re.fullmatch(r"@@TABLE(\d+)@@", line)
        if m:
            out.blocks.extend(table_rows[int(m.group(1))])
        else:
            out.blocks.append(Block("paragraph", line))
    out.pages = None
    if out.chars < 200:
        out.status, out.note = "empty", "no usable text in HTML"
    return out


def raw_html_text(path: Path) -> str:
    t = path.read_text(encoding="utf-8", errors="ignore")
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S)
    return norm(htmllib.unescape(re.sub(r"<[^>]+>", " ", t)))


# ----------------------------------------------------------------------------- Markdown / text

FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
SRC_COMMENT = re.compile(r"<!--\s*Source:\s*(\S+)(.*?)-->", re.S)


def extract_md(path: Path) -> Extracted:
    import yaml

    raw = path.read_text(encoding="utf-8", errors="ignore")
    out = Extracted()
    m = FRONT.match(raw)
    if m:
        try:
            fm = yaml.safe_load(m.group(1)) or {}
            if isinstance(fm, dict):
                out.meta.update({k: v for k, v in fm.items() if isinstance(v, (str, int, float))})
        except Exception:  # noqa: BLE001
            pass
        raw = raw[m.end():]
    c = SRC_COMMENT.search(raw)
    if c:
        out.meta.setdefault("source_url", c.group(1))
        out.meta["header_comment"] = norm(c.group(2))
    raw = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    para: list[str] = []
    table: list[str] = []

    def flush_para():
        if para:
            t = norm(" ".join(para))
            if t:
                out.blocks.append(Block("paragraph", t))
            para.clear()

    def flush_table():
        if len(table) >= 2:
            hdr = [norm(c) for c in table[0].strip().strip("|").split("|")]
            for line in table[1:]:
                if re.fullmatch(r"[\s|:\-]+", line):
                    continue
                cells = [norm(c) for c in line.strip().strip("|").split("|")]
                txt = " | ".join(f"{h}: {c}" if h else c for h, c in zip(hdr, cells) if c)
                if len(txt) > 8:
                    out.blocks.append(Block("table_row", txt))
        elif table:
            out.blocks.append(Block("paragraph", norm(" ".join(table))))
        table.clear()

    for line in raw.split("\n"):
        if line.lstrip().startswith("|"):
            flush_para()
            table.append(line)
            continue
        if table:
            flush_table()
        if not line.strip():
            flush_para()
        elif re.match(r"^\s{0,3}#{1,6}\s", line):
            flush_para()
            out.blocks.append(Block("paragraph", norm(re.sub(r"^\s*#+\s*", "", line))))
        else:
            para.append(line)
    flush_para()
    flush_table()
    if out.chars < 200:
        out.status, out.note = "empty", "no usable text"
    return out


OCR_PAGE = re.compile(r"^--- page (\d+) ---$", re.M)


def extract_ocr_txt(path: Path) -> Extracted:
    """Machine-read OCR sidecar written by the corpus team (`_ocr/*.ocr.txt`). Marked ocr by the caller."""
    raw = path.read_text(encoding="utf-8", errors="ignore")
    raw = "\n".join(l for l in raw.split("\n") if not l.startswith("# "))
    out = Extracted()
    parts = OCR_PAGE.split(raw)
    pages = 0
    if len(parts) == 1:
        parts = ["", "1", raw]
    for i in range(1, len(parts), 2):
        pno, body = int(parts[i]), parts[i + 1]
        pages = max(pages, pno)
        text = norm(body)
        if text:
            out.blocks.append(Block("paragraph", text, pno))
    out.pages = pages or None
    if out.chars < 100:
        out.status, out.note = "empty", "OCR sidecar has no text"
    return out


def extract(path: Path) -> Extracted:
    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            return extract_pdf(path)
        if ext in (".html", ".htm"):
            return extract_html(path)
        if ext == ".md":
            return extract_md(path)
        if ext == ".txt":
            return extract_ocr_txt(path)
    except Exception as e:  # noqa: BLE001
        return Extracted(status="failed", note=f"{type(e).__name__}: {e}")
    return Extracted(status="failed", note=f"unsupported extension {ext}")


def raw_text(path: Path) -> str:
    """Whole-document normalised text, used to verify rule-card quotes (exact substring after whitespace normalisation)."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return raw_pdf_text(path)
    if ext in (".html", ".htm"):
        return raw_html_text(path)
    return norm(path.read_text(encoding="utf-8", errors="ignore"))
