"""Shared helpers for the Tier A engine: text folding, segmentation, verdict building.

STDLIB ONLY. Everything here is deterministic and offset preserving: the folded text
has exactly the same length as the input, so a span found in the folded text indexes the
original text and ``text[start:end]`` is always a verbatim quote.
"""
from __future__ import annotations

import functools
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable

# ---------------------------------------------------------------- folding

_TRANS: dict[int, str] = {
    ord("’"): "'", ord("‘"): "'", ord("“"): '"', ord("”"): '"',
    ord("–"): "-", ord("—"): "-", ord(" "): " ", ord("​"): " ",
    ord("﻿"): " ", ord("‑"): "-", ord("−"): "-",
}
for _i, _c in enumerate("०१२३४५६७८९"):
    _TRANS[ord(_c)] = str(_i)
# precomposed nukta letters -> base consonant (same length). Matchers treat U+093C as optional.
for _cp, _base in {0x958: 0x915, 0x959: 0x916, 0x95A: 0x917, 0x95B: 0x91C,
                   0x95C: 0x921, 0x95D: 0x922, 0x95E: 0x92B, 0x95F: 0x92F}.items():
    _TRANS[_cp] = chr(_base)


def is_blank(text: str) -> bool:
    """True for empty text or text made only of whitespace / zero-width / control characters."""
    return all(ch.isspace() or unicodedata.category(ch) in ("Cf", "Cc") for ch in text)


def fold(text: str) -> str:
    """Length-preserving normalisation: lower-case, unify quotes/dashes/digits."""
    t = text.translate(_TRANS)
    low = t.lower()
    if len(low) == len(t):
        return low
    return "".join(c.lower() if len(c.lower()) == 1 else c for c in t)


@functools.lru_cache(maxsize=4096)
def rx(pattern: str, flags: int = re.IGNORECASE) -> re.Pattern[str]:
    return re.compile(pattern, flags)


def compile_list(patterns: Iterable[str]) -> list[re.Pattern[str]]:
    return [rx(p) for p in patterns]


def any_match(patterns: Iterable[str], s: str, pos: int = 0, endpos: int | None = None):
    """First match across a list of patterns (earliest start wins)."""
    best = None
    for p in patterns:
        m = rx(p).search(s, pos, len(s) if endpos is None else endpos)
        if m and (best is None or m.start() < best.start()):
            best = m
    return best


def all_matches(patterns: Iterable[str], s: str) -> list[re.Match[str]]:
    out: list[re.Match[str]] = []
    for p in patterns:
        out.extend(rx(p).finditer(s))
    out.sort(key=lambda m: (m.start(), -(m.end() - m.start())))
    return out


# ---------------------------------------------------------------- segmentation

_SENT = re.compile(r"(?<!\brs)(?<!\bno)(?<!\binr)[.!?।]+(?=\s|$)|\n+|;", re.IGNORECASE)
_CLAUSE = re.compile(
    r",(?=\s)|\s(?:but|however|though|although|while|whereas|lekin|magar|parantu|kintu|"
    r"लेकिन|परंतु|मगर|जबकि)\s",
    re.IGNORECASE,
)


def _trim(s: str, a: int, b: int) -> tuple[int, int]:
    while a < b and s[a].isspace():
        a += 1
    while b > a and s[b - 1].isspace():
        b -= 1
    return a, b


class Segments:
    """Sentence and clause spans over a (folded) text."""

    def __init__(self, f: str):
        self.f = f
        sents: list[tuple[int, int]] = []
        start = 0
        for m in _SENT.finditer(f):
            a, b = _trim(f, start, m.end())
            if b > a:
                sents.append((a, b))
            start = m.end()
        a, b = _trim(f, start, len(f))
        if b > a:
            sents.append((a, b))
        self.sentences = sents
        clauses: list[tuple[int, int]] = []
        for sa, sb in sents:
            cs = sa
            seg = f[sa:sb]
            for m in _CLAUSE.finditer(seg):
                a, b = _trim(f, cs, sa + m.start())
                if b > a:
                    clauses.append((a, b))
                cs = sa + m.end()
            a, b = _trim(f, cs, sb)
            if b > a:
                clauses.append((a, b))
        self.clauses = clauses

    def sentence_index(self, pos: int) -> int:
        for i, (a, b) in enumerate(self.sentences):
            if a <= pos < b or (pos == b and i == len(self.sentences) - 1):
                return i
        return max(0, len(self.sentences) - 1)

    def sentence_at(self, pos: int) -> tuple[int, int]:
        if not self.sentences:
            return (0, len(self.f))
        return self.sentences[self.sentence_index(pos)]

    def clause_at(self, pos: int) -> tuple[int, int]:
        for a, b in self.clauses:
            if a <= pos < b:
                return (a, b)
        return self.sentence_at(pos)

    def prev_sentence(self, pos: int) -> tuple[int, int] | None:
        i = self.sentence_index(pos)
        return self.sentences[i - 1] if i > 0 else None


