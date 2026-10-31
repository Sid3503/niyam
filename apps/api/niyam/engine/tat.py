"""RBI-TAT-UPI-TRANSFER (row 4a, T+1) and RBI-TAT-UPI-MERCHANT (row 4b, T+5): timeline_consistency.

The single most important guard: the engine NEVER guesses which row applies. It uses
facts.transaction_type, then facts.journey == 'merchant_payment', then CLEAR text cues; if
those are absent or contradict each other the verdict is ``review`` with the reason
'cannot determine which RBI TAT row applies'.
"""
from __future__ import annotations

import math

from .common import (Ctx, Finding, any_match, anchor_span, check_entry, fail_from_span, make_verdict,
                     num_fact, str_fact, tidy_span, all_matches)
from .phrases import comp_elements, find_complaint_required
from .timeline import Promise, annotate, extract_promises

ROW_UNDETERMINED = "cannot determine which RBI TAT row applies"
_TT_ALIASES = {
    "upi_transfer": "upi_transfer", "transfer": "upi_transfer", "p2p": "upi_transfer",
    "upi_merchant": "upi_merchant", "merchant": "upi_merchant", "p2m": "upi_merchant",
    "other": "other",
}


def determine_row(ctx: Ctx, m: dict) -> tuple[str | None, str, dict]:
    """Return (row, source, detail). row in upi_transfer | upi_merchant | other | None."""
    tt = str_fact(ctx.facts, "transaction_type")
    if tt in _TT_ALIASES:
        return _TT_ALIASES[tt], "facts.transaction_type", {}
    if str_fact(ctx.facts, "journey") == "merchant_payment":
        return "upi_merchant", "facts.journey=merchant_payment", {}
    mer = all_matches(m["row_cues"]["merchant"], ctx.f)
    tra = all_matches(m["row_cues"]["transfer"], ctx.f)
    detail = {"merchant": [ctx.text[x.start():x.end()] for x in mer][:4],
              "transfer": [ctx.text[x.start():x.end()] for x in tra][:4]}
    if mer and not tra:
        return "upi_merchant", "text cues", detail
    if tra and not mer:
        return "upi_transfer", "text cues", detail
    return None, "none", detail


def _topic(ctx: Ctx, m: dict, card: dict) -> bool:
    if str_fact(ctx.facts, "transaction_type") in _TT_ALIASES:
        return True
    j = str_fact(ctx.facts, "journey")
    if j and j in [x.lower() for x in card.get("scope", {}).get("journeys", [])]:
        return True
    return any_match(m["topic_cues"], ctx.f) is not None


def _relevant(p: Promise, ctx: Ctx, m: dict, topic_from_facts: bool) -> str | None:
    """None if the promise is about the money coming back; otherwise the ignore reason."""
    f, seg = ctx.f, ctx.seg
    sa, sb = p.sentence
    sent = f[sa:sb]
    ca, cb = p.clause
    clause = f[ca:cb]
    strong = any_match(m["money_cues"], sent)
    if strong and any_match(m["contact_cues"], clause):
        # 'we will get back to you in 2 days regarding the reversal': the timeline is for the update
        sm = any_match(m["money_cues"], clause)
        if sm is None or any_match(m["update_topic_prefix"], clause[:sm.start()]):
            return "timeline is for an update/contact about the reversal, not the reversal itself"
    if strong:
        return None
    if any_match(m["contact_cues"], sent):
        return "timeline is for an update/contact, not the reversal"
    if any_match(m["money_weak"], sent):
        return None
    prev = seg.prev_sentence(p.start)
    if prev and any_match(m["money_cues"], f[prev[0]:prev[1]]):
        return None
    if topic_from_facts:
        return None
    return "timeline is not tied to a reversal/refund"


def _judge(p: Promise, deadline: int, merchant: bool, late: bool) -> tuple[str, str]:
    """Return (level, detail) for one promise: level in ok | fail | review."""
    n = p.days
    desc = f"'{p.label}'"
    if p.kind == "vague":
        if p.min_days > deadline:
            return "fail", f"{desc}: at least {p.min_days:g} days; allowed {deadline}"
        return "review", f"{desc}: vague duration, cannot compare with allowed {deadline}"
    relative = p.kind in ("same_day", "next_day")
    if p.working:
        lo = n
        hi = n + 2 * math.ceil(n / 5)
    else:
        lo = hi = n
    if relative and late:
        # already beyond the deadline: a 'today/tomorrow' promise is not a NEW later deadline
        compliant = True
    elif lo > deadline:
        return "fail", f"{desc}: promised {lo:g} day(s){' (working)' if p.working else ''}; allowed {deadline}"
    elif hi > deadline:
        return "review", (f"{desc}: {lo:g} working day(s) may be up to {hi:g} calendar days; "
                          f"RBI's T is a calendar date and the allowed limit is {deadline}")
    else:
        compliant = True
    if merchant:
        if p.kind == "tplus" and n <= 1:
            return "fail", f"{desc}: agent applies T+{n:g} to a merchant payment; row 4b allows T+{deadline}"
        if (p.days is not None and p.days <= 1 and "regulatory" in p.flags and p.kind != "same_day"):
            return "fail", f"{desc}: agent presents a next-day limit as the rule for a merchant payment (T+{deadline})"
        if p.days is not None and p.days <= 1 and p.unconditional:
            return "review", (f"{desc}: unconditional same/next-day promise; the agent cannot control "
                              f"the reversal (limit is T+{deadline})")
    else:
        if p.kind == "same_day" and p.unconditional:
            return "review", f"{desc}: unconditional same-day promise; the agent cannot control the beneficiary bank"
    return "ok", f"{desc}: {n:g} day(s) <= allowed {deadline}" if compliant else desc


