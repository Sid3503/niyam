"""Render selected synthetic library markdown documents as real PDFs (text layer, multiple pages) with a `.pdf.meta.json` sidecar.
Usage: python tools/make_demo_pdfs.py   (needs PyMuPDF; run from the repo root). The markdown originals move to library/_source/."""
import html, json, re, shutil, sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "library"
TARGETS = ["proposal-bluecart-payment-gateway.md", "agreement-bluecart-payment-gateway.md"]


def front(raw):
    if not raw.startswith("---"):
        return {}, raw
    end = raw.find("\n---", 3)
    meta = {}
    for ln in raw[3:end].strip().splitlines():
        if ":" in ln:
            k, v = ln.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, raw[end + 4:].lstrip("\n")


def to_html(meta, body):
    out = ["<body style='font-family: sans-serif; font-size: 10.5pt; line-height: 1.4'>"]
    out.append(f"<p style='font-size:8pt; color:#555'>{html.escape(meta.get('merchant') or 'Paytm')} &middot; synthetic demo document</p>")
    for blk in re.split(r"\n\s*\n", body.strip()):
        blk = blk.strip()
        if blk.startswith("# "):
            out.append(f"<h1 style='font-size:19pt; margin:0 0 6pt 0'>{html.escape(blk[2:])}</h1>")
        elif blk.startswith("## "):
            out.append(f"<h2 style='font-size:13pt; margin:14pt 0 4pt 0'>{html.escape(blk[3:])}</h2>")
        else:
            out.append(f"<p style='margin:0 0 7pt 0'>{html.escape(blk)}</p>")
    out.append("</body>")
    return "".join(out)


def render(md: Path):
    meta, body = front(md.read_text(encoding="utf-8"))
    story = pymupdf.Story(to_html(meta, body))
    out = LIB / (md.stem + ".pdf")
    w = pymupdf.DocumentWriter(str(out))
    mediabox = pymupdf.paper_rect("a4")
    where = mediabox + (54, 60, -54, -60)
    more = 1
    while more:
        dev = w.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(dev)
        w.end_page()
    w.close()
    (LIB / (md.stem + ".pdf.meta.json")).write_text(json.dumps({k: v for k, v in meta.items()}, indent=2), encoding="utf-8")
    shutil.move(str(md), str(LIB / "_source" / md.name))
    print("wrote", out.name, pymupdf.open(str(out)).page_count, "page(s)")


if __name__ == "__main__":
    for t in TARGETS:
        p = LIB / t
        if p.exists():
            render(p)
        else:
            print("skip (already converted):", t, file=sys.stderr)
