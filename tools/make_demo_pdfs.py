"""Render synthetic library markdown as real PDFs (text layer) with a `.pdf.meta.json` sidecar.

Also writes `samples/` PDFs you can upload in the console (Add a document / Add a circular).

Usage (from the repo root, needs PyMuPDF):

    apps/api/.venv/bin/python tools/make_demo_pdfs.py
"""
from __future__ import annotations

import html
import json
import re
import shutil
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "library"
SOURCE = LIB / "_source"
SAMPLES = ROOT / "samples"

SAMPLES_DOCS = [
    {
        "stem": "circular-rbi-upi-tat-synthetic",
        "meta": {
            "title": "Synthetic circular: failed UPI merchant payments (T+5)",
            "kind": "circular",
            "institution": "RBI (synthetic demo text)",
            "product_area": "UPI merchant payments",
        },
        "body": """# Failed UPI merchant payments — customer reversal timeline

SYNTHETIC DEMO CIRCULAR. This is not an official RBI publication. Names, clause numbers and dates are invented for the Niyam prototype.

## 1. Purpose

This note is a dummy circular so you can press Add a circular in Niyam without using a real regulator PDF.

## 2. Obligation

Where a UPI merchant payment fails and the customer's account is debited, the payment system provider shall ensure auto-reversal to the customer within T+5 days (five calendar days from the date of the transaction).

A merchant, aggregator or payment gateway shall not advertise a longer reversal timeline in a proposal, brochure, order form or agreement.

## 3. What not to say

Phrases such as "refund in 7 working days", "refund in 10 days", or "we will try to reverse the amount shortly" do not meet this obligation.

## 4. Effective

Treat this text as effective from 15 September 2025 for the demo only.

Issued for the Niyam prototype. Decision support, not legal advice.
""",
    },
    {
        "stem": "proposal-stale-upi-refunds-synthetic",
        "meta": {
            "title": "Dummy proposal: stale 7-day UPI refunds",
            "doc_type": "proposal",
            "product": "Payment Gateway",
            "owner": "asha.verma@demo.paytm.example",
            "merchant": "Oak Street Grocers Pvt Ltd (synthetic)",
        },
        "body": """# Payment Gateway proposal for Oak Street Grocers

SYNTHETIC DEMO DOCUMENT. Upload this under Documents → Add a document to see Niyam flag a stale refund line.

## 1. Offer

1.1 Accept UPI, cards and netbanking on your website through one integration.

1.2 Your settlement is guaranteed within two hours of every successful payment.

## 2. Refunds

2.1 If a UPI merchant payment fails but the customer is debited, the amount is refunded to the customer within 7 working days.

## 3. Surplus

3.1 Park surplus funds with us and earn assured returns of 12% a year with no risk.

## 4. Next steps

4.1 Share your business PAN and we will start onboarding.
""",
    },
    {
        "stem": "brochure-zero-fees-synthetic",
        "meta": {
            "title": "Dummy brochure: zero fees and instant settlement",
            "doc_type": "brochure",
            "product": "Payment Gateway",
            "owner": "meera.iyer@demo.paytm.example",
        },
        "body": """# Start accepting payments today

SYNTHETIC DEMO BROCHURE. Upload this under Documents → Add a document.

- Instant settlement 24x7 on every payment, even on bank holidays.
- Go live in 10 minutes, with zero charges on every payment mode.
- Domestic cards at just 2% MDR.
- Failed UPI payments are refunded in 7 working days.
""",
    },
]


def front(raw: str) -> tuple[dict, str]:
    if not raw.startswith("---"):
        return {}, raw
    end = raw.find("\n---", 3)
    meta: dict[str, str] = {}
    for ln in raw[3:end].strip().splitlines():
        if ":" in ln:
            k, v = ln.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, raw[end + 4:].lstrip("\n")


def to_html(meta: dict, body: str) -> str:
    who = html.escape(meta.get("merchant") or meta.get("institution") or "synthetic demo")
    out = [
        "<body style='font-family: sans-serif; font-size: 10.5pt; line-height: 1.45'>",
        f"<p style='font-size:8pt; color:#555'>{who} · synthetic demo document · not a real merchant or regulator file</p>",
    ]
    for blk in re.split(r"\n\s*\n", body.strip()):
        blk = blk.strip()
        if blk.startswith("# "):
            out.append(f"<h1 style='font-size:18pt; margin:0 0 8pt 0'>{html.escape(blk[2:])}</h1>")
        elif blk.startswith("## "):
            out.append(f"<h2 style='font-size:13pt; margin:14pt 0 4pt 0'>{html.escape(blk[3:])}</h2>")
        elif any(ln.strip().startswith("- ") for ln in blk.splitlines()):
            items = "".join(f"<li>{html.escape(ln.strip()[2:])}</li>" for ln in blk.splitlines() if ln.strip().startswith("- "))
            out.append(f"<ul style='margin:0 0 8pt 18pt'>{items}</ul>")
        else:
            out.append(f"<p style='margin:0 0 7pt 0'>{html.escape(blk)}</p>")
    out.append("</body>")
    return "".join(out)


def write_pdf(out: Path, meta: dict, body: str) -> int:
    story = pymupdf.Story(to_html(meta, body))
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
    return pymupdf.open(str(out)).page_count


def render_library_md(md: Path) -> None:
    SOURCE.mkdir(exist_ok=True)
    meta, body = front(md.read_text(encoding="utf-8"))
    out = LIB / (md.stem + ".pdf")
    pages = write_pdf(out, meta, body)
    (LIB / (md.stem + ".pdf.meta.json")).write_text(
        json.dumps({k: v for k, v in meta.items() if v}, indent=2) + "\n", encoding="utf-8"
    )
    dest = SOURCE / md.name
    if dest.exists():
        md.unlink()
    else:
        shutil.move(str(md), str(dest))
    print("library", out.name, pages, "page(s)")


def render_samples() -> None:
    SAMPLES.mkdir(exist_ok=True)
    for doc in SAMPLES_DOCS:
        out = SAMPLES / f"{doc['stem']}.pdf"
        pages = write_pdf(out, doc["meta"], doc["body"])
        (SAMPLES / f"{doc['stem']}.pdf.meta.json").write_text(json.dumps(doc["meta"], indent=2) + "\n", encoding="utf-8")
        print("samples", out.name, pages, "page(s)")


if __name__ == "__main__":
    if not (ROOT / "library").is_dir():
        print("run from the repo (library/ missing)", file=sys.stderr)
        sys.exit(1)
    for md in sorted(LIB.glob("*.md")):
        render_library_md(md)
    render_samples()
