"""RBI-TAT-COMP-100, NPCI-UPI-CHARGES-PRE, NPCI-UPI-MASK-IDENTIFIERS."""
from __future__ import annotations

import re

from .common import (Ctx, Finding, all_matches, anchor_span, any_match, bool_fact, check_entry,
                     fail_from_span, make_verdict, num_fact, str_fact, tidy_span, rx)
from .phrases import comp_elements, find_complaint_required
from .tat import _TT_ALIASES, determine_row, ROW_UNDETERMINED

B_TIER = "B"


# ------------------------------------------------------------------ RBI-TAT-COMP-100

def check_comp100(ctx: Ctx) -> dict:
    card, m, f, seg = ctx.card, ctx.m, ctx.f, ctx.seg
    cfg = card["check"]["config"]
    checks: list[dict] = []
    tt_given = str_fact(ctx.facts, "transaction_type") in _TT_ALIASES
    j = str_fact(ctx.facts, "journey")
    in_journey = bool(j and j in [x.lower() for x in card["scope"]["journeys"]])
    if not (tt_given or in_journey or any_match(m["topic_cues"], f) or any_match(m["compensation_cues"], f)):
        return make_verdict(card, "not_applicable", confidence=0.85,
                            reason="text does not discuss a failed transaction or its compensation",
                            checks=[check_entry("topic", "skip", "no failed-payment or compensation wording")])

    # must_not_convey (checked first: wrong whenever it is said)
    bad: list[Finding] = []
    for mt in all_matches(m["discretionary"], f):
        sa, sb = seg.sentence_at(mt.start())
        if not any_match(m["compensation_cues"], f[sa:sb]):
            continue
        ca, cb = seg.clause_at(mt.start())
        bad.append(Finding("fail", "must_not_convey", "compensation is described as discretionary", (ca, cb), prio=1))
        break
    for c in find_complaint_required(ctx, m):
        sa, sb = seg.sentence_at(c.span[0])
        if c.level == "fail" and any_match(m["compensation_cues"], f[sa:sb]):
            bad.append(Finding("fail", "must_not_convey", "customer must raise a complaint/claim to receive compensation", c.span, prio=2))
            break
    for b in bad:
        checks.append(check_entry(b.name, "fail", b.detail))
    if bad:
        return fail_from_span(ctx, bad[0].span, reason="; ".join(b.detail for b in bad), checks=checks)

    row, src, _ = determine_row(ctx, m)
    delay = num_fact(ctx.facts, "delay_days")
    if delay is None:
        checks.append(check_entry("applicability", "review", "facts.delay_days missing: cannot tell whether the delay is beyond the row deadline"))
        return make_verdict(card, "review", confidence=1.0,
                            reason="facts insufficient: delay_days is required to know whether compensation is due", checks=checks)
    deadlines = {k: int(v) for k, v in m["row_deadlines"].items()}
    lo_dl, hi_dl = min(deadlines.values()), max(deadlines.values())
    if delay <= lo_dl:
        deadline = lo_dl      # not late under any carded row: no row guess is needed
    elif row in deadlines:
        deadline = deadlines[row]
    elif row == "other":
        checks.append(check_entry("row_selection", "review", "transaction_type=other: that TAT row is not carded"))
        return make_verdict(card, "review", confidence=1.0, reason="the matching TAT row is not carded yet", checks=checks)
    elif delay > hi_dl:
        deadline = hi_dl      # late under every carded row, so no row guess is needed
    else:
        checks.append(check_entry("row_selection", "review", ROW_UNDETERMINED))
        return make_verdict(card, "review", confidence=1.0, reason=ROW_UNDETERMINED, checks=checks)
    if delay <= deadline:
        return make_verdict(card, "not_applicable", confidence=0.9,
                            reason=f"delay_days={delay:g} is not beyond the row deadline (T+{deadline}); compensation not yet due",
                            checks=[check_entry("applicability", "skip", f"delay {delay:g} <= {deadline}")])

    # delay beyond deadline: both elements must be conveyed (shared predicate)
    ce = comp_elements(ctx, m)
    amount_ok, auto_ok, wrong_amount, amount_sents = ce.amount_per_day, ce.automatic, ce.wrong_amount, ce.amount_spans
    checks.append(check_entry("amount_per_day", "pass" if amount_ok else "fail",
                              "₹100 per day conveyed" if amount_ok else "₹100 per day of delay not conveyed"))
    checks.append(check_entry("automatic", "pass" if auto_ok else "fail",
                              "credited automatically / no complaint needed conveyed" if auto_ok
                              else "does not say compensation is automatic / needs no claim"))
    checks.append(check_entry("semantic", "review", "Tier B not configured: paraphrases the matchers do not know"))
    if amount_ok and auto_ok:
        return make_verdict(card, "pass", confidence=0.85,
                            reason=f"delay {delay:g} days > T+{deadline}: ₹100/day and automatic crediting both conveyed",
                            checks=checks)
    missing = [n for n, ok in (("₹100 per day of delay", amount_ok), ("automatic crediting without a complaint or claim", auto_ok)) if not ok]
    if wrong_amount and not amount_ok:
        missing[0] = f"₹100 per day (reply states '{wrong_amount[0]}')"
    pref = amount_sents or ([wrong_amount[1]] if wrong_amount else [])
    cm = any_match(m["compensation_cues"], f)
    if not pref and cm:
        pref = [seg.sentence_at(cm.start())]
    sp = anchor_span(ctx, pref)
    return fail_from_span(ctx, sp, reason=f"delay {delay:g} days is beyond T+{deadline} but the reply does not convey: " + ", ".join(missing),
                          checks=checks, confidence=0.9)


