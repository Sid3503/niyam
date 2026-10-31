"""Timeline parser: extracts the reversal / refund timelines an agent PROMISES.

Output is a list of :class:`Promise` normalised to calendar days from T (the transaction
date). Lexicons and regexes live in the card (``check.config.matchers.timeline`` and the
cue lists next to it) so compliance can edit them; this module is only the mechanics.

Normalisation rules (see docs/ENGINE.md):
  * 'today / tonight / same day / aaj raat / आज' -> 0 days (kind ``same_day``)
  * 'tomorrow / kal tak / कल तक / next day / 24 hours / T+1' -> 1 day
  * 'N days / din / दिन', 'N-M days' (the MAX is used), 'N weeks / hafte' (7N)
  * hours: <= 12h counts as same-day (0), otherwise ceil(h/24)
  * 'working / business days' keep ``working=True``; the judge converts to a calendar
    range because RBI's T is a calendar date (worst case n + 2*ceil(n/5)).
  * relative words ('tomorrow') are relative to the time the agent writes, which the
    engine does not know; they are read as T+offset (documented limitation).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from .common import Segments, any_match, rx


@dataclass
class Promise:
    start: int
    end: int
    days: float | None          # max calendar-day equivalent (nominal n for working days); None = vague
    min_days: float
    kind: str                   # same_day | next_day | duration | tplus | vague
    working: bool
    label: str
    clause: tuple[int, int]
    sentence: tuple[int, int]
    flags: set[str] = field(default_factory=set)   # negated hedged conditional regulatory
    ignore: str | None = None   # reason this promise is not evaluated

    @property
    def unconditional(self) -> bool:
        return not ({"hedged", "conditional"} & self.flags)


def _build_duration(tl: dict) -> tuple[re.Pattern[str], dict[str, tuple[str, float]]]:
    words = sorted(tl["number_words"], key=len, reverse=True)
    num = r"(?:\d+(?:\.\d+)?|" + "|".join(re.escape(w) for w in words) + ")"
    unit_map: dict[str, tuple[str, float]] = {}
    mult = {"days": 1.0, "weeks": 7.0, "months": 30.0, "hours": 1.0, "minutes": 1.0}
    for kind, forms in tl["units"].items():
        for u in forms:
            unit_map[u.lower()] = (kind, mult[kind])
    units = "|".join(re.escape(u) for u in sorted(unit_map, key=len, reverse=True))
    wd = "|".join(re.escape(w) for w in sorted(tl["working_markers"] + tl.get("calendar_markers", []), key=len, reverse=True))
    sep = "|".join(re.escape(s) for s in sorted(tl["range_separators"], key=len, reverse=True))
    pre = "|".join(sorted(tl["pre_words"], key=len, reverse=True))   # regex fragments
    pat = (
        r"(?<![\w.+])(?:(?P<pre>" + pre + r")\s+)?(?P<n1>" + num + r")"
        r"(?:\s*(?:" + sep + r")\s*(?P<n2>" + num + r"))?"
        r"\s*(?P<wd>(?:" + wd + r")\s*)?(?P<unit>" + units + r")(?![a-zऀ-ॿ])"
    )
    return re.compile(pat, re.IGNORECASE), unit_map


def _num(tok: str, words: dict[str, float]) -> float:
    tok = tok.lower()
    if tok in words:
        return float(words[tok])
    return float(tok)


def extract_promises(f: str, seg: Segments, m: dict) -> list[Promise]:
    tl = m["timeline"]
    cands: list[tuple[int, int, dict]] = []

    for item in tl["fixed"]:
        for mt in rx(item["regex"]).finditer(f):
            if mt.end() > mt.start():
                cands.append((mt.start(), mt.end(), {
                    "days": item.get("days"), "min": item.get("min_days", item.get("days") or 0),
                    "kind": item["kind"], "working": bool(item.get("working")), "label": item["label"]}))

    for mt in rx(tl["tplus"]).finditer(f):
        n = float(mt.group("n"))
        cands.append((mt.start(), mt.end(), {"days": n, "min": n, "kind": "tplus", "working": False,
                                             "label": f"T+{mt.group('n')}"}))

    dur, unit_map = _build_duration(tl)
    words = {k.lower(): v for k, v in tl["number_words"].items()}
    skip_before = tl.get("skip_before", [])
    skip_after = tl.get("skip_after", [])
    for mt in dur.finditer(f):
        n1_tok, n2_tok = mt.group("n1"), mt.group("n2")
        if n1_tok.lower() in ("a", "an") and not mt.group("pre"):
            continue
        n1 = _num(n1_tok, words)
        n2 = _num(n2_tok, words) if n2_tok else n1
        lo_n, hi_n = min(n1, n2), max(n1, n2)
        ukind, umult = unit_map[mt.group("unit").lower()]
        start = mt.start()
        window = f[max(0, start - 28):start]
        if any_match([p + r"\s*$" for p in skip_before], window):
            continue
        after = f[mt.end():mt.end() + 24]
        if any_match([r"^\s*" + p for p in skip_after], after):
            continue
        wd_tok = (mt.group("wd") or "").strip().lower()
        working = bool(wd_tok) and wd_tok not in [c.lower() for c in tl.get("calendar_markers", [])]
        if ukind in ("hours", "minutes"):
            def h2d(h: float) -> float:
                return 0.0 if h <= 12 else float(math.ceil(h / 24))
            scale = 1 / 60 if ukind == "minutes" else 1.0
            lo, hi = h2d(lo_n * scale), h2d(hi_n * scale)
            kind = "same_day" if hi == 0 else "duration"
            working = False
        else:
            lo, hi = lo_n * umult, hi_n * umult
            kind = "duration"
        label = mt.group(0).strip()
        cands.append((start, mt.end(), {"days": hi, "min": lo, "kind": kind, "working": working, "label": label}))

    cands.sort(key=lambda c: (c[0], -(c[1] - c[0])))
    kept: list[tuple[int, int, dict]] = []
    for c in cands:
        if kept and c[0] < kept[-1][1]:
            continue
        kept.append(c)

    out: list[Promise] = []
    for a, b, d in kept:
        out.append(Promise(
            start=a, end=b, days=d["days"], min_days=float(d["min"] or 0), kind=d["kind"],
            working=d["working"], label=d["label"], clause=seg.clause_at(a), sentence=seg.sentence_at(a)))
    return out


def annotate(promises: list[Promise], f: str, m: dict) -> None:
    """Attach negation / hedge / conditional / regulatory flags and ignore reasons."""
    for p in promises:
        ca, cb = p.clause
        sa, sb = p.sentence
        before = f[ca:p.start]
        # --- negation: a cue shortly before the promise, not across an 'and', not an upper bound.
        # 'wide' cues (cannot / unable / no guarantee) reach 60 chars; plain 'not / nahi' only 18.
        guarded = any_match(m["negation_guard"], before[-45:]) is not None

        def _cut(w: str) -> str:
            c = max(w.rfind(" and "), w.rfind(" aur "), w.rfind(" \u0914\u0930 "))
            return w[c + 5:] if c >= 0 else w

        if not guarded:
            if any_match(m["negation"], _cut(before[-60:])) or any_match(m["negation_near"], _cut(before[-18:])):
                p.flags.add("negated")
        after = f[p.end:min(cb, p.end + 28)]
        if any_match(m["negation_after"], after):
            p.flags.add("negated")
        sent = f[sa:sb]
        if any_match(m["hedges"], f[ca:cb]):
            p.flags.add("hedged")
        if any_match(m["conditional"], sent):
            p.flags.add("conditional")
        if any_match(m["regulatory_cues"], sent):
            p.flags.add("regulatory")
        if "negated" in p.flags:
            p.ignore = "negated (agent disclaims this timeline)"
        elif p.kind in ("same_day", "next_day") and any_match(m.get("initiation_cues", []), f[sa:p.start]):
            p.ignore = "timeline is for initiating/raising something, not for the money coming back"
        elif "conditional" in p.flags and any_match(m["escalation_cues"], sent):
            p.ignore = "escalation threshold, not a reversal promise"
