"""Blocks -> citable units (heading | paragraph | table_row | list_item) with a best-effort locator.

A unit is the smallest span a rule card can cite. Rules of the road:
- never merge across a numbered-paragraph boundary, never split inside a sentence unless a unit exceeds MAX_CHARS;
- a table row is always its own unit;
- the locator is best-effort ("para 10(i)", "p.4", "table row"), the verbatim text is the evidence.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass

from niyam.kb.extract import Block

MAX_CHARS = 1400
NS = uuid.UUID("5a1b6c0e-4f4e-4d6e-9b5e-6e1a8f0c2b11")

LABEL = re.compile(r"^\s*(?P<label>(?:\d{1,3}(?:\.\d{1,3}){0,3}\.?)|(?:\([a-z]{1,4}\))|(?:\([ivxlc]{1,6}\))|(?:[A-Z]\.))\s+\S")
NUMERIC = re.compile(r"^\d{1,3}(?:\.\d{1,3}){0,3}\.?$")
HEADING = re.compile(
    r"^(?:chapter\s+[ivxlc\d]+|part\s+[ivxlc\d]+|annex(?:ure)?\s+[ivxlc\d]+|schedule\s+[ivxlc\d]+|section\s+\d+|\d{1,3}(?:\.\d{1,3}){0,2}\.?\s+[A-Z][^.!?]{2,90})\b",
    re.I,
)
SENT_SPLIT = re.compile(r"(?<=[.;:])\s+(?=[A-Z0-9(“\"'])")


@dataclass
class Unit:
    ordinal: int
    page: int | None
    kind: str
    locator: str | None
    heading_path: str | None
    text: str
    text_sha256: str
    id: uuid.UUID


def _is_heading(t: str) -> bool:
    if len(t) > 110 or t.endswith((".", ";", ",")) and not NUMERIC.match(t.split(" ")[0]):
        return False
    if len(t) < 3:
        return False
    if HEADING.match(t):
        return True
    letters = [c for c in t if c.isalpha()]
    return bool(letters) and len(t) <= 80 and sum(c.isupper() for c in letters) / len(letters) > 0.85 and len(t.split()) <= 12


def _split_long(t: str) -> list[str]:
    if len(t) <= MAX_CHARS:
        return [t]
    sents = SENT_SPLIT.split(t)
    out, cur = [], ""
    for s in sents:
        if cur and len(cur) + 1 + len(s) > MAX_CHARS:
            out.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        out.append(cur)
    # a single run-on sentence longer than the cap: hard-split on whitespace
    final = []
    for piece in out:
        while len(piece) > MAX_CHARS * 1.5:
            cut = piece.rfind(" ", 0, MAX_CHARS)
            cut = cut if cut > 200 else MAX_CHARS
            final.append(piece[:cut])
            piece = piece[cut:].lstrip()
        final.append(piece)
    return final


def build_units(blocks: list[Block], doc_sha256: str) -> list[Unit]:
    units: list[Unit] = []
    headings: list[str] = []
    last_numeric: str | None = None
    for b in blocks:
        t = b.text.strip()
        if not t or re.fullmatch(r"[\d\s.\-–|]+", t) and len(t) < 6:   # bare page numbers
            continue
        if b.kind == "table_row":
            kind, loc = "table_row", f"p.{b.page} table row" if b.page else "table row"
            pieces = _split_long(t)
        else:
            kind, loc = "paragraph", None
            if _is_heading(t):
                headings.append(t[:120])
                headings[:] = headings[-3:]
                kind = "heading"
            m = LABEL.match(t)
            if m and kind != "heading":
                label = m.group("label").rstrip(".")
                if NUMERIC.match(m.group("label")):
                    last_numeric = label
                    loc = f"para {label}"
                else:
                    loc = f"para {last_numeric}{label}" if last_numeric else f"para {label}"
                    kind = "list_item"
            elif kind == "heading":
                hm = LABEL.match(t)
                if hm and NUMERIC.match(hm.group("label")):
                    last_numeric = hm.group("label").rstrip(".")
                    loc = f"para {last_numeric}"
            if loc is None and b.page:
                loc = f"p.{b.page}"
            pieces = _split_long(t)
        for p in pieces:
            o = len(units)
            units.append(
                Unit(
                    ordinal=o,
                    page=b.page,
                    kind=kind,
                    locator=loc,
                    heading_path=" > ".join(headings[-2:]) if headings and kind != "heading" else (" > ".join(headings[-3:-1]) or None),
                    text=p,
                    text_sha256=hashlib.sha256(p.encode("utf-8")).hexdigest(),
                    id=uuid.uuid5(NS, f"{doc_sha256}:{o}"),
                )
            )
    return units