# ------------------------------------------------------------------ NPCI-UPI-CHARGES-PRE

def check_charges(ctx: Ctx) -> dict:
    card, m, f, seg = ctx.card, ctx.m, ctx.f, ctx.seg
    checks: list[dict] = []
    if not any_match(m["topic_cues"], f):
        if str_fact(ctx.facts, "journey") in ("merchant_payment", "checkout"):
            return make_verdict(card, "review", confidence=0.5,
                                reason="facts say this is a merchant checkout journey but the reply contains no recognisable statement about fees; a person must confirm nothing misleading was said",
                                checks=[check_entry("topic", "review", "checkout journey without fee wording")])
        return make_verdict(card, "not_applicable", confidence=0.85, reason="text makes no statement about fees or charges",
                            checks=[check_entry("topic", "skip", "no fee/charge wording")])
    fee_shown = bool_fact(ctx.facts, "convenience_fee_shown")
    fails: list[Finding] = []

    for mt in all_matches(m["surcharge_claims"], f):
        ctx_before = f[max(0, mt.start() - 25):mt.start()]
        if (any_match(m["surcharge_negation"], ctx_before) or any_match(m["surcharge_negation"], mt.group(0))
                or any_match(m.get("surcharge_negation_after", []), f[mt.end():mt.end() + 25])):
            continue
        fails.append(Finding("fail", "surcharge", "a surcharge/extra charge is described as levied on UPI payments", seg.clause_at(mt.start()), prio=1))
        break
    for mt in all_matches(m["fee_after_mode"], f):
        fails.append(Finding("fail", "ordering", "fee is described as shown only after the payment mode is selected", seg.clause_at(mt.start()), prio=2))
        break
    claim = None
    for mt in all_matches(m["no_fee_claims"], f):
        pre = f[max(0, mt.start() - 20):mt.start()]
        if any_match(m["claim_negation"], pre):
            continue
        claim = mt
        break
    if claim is not None:
        checks.append(check_entry("no_fee_claim", "info", f"reply says: '{ctx.text[claim.start():claim.end()]}'"))
        if fee_shown is True:
            fails.append(Finding("fail", "fact_consistency",
                                 "reply says there is no fee/charge while facts.convenience_fee_shown is true",
                                 seg.clause_at(claim.start()), prio=0))
    for fl in fails:
        checks.append(check_entry(fl.name, "fail", fl.detail))
    if fails:
        fails.sort(key=lambda x: x.prio)
        return fail_from_span(ctx, fails[0].span, reason="; ".join(x.detail for x in fails), checks=checks)

    if claim is not None:
        if fee_shown is False:
            checks.append(check_entry("fact_consistency", "pass", "no fee claimed and no convenience fee shown"))
            return make_verdict(card, "pass", confidence=0.85, reason="statement that UPI has no fee is consistent with facts (no convenience fee shown)", checks=checks)
        checks.append(check_entry("fact_consistency", "review", "facts.convenience_fee_shown missing"))
        return make_verdict(card, "review", confidence=0.5,
                            reason="reply claims no fee but facts.convenience_fee_shown is unknown, so consistency cannot be checked",
                            checks=checks)
    cons = any_match(m.get("consistent_statements", []), f)
    if cons is not None:
        checks.append(check_entry("surcharge_statement", "pass", f"'{ctx.text[cons.start():cons.end()]}' is consistent with the rule (no surcharge on UPI)"))
        return make_verdict(card, "pass", confidence=0.8, reason="reply says there is no surcharge on UPI, which matches the NPCI rule", checks=checks)
    # no claim: a fee statement
    upfront = any_match(m["fee_upfront"], f)
    if fee_shown is True and upfront:
        checks.append(check_entry("disclosure", "pass", "fee described as disclosed on the payment page before choosing the mode"))
        return make_verdict(card, "pass", confidence=0.8, reason="convenience fee is described as disclosed upfront and the facts show it", checks=checks)
    checks.append(check_entry("disclosure", "review", "fee mentioned but upfront disclosure / facts could not be confirmed"))
    return make_verdict(card, "review", confidence=0.5,
                        reason="fee wording present but nothing shows it is consistent with the facts and disclosed before payment mode selection",
                        checks=checks)