# ---------------------------------------------------------------- facts helpers

def num_fact(facts: dict | None, key: str) -> float | None:
    v = (facts or {}).get(key)
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.strip())
        except ValueError:
            return None
    return None


def str_fact(facts: dict | None, key: str) -> str | None:
    v = (facts or {}).get(key)
    return v.strip().lower() if isinstance(v, str) and v.strip() else None


def bool_fact(facts: dict | None, key: str):
    v = (facts or {}).get(key)
    return v if isinstance(v, bool) else None


def matchers(card: dict) -> dict:
    return (card.get("check", {}).get("config", {}) or {}).get("matchers") or {}


# ---------------------------------------------------------------- findings / verdicts

@dataclass
class Finding:
    level: str                    # fail | review | ok | info
    name: str
    detail: str
    span: tuple[int, int] | None = None   # span of the offending phrase / clause in the input
    prio: int = 0


def check_entry(name: str, result: str, detail: str) -> dict:
    return {"name": name, "result": result, "detail": detail}


@dataclass
class Ctx:
    card: dict
    text: str
    f: str
    facts: dict
    seg: Segments
    m: dict = field(default_factory=dict)


def source_block(card: dict) -> dict:
    s = card.get("source", {}) or {}
    q = (s.get("quotes") or [None])[0]
    return {"document": s.get("document"), "reference": s.get("reference"),
            "locator": s.get("locator"), "file": s.get("file"), "quote": q}


def make_verdict(card: dict, verdict: str, *, tier: str = "A", confidence: float,
                 reason: str, quote: str | None = None, span: tuple[int, int] | None = None,
                 checks: list[dict] | None = None) -> dict:
    return {
        "rule_id": card["id"],
        "rule_version": card["version"],
        "rule_status": card["status"],
        "verdict": verdict,
        "tier": tier,
        "confidence": round(float(confidence), 2),
        "quote": quote,
        "span": [span[0], span[1]] if span else None,
        "reason": reason,
        "checks": checks or [],
        "source": source_block(card),
    }


def tidy_span(text: str, span: tuple[int, int], max_len: int = 240) -> tuple[int, int]:
    a, b = span
    a = max(0, a)
    b = min(len(text), b)
    while a < b and text[a].isspace():
        a += 1
    while b > a and text[b - 1].isspace():
        b -= 1
    if b - a > max_len:
        b = a + max_len
    return a, b


def fail_from_span(ctx: Ctx, span: tuple[int, int], *, reason: str, checks: list[dict],
                   confidence: float = 0.95, tier: str = "A") -> dict:
    a, b = tidy_span(ctx.text, span)
    return make_verdict(ctx.card, "fail", tier=tier, confidence=confidence, reason=reason,
                        quote=ctx.text[a:b], span=(a, b), checks=checks)


def anchor_span(ctx: Ctx, preferred: Iterable[tuple[int, int]] | None = None) -> tuple[int, int]:
    """Span to quote when a failure is an OMISSION (nothing offending to quote).

    Policy: the first sentence that talks about the topic (``preferred`` spans), else the
    first sentence of the text, else the whole trimmed text."""
    for sp in preferred or []:
        return ctx.seg.sentence_at(sp[0])
    if ctx.seg.sentences:
        return ctx.seg.sentences[0]
    return tidy_span(ctx.text, (0, len(ctx.text)))


def finalize(text: str, v: dict) -> dict:
    """Hard invariants. Downgrades (never upgrades) a verdict that would break them."""
    if v["verdict"] == "fail":
        q, sp = v.get("quote"), v.get("span")
        ok = (isinstance(q, str) and q != "" and isinstance(sp, list) and len(sp) == 2
              and 0 <= sp[0] < sp[1] <= len(text) and text[sp[0]:sp[1]] == q)
        if not ok:
            v["reason"] = "[invariant guard: fail had no verbatim quote] " + v["reason"]
            v["verdict"] = "review"
            v["quote"], v["span"] = None, None
            v["confidence"] = min(v["confidence"], 0.5)
    if v["verdict"] in ("pass", "fail") and is_blank(text):
        v["verdict"] = "review"
        v["reason"] = "empty text cannot pass"
        v["confidence"] = 1.0
    return v
