#!/usr/bin/env python3
"""Validate Niyam rule cards (rules/cards/*.json) against their source documents.

Run from anywhere:  python3 -I rules/validate.py [--stamp] [--as-of YYYY-MM-DD] [card.json ...]

What it checks (stdlib only, no network):
  1. Schema: required fields, types, closed vocabularies (see docs/NIYAM-END-TO-END.md section 5).
  2. Invariants: only a human can make a card `active` (needs approved_by + approved_at);
     ids are unique; Tier A / A+B cards carry a non-empty check.config.
  3. Provenance: source.file exists and its sha256 matches the stored hash.
  4. Citations: every source.quotes[] entry is an EXACT substring of the source text after
     whitespace normalisation (nothing else is normalised: not quotes, not dashes, not case).
     A quote that appears more than once is flagged, because it is not a precise citation.
  5. Dates: effective_from is reported against --as-of (default today) so a card that is
     not yet enforceable is labelled, not silently treated as live.

--stamp  fills in a missing/empty source.sha256 from the file on disk (never overwrites a
         non-empty hash: a mismatch is an error you must look at).

The validator proves the quote exists in the stored file. It does NOT prove the obligation is
a correct reading of the quote, and it does not replace the compliance officer's approval.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHECK_TYPES = {"timeline_consistency", "must_contain", "must_not_claim", "ordering",
               "fact_consistency", "escalation_required", "action_conformance"}
TIERS = {"A", "B", "A+B"}
SEVERITIES = {"low", "medium", "high", "critical"}
STATUSES = {"draft", "in_review", "active", "superseded", "retired", "rejected"}
TEXT_BASES = {"native", "ocr"}
PROVENANCE = {"official", "official_html_extract", "mirror", "user_downloaded"}
REQUIRED = ["id", "version", "title", "obligation", "source", "check", "scope", "severity",
            "owner", "confidence_threshold", "evidence_required", "effective_from", "status"]
ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(-[A-Z0-9]+)+$")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


_text_cache: dict[str, str] = {}


def pdf_text(path: str) -> str:
    if shutil.which("pdftotext"):
        return subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True).stdout
    helper = os.path.join(ROOT, "rules", "tools", "bin", "pdftxt")
    src = os.path.join(ROOT, "rules", "tools", "pdftxt.swift")
    if not os.path.exists(helper) and shutil.which("swiftc") and os.path.exists(src):
        os.makedirs(os.path.dirname(helper), exist_ok=True)
        subprocess.run(["swiftc", "-O", "-o", helper, src], capture_output=True)
    if os.path.exists(helper):
        return subprocess.run([helper, path], capture_output=True, text=True).stdout
    raise RuntimeError("no PDF text extractor: install poppler (pdftotext) or Xcode command line tools")


def source_text(path: str) -> str:
    if path in _text_cache:
        return _text_cache[path]
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        t = pdf_text(path)
    else:
        t = open(path, encoding="utf-8", errors="ignore").read()
        if ext in (".html", ".htm"):
            t = re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S)
            t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    _text_cache[path] = norm(t)
    return _text_cache[path]


def validate_card(path: str, card: dict, as_of: dt.date, stamp: bool, seen_ids: set):
    errs, warns, info = [], [], []
    for f in REQUIRED:
        if f not in card:
            errs.append(f"missing field: {f}")
    if errs:
        return errs, warns, info
    cid = card["id"]
    if not ID_RE.match(cid):
        errs.append(f"id {cid!r} must be UPPERCASE with hyphens, e.g. RBI-TAT-UPI-TRANSFER")
    if cid in seen_ids:
        errs.append(f"duplicate id {cid}")
    seen_ids.add(cid)
    if os.path.splitext(os.path.basename(path))[0] != f"{cid}.v{card['version']}":
        warns.append(f"file name should be {cid}.v{card['version']}.json")
    if not isinstance(card["version"], int) or card["version"] < 1:
        errs.append("version must be an integer >= 1")
    if len(card["title"]) > 80:
        errs.append("title longer than 80 chars")
    if card["severity"] not in SEVERITIES:
        errs.append(f"severity {card['severity']!r} not in {sorted(SEVERITIES)}")
    if card["status"] not in STATUSES:
        errs.append(f"status {card['status']!r} not in {sorted(STATUSES)}")
    ct = card["confidence_threshold"]
    if not isinstance(ct, (int, float)) or not 0 <= ct <= 1:
        errs.append("confidence_threshold must be a number in [0,1]")
    chk = card["check"]
    if chk.get("type") not in CHECK_TYPES:
        errs.append(f"check.type {chk.get('type')!r} not in closed vocabulary")
    if chk.get("tier") not in TIERS:
        errs.append(f"check.tier {chk.get('tier')!r} not in {sorted(TIERS)}")
    if chk.get("tier") in ("A", "A+B") and not chk.get("config"):
        errs.append("Tier A / A+B needs a non-empty check.config (deterministic parameters)")
    sc = card["scope"]
    if not sc.get("surfaces"):
        errs.append("scope.surfaces must list at least one surface")
    try:
        eff = dt.date.fromisoformat(card["effective_from"])
        if eff > as_of:
            info.append(f"NOT YET ENFORCEABLE as of {as_of} (effective_from {eff})")
    except ValueError:
        errs.append("effective_from must be an ISO date")
    # invariant: only a human activates a rule
    if card["status"] == "active":
        if not card.get("approved_by") or not card.get("approved_at"):
            errs.append("status=active requires approved_by and approved_at (a named human)")
    else:
        if card.get("approved_by"):
            warns.append("approved_by is set but status is not active")
    if card["status"] in ("draft", "in_review") and card["owner"] in ("", None):
        errs.append("owner must be set (use 'unassigned' for a draft)")
    # provenance + citations
    src = card["source"]
    for f in ("regulator", "document", "file", "text_basis", "provenance", "quotes"):
        if f not in src:
            errs.append(f"source.{f} missing")
    if errs:
        return errs, warns, info
    if src["text_basis"] not in TEXT_BASES:
        errs.append(f"source.text_basis must be one of {sorted(TEXT_BASES)}")
    if src["provenance"] not in PROVENANCE:
        errs.append(f"source.provenance must be one of {sorted(PROVENANCE)}")
    if src["provenance"] in ("mirror", "user_downloaded"):
        warns.append(f"source provenance is '{src['provenance']}': replace with the official copy before activation")
    if src["text_basis"] == "ocr":
        warns.append("quote read from OCR text: confirm against the page image before activation")
    fpath = os.path.join(ROOT, src["file"])
    if not os.path.exists(fpath):
        errs.append(f"source.file not found: {src['file']}")
        return errs, warns, info
    actual = sha256_file(fpath)
    declared = src.get("sha256", "")
    if not declared:
        if stamp:
            card["source"]["sha256"] = actual
            info.append("stamped source.sha256")
        else:
            errs.append("source.sha256 is empty (run with --stamp)")
    elif declared != actual:
        errs.append(f"source.sha256 mismatch: card {declared[:12]}.. vs file {actual[:12]}..")
    text = source_text(fpath)
    if not src["quotes"]:
        errs.append("source.quotes must contain at least one verbatim quote")
    # numeric cross-check: numbers the check relies on must appear in the cited quotes
    cfg = chk.get("config") or {}
    joined = " ".join(norm(q) for q in src["quotes"])
    if chk.get("type") == "timeline_consistency" and isinstance(cfg.get("deadline_days"), int):
        n_days = cfg["deadline_days"]
        if not re.search(rf"T\s*\+\s*{n_days}\b", joined):
            errs.append(f"config.deadline_days={n_days} but no 'T + {n_days}' appears in the cited quotes")
    if isinstance(cfg.get("compensation_per_day_inr"), int):
        amt = cfg["compensation_per_day_inr"]
        if not re.search(rf"₹\s*{amt}\b", joined):
            errs.append(f"config.compensation_per_day_inr={amt} but no '₹{amt}' appears in the cited quotes")
    for i, q in enumerate(src["quotes"]):
        nq = norm(q)
        n = text.count(nq)
        if n == 0:
            errs.append(f"quote[{i}] is NOT an exact substring of {src['file']}: {nq[:90]!r}...")
        elif n > 1:
            warns.append(f"quote[{i}] occurs {n} times in the source: not a precise citation")
    return errs, warns, info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cards", nargs="*")
    ap.add_argument("--stamp", action="store_true")
    ap.add_argument("--as-of", default=dt.date.today().isoformat())
    a = ap.parse_args()
    as_of = dt.date.fromisoformat(a.as_of)
    paths = a.cards or sorted(glob.glob(os.path.join(ROOT, "rules", "cards", "*.json")))
    if not paths:
        print("no cards found")
        return 1
    seen: set = set()
    total_err = 0
    for p in paths:
        try:
            card = json.load(open(p, encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {os.path.basename(p)}: invalid JSON: {e}")
            total_err += 1
            continue
        errs, warns, info = validate_card(p, card, as_of, a.stamp, seen)
        if a.stamp and any("stamped" in i for i in info):
            json.dump(card, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            open(p, "a", encoding="utf-8").write("\n")
        status = "FAIL" if errs else "ok  "
        print(f"{status} {card.get('id', os.path.basename(p)):34s} status={card.get('status')}")
        for m in errs:
            print(f"       ERROR {m}")
        for m in warns:
            print(f"       warn  {m}")
        for m in info:
            print(f"       info  {m}")
        total_err += len(errs)
    print(f"\n{len(paths)} cards, {total_err} errors (as of {as_of})")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main())
