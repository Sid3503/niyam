#!/usr/bin/env python3
"""OCR scanned PDFs (no text layer) into `_ocr/<stem>.ocr.txt` sidecars next to the PDF.  macOS only (Apple Vision).

    python tools/make_ocr_sidecars.py /path/to/regulations [--dry-run]

Sidecars are MACHINE-READ and may contain errors; the PDF stays authoritative. Ingestion marks such documents text_basis=ocr.
On Linux/Docker use Tesseract instead (see docs/PLATFORM-BUILD.md); the sidecar format is the same.
"""
import subprocess, sys
from pathlib import Path
import pymupdf

root = Path(sys.argv[1])
dry = "--dry-run" in sys.argv
here = Path(__file__).parent
binary = here / "bin" / "ocr_vision"
if not dry and not binary.exists():
    binary.parent.mkdir(exist_ok=True)
    subprocess.run(["swiftc", "-O", "-o", str(binary), str(here / "ocr_vision.swift")], check=True, capture_output=True)
done = skipped = 0
for pdf in sorted(root.rglob("*.pdf")):
    if "_ocr" in pdf.parts:
        continue
    try:
        with pymupdf.open(pdf) as d:
            chars = sum(len(p.get_text().strip()) for p in d)
            pages = d.page_count
    except Exception as e:
        print(f"skip (unreadable) {pdf.name}: {e}"); continue
    side = pdf.parent / "_ocr" / f"{pdf.stem}.ocr.txt"
    if chars >= 200 or side.exists():
        skipped += 1; continue
    print(f"OCR {pages:>3}p  {pdf.relative_to(root)}", flush=True)
    if dry:
        continue
    out = subprocess.run([str(binary), str(pdf)], capture_output=True, text=True, timeout=1800).stdout
    side.parent.mkdir(exist_ok=True)
    side.write_text(f"# OCR TEXT (Apple Vision, machine-read, may contain errors). The PDF is authoritative.\n# source: {pdf.name}\n\n{out}", encoding="utf-8")
    done += 1
print(f"done={done} skipped={skipped}")
