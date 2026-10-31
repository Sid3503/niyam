"""Split a document into citable clauses with exact character offsets into the stored content.

A clause is a numbered clause ("3.2 ..."), a bullet, or a paragraph. Headings are not clauses; they feed the locator.
Offsets always index the stored content, so a finding's quote can be located verbatim and highlighted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_NUM = re.compile(r"^\s*(?:[-*]\s+)?(\d+(?:\.\d+)*)[.)]?\s+\S")
_HEAD = re.compile(r"^\s{0,3}#{1,6}\s+")
_LEAD = re.compile(r"^\s*(?:[-*]\s+)?(?:\d+(?:\.\d+)*[.)]?\s+)?")
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


@dataclass
class Clause:
    idx: int
    locator: str
    text: str
    start: int
    end: int


def parse_front_matter(raw: str) -> tuple[dict, str]:
    """Tiny `key: value` front matter between --- lines. Returns (meta, body)."""
    if not raw.startswith("---"):
        return {}, raw
    end = raw.find("\n---", 3)
    if end < 0:
        return {}, raw
    meta = {}
    for line in raw[3:end].strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"')
    body = raw[end + 4:].lstrip("\n")
    return meta, body


def segment(content: str) -> list[Clause]:
    clauses: list[Clause] = []
    para_no = 0
    pos = 0
    block_start = None
    block_lines: list[str] = []

    def flush(end_pos: int):
        nonlocal para_no, block_start, block_lines
        if block_start is None:
            return
        raw = "".join(block_lines)
        stripped = raw.strip()
        if stripped:
            lead = len(raw) - len(raw.lstrip())
            start = block_start + lead
            end = start + len(stripped)
            m = _NUM.match(stripped)
            if m:
                loc = f"§{m.group(1)}"
            else:
                para_no += 1
                loc = f"para {para_no}"
            clauses.append(Clause(len(clauses), loc, stripped, start, end))
        block_start, block_lines = None, []

    for line in content.splitlines(keepends=True):
        s = line.strip()
        if not s:
            flush(pos)
        elif _HEAD.match(line):
            flush(pos)
        elif _NUM.match(line) or re.match(r"^\s*[-*]\s+", line):
            flush(pos)
            block_start, block_lines = pos, [line]
        else:
            if block_start is None:
                block_start = pos
            block_lines.append(line)
        pos += len(line)
    flush(pos)
    return clauses


def sentences(clause: Clause) -> list[tuple[int, int, str]]:
    """Sentence spans (absolute offsets) inside a clause, so a quote can be the one offending sentence."""
    out, last = [], 0
    for m in _SENT.finditer(clause.text):
        out.append((last, m.start()))
        last = m.end()
    out.append((last, len(clause.text)))
    res = []
    for a, b in out:
        seg = clause.text[a:b]
        if not seg.strip():
            continue
        if a == 0:                                  # the clause number / bullet is a locator, not part of the quoted sentence
            m = _LEAD.match(seg)
            if m:
                a += m.end()
        res.append((clause.start + a, clause.start + b, clause.text[a:b]))
    return res