# ------------------------------------------------------------------ NPCI-UPI-MASK-IDENTIFIERS

_UPI_RX = re.compile(r"(?P<h>[^\s@<>()\[\]{},;:\"'/\\]{1,64})@(?P<d>[a-z][a-z0-9.\-]*[a-z0-9])", re.IGNORECASE)
_DIGITS_RX = re.compile(r"(?<![\w.,+])(?:\+?91[\s-]?)?(?P<d>\d{9,18})(?![\w]|[.,]\d)")
_MOB_PLUS_RX = re.compile(r"(?<![\w])(?:\+91|0091)[\s-]?[6-9]\d{4}[\s-]?\d{5}(?![\w])")
_MOB_GROUP_RX = re.compile(r"(?<![\w])[6-9]\d{4}[\s-]\d{5}(?![\w])")
_ACC_GROUP_RX = re.compile(r"(?<![\w])\d{4}(?:[\s-]\d{4}){2,4}(?![\w])")
_MASKED = re.compile(r"[*•●×]|x{3,}", re.IGNORECASE)


def _cue_class(f: str, start: int, m: dict) -> str:
    """Closest cue before the token decides: 'pos' (mobile/account), 'neg' (ref/amount/otp), or ''."""
    win = f[max(0, start - 42):start]
    best_pos = best_neg = -1
    for p in m["positive_cues"]:
        for mm in rx(p).finditer(win):
            best_pos = max(best_pos, mm.end())
    for p in m["negative_cues"]:
        for mm in rx(p).finditer(win):
            best_neg = max(best_neg, mm.end())
    if best_pos < 0 and best_neg < 0:
        return ""
    return "pos" if best_pos >= best_neg else "neg"