def check_tat(ctx: Ctx) -> dict:
    card, m, f = ctx.card, ctx.m, ctx.f
    cfg = card["check"]["config"]
    deadline = int(cfg["deadline_days"])
    my_row = m["row"]
    merchant = my_row == "upi_merchant"
    checks: list[dict] = []

    if not _topic(ctx, m, card):
        return make_verdict(card, "not_applicable", confidence=0.85,
                            reason="text does not discuss a failed/pending UPI payment, reversal or refund",
                            checks=[check_entry("topic", "skip", "no failed-payment, reversal or refund wording")])

    row, src, rdetail = determine_row(ctx, m)
    promises = extract_promises(f, ctx.seg, m)
    annotate(promises, f, m)

    if row is None:
        info = [f"'{ctx.text[p.start:p.end]}'" for p in promises if p.ignore is None][:4]
        checks.append(check_entry("row_selection", "review",
                                  f"{ROW_UNDETERMINED}: no transaction_type fact and text cues are absent or conflict {rdetail}"))
        if info:
            checks.append(check_entry("timeline", "info", "timelines present but not evaluated: " + ", ".join(info)))
        return make_verdict(card, "review", confidence=1.0, reason=ROW_UNDETERMINED, checks=checks)
    if row == "other":
        return make_verdict(card, "not_applicable", confidence=1.0,
                            reason="transaction_type is 'other': neither UPI transfer (4a) nor UPI merchant payment (4b)",
                            checks=[check_entry("row_selection", "skip", "facts.transaction_type=other")])
    if row != my_row:
        other_id = "RBI-TAT-UPI-MERCHANT" if row == "upi_merchant" else "RBI-TAT-UPI-TRANSFER"
        return make_verdict(card, "not_applicable", confidence=1.0 if src.startswith("facts") else 0.85,
                            reason=f"this card covers {my_row}; transaction is {row} ({src}); see {other_id}",
                            checks=[check_entry("row_selection", "skip", f"{row} via {src}")])
    checks.append(check_entry("row_selection", "pass", f"{row} via {src}"))
    row_conf = 1.0 if src.startswith("facts") else 0.85

    delay = num_fact(ctx.facts, "delay_days")
    late = delay is not None and delay > deadline
    topic_from_facts = str_fact(ctx.facts, "transaction_type") in _TT_ALIASES

    findings: list[Finding] = []
    n_rel = n_ok = 0
    for p in promises:
        if p.ignore is None:
            why = _relevant(p, ctx, m, topic_from_facts)
            if why:
                p.ignore = why
        if p.ignore:
            checks.append(check_entry("timeline", "skip", f"'{ctx.text[p.start:p.end]}' ignored: {p.ignore}"))
            continue
        n_rel += 1
        level, detail = _judge(p, deadline, merchant, late)
        checks.append(check_entry("timeline", {"ok": "pass"}.get(level, level), detail))
        if level == "ok":
            n_ok += 1
        else:
            findings.append(Finding(level, "timeline", detail, p.clause, prio=0 if level == "fail" else 4))

    complaints = find_complaint_required(ctx, m)
    for c in complaints:
        checks.append(check_entry(c.name, c.level, c.detail))
    findings.extend(complaints)

    ce = comp_elements(ctx, m)
    comp_ok = ce.complete
    if late:
        if comp_ok:
            checks.append(check_entry("compensation", "pass", f"delay_days={delay:g} > {deadline}: \u20b9100/day and automatic crediting conveyed"))
        else:
            miss = [n for n, ok in (("\u20b9100 per day of delay", ce.amount_per_day), ("automatic crediting", ce.automatic)) if not ok]
            detail = (f"delay_days={delay:g} is beyond T+{deadline} but the reply does not convey: " + ", ".join(miss)
                      + ("" if not ce.mentioned else " (compensation is mentioned but incompletely)"))
            checks.append(check_entry("compensation", "fail", detail))
            pref = list(ce.amount_spans) or [p.sentence for p in promises if p.ignore is None] or [tuple(s) for s in ctx.seg.sentences[:1]]
            findings.append(Finding("fail", "compensation", detail, anchor_span(ctx, pref), prio=2))
    elif delay is not None:
        checks.append(check_entry("compensation", "skip", f"delay_days={delay:g} <= {deadline}: not yet due"))

    fails = sorted([x for x in findings if x.level == "fail"], key=lambda x: (x.prio, x.span or (0, 0)))
    if fails:
        top = fails[0]
        reason = "; ".join(x.detail for x in fails[:3])
        return fail_from_span(ctx, top.span, reason=reason, checks=checks, confidence=0.95 * (1 if row_conf == 1.0 else 0.9))
    revs = sorted([x for x in findings if x.level == "review"], key=lambda x: (x.prio, x.span or (0, 0)))
    if revs:
        top = revs[0]
        a, b = tidy_span(ctx.text, top.span) if top.span else (None, None)
        return make_verdict(card, "review", confidence=0.6, reason="; ".join(x.detail for x in revs[:3]),
                            quote=ctx.text[a:b] if a is not None else None,
                            span=(a, b) if a is not None else None, checks=checks)
    if n_ok > 0 or (late and comp_ok):
        what = f"{n_ok} compliant timeline(s)" if n_ok else "compensation conveyed for a delayed reversal"
        return make_verdict(card, "pass", confidence=0.85 * (1 if row_conf == 1.0 else 0.9),
                            reason=f"{what}; no complaint-required wording; allowed T+{deadline}", checks=checks)
    return make_verdict(card, "review", confidence=0.5,
                        reason="no reversal/refund timeline found in the reply, so there is nothing to verify against the TAT",
                        checks=checks)
