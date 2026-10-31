"""Tier A document checks against Paytm-controlled product facts (synthetic in the demo).

Each check returns Hit objects. A Hit always names the fact it was judged against, the exact sentence (quote, offsets into the
document), and a status from the single vocabulary: current | outdated | missing | contradiction | review.
Rules of thumb enforced here:
- a claim we cannot verify is `review`, never `current`;
- `current` is only emitted when the clause's number or term matches the approved fact and carries a quote.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache

from niyam.config import get_settings
from niyam.review.segment import Clause, sentences

_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "twelve": 12, "twenty four": 24, "ten": 10}
_NUM = r"(?P<n>\d+(?:\.\d+)?|one|two|three|four|five|six|ten|twelve|twenty[- ]four)"
_SETTLE_WORD = re.compile(r"\b(settle\w*|payouts?|pay[- ]outs?)\b", re.I)
_TIME = re.compile(rf"\b(?:within|in|by|under)\s+{_NUM}\s*(?P<u>hours?|hrs?|minutes?|mins?|business days?|working days?|days?)\b", re.I)
_TPLUS = re.compile(r"\bT\s*\+\s*(\d)\b", re.I)
_INSTANT = re.compile(r"\b(instant(ly)?|real[- ]time|immediate(ly)?|same[- ]day|24\s*[x×*]\s*7|round[- ]the[- ]clock)\b", re.I)
_GUAR = re.compile(r"\b(guarantee[sd]?|assured|promise[sd]?|100\s*%|certain(ly)?|always)\b", re.I)
_PCT = re.compile(r"(?P<p>\d+(?:\.\d+)?)\s*%")
_FEE_CTX = re.compile(r"\b(mdr|fee|fees|charge[sd]?|charges|rate|commission|pricing|cost)\b", re.I)
_CARD = re.compile(r"\b(cards?|credit|debit|rupay|visa|mastercard)\b", re.I)
_UPI = re.compile(r"\bupi\b", re.I)
_NOT_FEE = re.compile(r"\b(returns?|interest|yield|profit|growth|p\.a\.|per annum)\b", re.I)
_ZERO_FEE = re.compile(r"\b(zero|no|nil|without any)\s+(hidden\s+)?(charges?|fees?|costs?|mdr)\b|\bfree of (cost|charge)\b|\b0\s*%\s*(mdr|fee|charges?)\b", re.I)
_ALL_MODES = re.compile(r"\b(every|all|any|each)\b[^.]{0,40}\b(payment mode|mode|modes|method|methods|transaction|transactions)\b", re.I)
_NO_KYC = re.compile(r"\b(no|without|zero|skip(ped)?)\s+(kyc|documents?|documentation|paperwork)\b|\bkyc[- ]free\b|\bno[- ]kyc\b", re.I)
_APPROVAL_G = re.compile(r"\b(guaranteed|assured|certain|100\s*%)\s+(merchant\s+)?(approval|onboarding|activation|go[- ]live)\b|\b(approval|onboarding|activation)\s+(is\s+)?guaranteed\b|\binstant\s+(approval|onboarding|activation)\b", re.I)
_GO_LIVE_FAST = re.compile(rf"\b(go live|live|activated?|onboarded|approved?)\b[^.]{{0,40}}\b(?:within|in)\s+{_NUM}\s*(?P<u>hours?|hrs?|minutes?|mins?)\b", re.I)
_NO_HOLD = re.compile(r"\b(never|no|without)\s+(hold|holds|delay|delays|held|withhold)\w*\b|\bsettlements?\s+(are\s+)?(never|not)\s+(held|delayed)\b|\bunconditional\w*\s+settle", re.I)
_SUPERSEDED_WORD = re.compile(r"\b(earlier|old|legacy|previous)\b", re.I)


@dataclass
class Hit:
    status: str
    severity: str
    confidence: float
    reason: str
    fact_id: str
    quote: str
    span: tuple[int, int]
    clause_idx: int
    locator: str
    claim: str
    extra: dict = field(default_factory=dict)


@lru_cache
def load_facts() -> dict:
    p = get_settings().rules_path.parent / "product-facts.json"
    raw = p.read_bytes()
    data = json.loads(raw)
    data["sha256"] = hashlib.sha256(raw).hexdigest()
    data["by_id"] = {f["id"]: f for f in data["facts"]}
    return data


def facts_fingerprint() -> str:
    return load_facts()["sha256"]


def _num(tok: str) -> float:
    tok = tok.lower().replace("-", " ")
    return float(_WORDS.get(tok, tok)) if tok in _WORDS or tok.replace(".", "", 1).isdigit() else float("nan")


def _hours(n: float, unit: str) -> float:
    u = unit.lower()
    if u.startswith(("hour", "hr")):
        return n
    if u.startswith(("min",)):
        return n / 60
    return n * 24     # (business) days


def _fact_src(fid: str) -> dict:
    f = load_facts()["by_id"][fid]
    return {"fact_id": fid, "title": f["title"], "statement": f["statement"], "label": load_facts()["label"]}


def source_for_fact(fid: str) -> dict:
    return _fact_src(fid)


def _sentences_with(c: Clause, pred) -> list[tuple[int, int, str]]:
    return [s for s in sentences(c) if pred(s[2])]


def check_clause(c: Clause) -> list[Hit]:
    hits: list[Hit] = []
    F = load_facts()["by_id"]

    def mk(fid, status, sev, conf, reason, s, claim, **extra):
        hits.append(Hit(status, sev, conf, reason, fid, s[2], (s[0], s[1]), c.idx, c.locator, claim, extra))

    # --- settlement promises -------------------------------------------------------------------------------
    sf = F["PF-PG-SETTLEMENT"]["value"]
    sup = F["PF-PG-SETTLEMENT"]["superseded"]["values_days"]
    for s in _sentences_with(c, lambda t: bool(_SETTLE_WORD.search(t))):
        t = s[2]
        tp = _TPLUS.search(t)
        tm = _TIME.search(t)
        inst = _INSTANT.search(t)
        guar = bool(_GUAR.search(t))
        if tm:
            hrs = _hours(_num(tm.group("n")), tm.group("u"))
            days = hrs / 24
        elif tp:
            days, hrs = float(tp.group(1)), float(tp.group(1)) * 24
        elif inst:
            days, hrs = 0.0, 0.0
        else:
            continue
        if days != days:   # NaN: could not parse
            continue
        hold_ok = bool(re.search(r"subject to|risk review|as per (the )?(merchant )?agreement", t, re.I))
        if days < sf["fastest_days"]:
            sev = "critical" if guar else "high"
            mk("PF-PG-SETTLEMENT", "contradiction", sev, 0.95 if (guar or inst) else 0.85,
               f"Promises settlement in {_fmt_h(hrs)}{' and guarantees it' if guar else ''}; approved terms are T+{sf['default_days']} by default (T+{sf['fastest_days']} on request, "
               f"subject to risk review) with no guaranteed shorter time.", s, "settlement_time", promised_hours=hrs)
        elif days in sup or days > sf["default_days"]:
            mk("PF-PG-SETTLEMENT", "outdated", "medium", 0.9,
               f"States a T+{int(days)} settlement; the current cycle is T+{sf['default_days']}. {F['PF-PG-SETTLEMENT']['superseded']['note']}", s, "settlement_time", promised_hours=hrs)
        elif days == sf["fastest_days"] and not hold_ok:
            mk("PF-PG-SETTLEMENT", "review", "medium", 0.8,
               "T+1 settlement is available only on request and subject to risk review; the clause states it without that condition.", s, "settlement_time", promised_hours=hrs)
        else:
            mk("PF-PG-SETTLEMENT", "current", "low", 0.9,
               f"T+{int(days)} matches the approved settlement cycle.", s, "settlement_time", promised_hours=hrs)

    # --- settlement holds ----------------------------------------------------------------------------------
    for s in _sentences_with(c, lambda t: bool(_NO_HOLD.search(t)) and bool(_SETTLE_WORD.search(t))):
        mk("PF-PG-HOLD", "contradiction", "high", 0.85,
           "Says settlement is never held or delayed; Paytm may hold settlement for risk review, chargebacks, disputes or regulatory reasons.", s, "settlement_hold")

    # --- fees -----------------------------------------------------------------------------------------------
    fc, fu = F["PF-PG-FEE-CARD"], F["PF-PG-FEE-UPI"]
    for s in sentences(c):
        t = s[2]
        if _NOT_FEE.search(t) or not _FEE_CTX.search(t):
            continue
        for m in _PCT.finditer(t):
            p = float(m.group("p"))
            ctx = t[max(0, m.start() - 55):m.start()]          # judge each percentage by what sits just before it ("card MDR is 2.25% and UPI is 0.5%")
            last_upi = max((x.start() for x in _UPI.finditer(ctx)), default=-1)
            last_card = max([x.start() for x in _CARD.finditer(ctx)] + [x.start() for x in re.finditer(r"\bmdr\b", ctx, re.I)] or [-1])
            if last_upi >= 0 and last_upi > last_card:
                if p != fu["value"]["percent"]:
                    mk("PF-PG-FEE-UPI", "contradiction", "high", 0.92, f"States {p:g}% on UPI; UPI carries no MDR in the approved fee terms.", s, "fee_rate", percent=p)
                else:
                    mk("PF-PG-FEE-UPI", "current", "low", 0.9, "0% UPI MDR matches the approved fee terms.", s, "fee_rate", percent=p)
            elif last_card >= 0 or _CARD.search(t) or re.search(r"\bmdr\b", t, re.I):
                if p == fc["value"]["percent"]:
                    mk("PF-PG-FEE-CARD", "current", "low", 0.9, f"{p:g}% card MDR matches the approved fee schedule.", s, "fee_rate", percent=p)
                elif p in fc["superseded"]["values_percent"]:
                    mk("PF-PG-FEE-CARD", "outdated", "medium", 0.92, f"States {p:g}% card MDR. {fc['superseded']['note']} Current rate: {fc['value']['percent']:g}% plus GST.", s, "fee_rate", percent=p)
                else:
                    mk("PF-PG-FEE-CARD", "contradiction", "high", 0.85, f"States {p:g}% card MDR; the approved rate is {fc['value']['percent']:g}% plus GST.", s, "fee_rate", percent=p)
    for s in _sentences_with(c, lambda t: bool(_ZERO_FEE.search(t)) and bool(_ALL_MODES.search(t) or re.search(r"\bhidden\b|\bno charges\b|\bzero (charges|fees)\b", t, re.I))):
        if _UPI.search(s[2]) and not _ALL_MODES.search(s[2]):
            continue
        mk("PF-PG-FEES-ALL", "contradiction", "medium", 0.82,
           "Presents charges as zero or absent for every mode; fees apply to cards, netbanking and other non-UPI modes.", s, "zero_fee")

    # --- onboarding / approval / KYC -------------------------------------------------------------------------
    for s in _sentences_with(c, lambda t: bool(_NO_KYC.search(t))):
        mk("PF-PG-APPROVAL", "contradiction", "critical", 0.95, "Suggests onboarding without KYC or documents; KYC is mandatory before a merchant can be activated.", s, "kyc_waiver")
    for s in _sentences_with(c, lambda t: bool(_APPROVAL_G.search(t))):
        mk("PF-PG-APPROVAL", "contradiction", "high", 0.93, "Guarantees approval or instant activation; onboarding is subject to KYC and risk verification and approval is not guaranteed.", s, "approval_guarantee")
    for s in _sentences_with(c, lambda t: bool(_GO_LIVE_FAST.search(t))):
        if any(h.quote == s[2] for h in hits):
            continue
        mk("PF-PG-APPROVAL", "contradiction", "high", 0.85, "Promises activation within hours or minutes; the indicative time is 3-5 working days after complete documents.", s, "activation_time")
    # one finding per (fact, sentence): keep the most severe, so a single sentence never produces duplicates
    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    best: dict = {}
    for h in hits:
        k = (h.fact_id, h.span)
        if k not in best or rank[h.severity] < rank[best[k].severity]:
            best[k] = h
    return [h for h in hits if best[(h.fact_id, h.span)] is h]


def _fmt_h(h: float) -> str:
    if h == 0:
        return "an immediate/instant timeframe"
    if h < 1:
        return f"{round(h * 60)} minutes"
    if h < 24:
        return f"{h:g} hours"
    return f"{h / 24:g} days"


def missing_disclosures(doc_type: str, content: str) -> list[dict]:
    """Required statements absent from the whole document. Missing evidence is never `current`."""
    out = []
    low = content.lower()
    for d in load_facts()["required_disclosures"]:
        if doc_type not in d["applies_to"]:
            continue
        if any(p in low for p in d["patterns"]):
            continue
        out.append(d)
    return out


def disclosure_present(d: dict, text: str) -> bool:
    low = text.lower()
    return any(p in low for p in d["patterns"])


def validate_wording(fid: str, wording: str) -> bool:
    """A proposed replacement must not itself trip the checks for the same fact."""
    c = Clause(0, "proposed", wording, 0, len(wording))
    return not any(h.fact_id == fid and h.status in ("contradiction", "outdated", "review") for h in check_clause(c))


def extract_terms(clauses: list[Clause]) -> dict:
    """Numbers used for cross-document consistency: settlement hours and card MDR, with their clause."""
    terms: dict[str, list[dict]] = {"settlement_hours": [], "card_mdr": []}
    for c in clauses:
        for h in check_clause(c):
            if h.claim == "settlement_time":
                terms["settlement_hours"].append({"value": h.extra["promised_hours"], "clause_idx": c.idx, "quote": h.quote, "span": h.span, "locator": c.locator})
            elif h.claim == "fee_rate" and h.fact_id == "PF-PG-FEE-CARD":
                terms["card_mdr"].append({"value": h.extra["percent"], "clause_idx": c.idx, "quote": h.quote, "span": h.span, "locator": c.locator})
    return terms