def check_mask(ctx: Ctx) -> dict:
    card, m, f, text = ctx.card, ctx.m, ctx.f, ctx.text
    handles = set(h.lower() for h in m["upi_handles"])
    fails: list[tuple[int, int, str, str]] = []     # (start, end, kind, detail)
    ambig: list[tuple[int, int, str, str]] = []
    checks: list[dict] = []
    covered: list[tuple[int, int]] = []

    def free(a: int, b: int) -> bool:
        return not any(a < y and x < b for x, y in covered)

    for mt in _UPI_RX.finditer(f):
        h, d = mt.group("h"), mt.group("d").lower()
        a, b = mt.start(), mt.end()
        covered.append((a, b))
        if "." in d:
            checks.append(check_entry("upi_id", "skip", f"'{text[a:b]}' is an e-mail address, not a UPI ID"))
        elif _MASKED.search(h):
            checks.append(check_entry("upi_id", "pass", f"'{text[a:b]}' is masked"))
        elif d in handles:
            fails.append((a, b, "upi_id", "unmasked UPI ID"))
        else:
            ambig.append((a, b, "upi_id", f"'@{d}' is not a known UPI handle; could be an e-mail-like or UPI ID"))

    for rxp, kind in ((_MOB_PLUS_RX, "mobile_number"), (_MOB_GROUP_RX, "mobile_number")):
        for mt in rxp.finditer(f):
            a, b = mt.start(), mt.end()
            if not free(a, b):
                continue
            cls = _cue_class(f, a, m)
            covered.append((a, b))
            if cls == "neg":
                checks.append(check_entry(kind, "skip", f"'{text[a:b]}' follows a reference/amount cue"))
            elif kind == "mobile_number" and (rxp is _MOB_PLUS_RX or cls == "pos"):
                fails.append((a, b, kind, "unmasked mobile number"))
            else:
                ambig.append((a, b, kind, "grouped 10-digit number with no mobile/account cue"))

    for mt in _ACC_GROUP_RX.finditer(f):
        a, b = mt.start(), mt.end()
        if not free(a, b):
            continue
        cls = _cue_class(f, a, m)
        covered.append((a, b))
        if cls == "pos":
            fails.append((a, b, "account_number", "unmasked account number (grouped digits)"))
        elif cls == "neg":
            checks.append(check_entry("account_number", "skip", f"'{text[a:b]}' follows a reference/amount cue"))
        else:
            ambig.append((a, b, "account_number", "grouped digits with no cue: could be an account or card-like number"))

    for mt in _DIGITS_RX.finditer(f):
        a, b = mt.start(), mt.end()
        if not free(a, b):
            continue
        d = mt.group("d")
        da = mt.start("d")
        cls = _cue_class(f, a, m)
        covered.append((a, b))
        is_mobile_shape = (len(d) == 10 and d[0] in "6789") or (mt.group(0) != d and len(d) == 10 and d[0] in "6789")
        if cls == "neg":
            checks.append(check_entry("digits", "skip", f"'{text[a:b]}' follows a reference/amount/OTP cue"))
        elif cls == "pos":
            fails.append((a, b, "mobile_number" if is_mobile_shape else "account_number",
                          "unmasked mobile number" if is_mobile_shape else "unmasked account number"))
        elif is_mobile_shape and f[a] == "+":
            fails.append((a, b, "mobile_number", "unmasked mobile number with country code"))
        else:
            ambig.append((a, b, "mobile_number" if is_mobile_shape else "account_number",
                          f"{len(d)}-digit number with no mobile/account/reference cue"))

    for a, b, kind, detail in fails:
        checks.append(check_entry(kind, "fail", f"'{text[a:b]}': {detail}"))
    for a, b, kind, detail in ambig:
        checks.append(check_entry(kind, "review", f"'{text[a:b]}': {detail}"))
    if fails:
        fails.sort()
        a, b = fails[0][0], fails[0][1]
        return fail_from_span(ctx, (a, b), reason="; ".join(f"{k}: {d}" for _, _, k, d in fails[:3]), checks=checks, confidence=0.95)
    if ambig:
        ambig.sort()
        a, b = ambig[0][0], ambig[0][1]
        return make_verdict(card, "review", confidence=0.5, quote=text[a:b], span=(a, b),
                            reason="ambiguous identifier-like token; not enough context to call it an unmasked identifier or a reference number",
                            checks=checks)
    checks.append(check_entry("scan", "pass", "no unmasked UPI ID, mobile number or account number found"))
    return make_verdict(card, "pass", confidence=0.9,
                        reason="no unmasked UPI ID, mobile number or account number detected (masked forms and reference numbers ignored)",
                        checks=checks)
