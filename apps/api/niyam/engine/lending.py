"""RBI-KFS-LOAN, RBI-COOLING-OFF, RBI-OMB-ESCALATION."""
from __future__ import annotations

import re

from .common import (Ctx, all_matches, anchor_span, any_match, check_entry, fail_from_span,
                     make_verdict, str_fact, rx, tidy_span)

B_TIER = "B"
_NUMW = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "ek": 1, "do": 2, "teen": 3}


def _n(tok: str) -> float:
    tok = tok.lower()
    return float(_NUMW[tok]) if tok in _NUMW else float(tok)


# ------------------------------------------------------------------ RBI-KFS-LOAN

def check_kfs(ctx: Ctx) -> dict:
    card, m, f, text = ctx.card, ctx.m, ctx.f, ctx.text
    marker = any_match(m["kfs_marker"], f)
    j = str_fact(ctx.facts, "journey")
    loanish = (j in [x.lower() for x in card["scope"]["journeys"]]) if j else False
    prod = str_fact(ctx.facts, "product") or ""
    loanish = loanish or any(w in prod for w in ("loan", "lend", "pay later", "credit")) or any_match(m["loan_cues"], f) is not None
    if marker is None:
        if loanish:
            return make_verdict(card, "review", tier=B_TIER, confidence=0.5,
                                reason="loan content but no Key Fact Statement document recognised; whether a KFS was given before the contract is a Tier B / process question (Tier B not configured)",
                                checks=[check_entry("kfs_document", "review", "no KFS marker found"),
                                        check_entry("semantic", "review", "Tier B not configured")])
        return make_verdict(card, "not_applicable", confidence=0.85, reason="text is not about a loan or a KFS",
                            checks=[check_entry("topic", "skip", "no loan / KFS wording")])
    features = [name for name, pats in m["doc_features"].items() if any_match(pats, f)]
    is_doc = len(features) >= int(m["min_doc_features"])
    checks = [check_entry("kfs_document", "pass" if is_doc else "review",
                          f"KFS marker found; document-like features: {features or 'none'} (need {m['min_doc_features']})")]
    if not is_doc:
        return make_verdict(card, "review", tier=B_TIER, confidence=0.5,
                            reason="KFS is mentioned but the text is not clearly a KFS document, so required elements cannot be demanded of it (Tier B not configured)",
                            checks=checks + [check_entry("semantic", "review", "Tier B not configured")])
    missing: list[str] = []
    for name, pats in m["elements"].items():
        hit = any_match(pats, f)
        checks.append(check_entry(name, "pass" if hit else "fail", f"found '{text[hit.start():hit.end()]}'" if hit else "not found"))
        if not hit:
            missing.append(name)
    # validity numeric rule
    val_fail = val_review = None
    vm = any_match([m["validity_value"]], f)
    if vm and "validity" not in missing:
        n = _n(vm.group("n"))
        wd = bool(vm.group("wd"))
        tm = any_match([m["tenor_value"]], f)
        tenor_days = None
        if tm:
            tn = float(tm.group("n"))
            u = tm.group("u").lower()
            tenor_days = tn * (365 if u.startswith("y") else 30 if u.startswith("m") else 1)
        if wd and n < 3 and tenor_days is not None and tenor_days >= 7:
            val_fail = f"validity {n:g} working day(s) but tenor is {tenor_days:g} days (needs at least 3 working days)"
        elif wd and n < 3 and tenor_days is None:
            val_review = f"validity {n:g} working day(s): allowed only if tenor is under 7 days, tenor not found"
        if val_fail:
            checks.append(check_entry("validity_period", "fail", val_fail))
        elif val_review:
            checks.append(check_entry("validity_period", "review", val_review))
    if missing or val_fail:
        a, b = marker.start(), marker.end()
        reason = []
        if missing:
            reason.append("KFS document lacks: " + ", ".join(missing))
        if val_fail:
            reason.append(val_fail)
        return fail_from_span(ctx, (a, b), reason="; ".join(reason), checks=checks, confidence=0.9)
    pending = ["kfs_provided_before_loan_contract_executed", "kfs_language_understood_by_borrower",
               "validity numeric rule" if val_review else None]
    pending = [p for p in pending if p]
    return make_verdict(card, "review", tier=B_TIER, confidence=0.6,
                        reason="all Tier A document elements are present; Tier B (not configured) must confirm: " + ", ".join(pending)
                        + (f"; {val_review}" if val_review else ""),
                        checks=checks + [check_entry("semantic", "review", "Tier B not configured: " + ", ".join(pending))])


# ------------------------------------------------------------------ RBI-COOLING-OFF

def _lending_ctx(m: dict, f: str, ctx: Ctx) -> bool:
    p = str_fact(ctx.facts, "product")
    if p:
        return any(w in p for w in ("lend", "loan", "pay later", "credit"))
    return any_match(m["lending_cues"], f) is not None


def _lending_ctx_facts(ctx: Ctx) -> bool:
    p = str_fact(ctx.facts, "product")
    return bool(p) and any(w in p for w in ("lend", "loan", "pay later", "credit"))


def check_cooling(ctx: Ctx) -> dict:
    card, m, f, text, seg = ctx.card, ctx.m, ctx.f, ctx.text, ctx.seg
    j = str_fact(ctx.facts, "journey")
    facts_say_applies = _lending_ctx_facts(ctx) and j in ("loan_cancellation", "prepayment")
    if not facts_say_applies and not (any_match(m["topic_cues"], f) and _lending_ctx(m, f, ctx)):
        return make_verdict(card, "not_applicable", confidence=0.85,
                            reason="text is not about exiting, cancelling or prepaying a digital loan",
                            checks=[check_entry("topic", "skip", "no loan exit/cancellation/prepayment wording in a lending context")])
    checks: list[dict] = []
    bad = None
    for mt in all_matches(m["must_not_convey"], f):
        sa, sb = seg.sentence_at(mt.start())
        sent = f[sa:sb]
        win = f[max(sa, mt.start() - 25):mt.end()]
        if any_match(m["penalty_negation"], win) or any_match(m["after_cooling_exception"], sent):
            continue
        bad = (seg.clause_at(mt.start()), text[mt.start():mt.end()])
        break
    if bad:
        checks.append(check_entry("must_not_convey", "fail", f"forbidden statement: '{bad[1]}'"))
        return fail_from_span(ctx, bad[0], reason=f"agent conveys something the Directions forbid: '{bad[1]}' (para 10: penal-free exit in cooling-off)",
                              checks=checks)
    pv = any_match([m["period_value"]], f)
    if pv:
        n = float(pv.group("n"))
        u = pv.group("u").lower()
        hours = u.startswith(("hour", "hr", "ghant", "\u0918\u0902\u091f"))
        too_short = (n / 24 if hours else n) < 1
        if too_short:
            checks.append(check_entry("minimum_period", "fail", f"cooling-off stated as {n:g} {u}; the Directions require not less than one day"))
            return fail_from_span(ctx, seg.clause_at(pv.start()), reason="stated cooling-off period is shorter than one day", checks=checks)
    free = any_match(m["penal_free_exit"], f)
    cool = any_match(m["cooling_mention"], f)
    prin = any_match(m["principal_apr"], f)
    checks.append(check_entry("penal_free_exit", "pass" if free else "review", "explicit penal-free exit conveyed" if free else "no explicit penal-free exit wording"))
    checks.append(check_entry("cooling_off_period", "pass" if cool else "review", "cooling-off period mentioned" if cool else "cooling-off period not mentioned"))
    checks.append(check_entry("principal_and_apr", "pass" if prin else "review", "exit by repaying principal and proportionate APR conveyed" if prin else "repayment of principal + proportionate APR not stated"))
    if free and cool and prin:
        return make_verdict(card, "pass", confidence=0.85,
                            reason="explicit penal-free exit during the cooling-off period by repaying principal and proportionate APR is conveyed",
                            checks=checks)
    return make_verdict(card, "review", confidence=0.5,
                        reason="exit/cancellation/prepayment is discussed but the explicit penal-free cooling-off exit is not conveyed in words the matchers recognise",
                        checks=checks + [check_entry("semantic", "review", "Tier B not configured")])


# ------------------------------------------------------------------ RBI-OMB-ESCALATION

def _truthy(v) -> bool:
    return v is True


def check_omb(ctx: Ctx) -> dict:
    card, m, f, text, seg = ctx.card, ctx.m, ctx.f, ctx.text, ctx.seg
    checks: list[dict] = []
    p = str_fact(ctx.facts, "product")
    if p:
        lending = any(w in p for w in ("lend", "loan", "pay later", "credit"))
        if not lending:
            return make_verdict(card, "not_applicable", confidence=1.0,
                                reason=f"product '{p}' is not digital lending; this card covers digital-lending complaints only (Directions para 11(iv))",
                                checks=[check_entry("scope", "skip", f"facts.product={p}")])
        lend_src = "facts.product"
    else:
        lend_src = "text cues" if any_match(m["lending_cues"], f) else None
        if lend_src is None and not isinstance((ctx.facts or {}).get("complaint_state"), dict) and not any_match(m["text_trigger"], f) \
                and not any_match(m.get("complaint_topic", []), f):
            return make_verdict(card, "not_applicable", confidence=0.8, reason="no complaint, loan or escalation context in the text or facts",
                                checks=[check_entry("scope", "skip", "no complaint context")])
        if lend_src is None:
            return make_verdict(card, "review", tier=B_TIER, confidence=0.5,
                                reason="cannot tell whether this is a digital-lending complaint (facts.product missing, no lending wording); Tier B not configured",
                                checks=[check_entry("scope", "review", "product unknown")])
    cs = (ctx.facts or {}).get("complaint_state")
    trig: list[str] = []
    if isinstance(cs, dict):
        if _truthy(cs.get("rejected")):
            trig.append("complaint rejected wholly or partly")
        if _truthy(cs.get("unsatisfied")):
            trig.append("borrower not satisfied with the reply")
        d = cs.get("days_without_reply")
        if isinstance(d, (int, float)) and not isinstance(d, bool) and d >= 30:
            trig.append(f"no reply for {d:g} days (>= 30)")
        if not trig:
            return make_verdict(card, "not_applicable", confidence=0.9,
                                reason="no escalation trigger in facts.complaint_state (not rejected, not unsatisfied, under 30 days without reply)",
                                checks=[check_entry("trigger", "skip", f"complaint_state={cs}")])
        trig_src = "facts"
    else:
        tm = any_match(m["text_trigger"], f)
        if tm is None:
            return make_verdict(card, "review", tier=B_TIER, confidence=0.5,
                                reason="facts.complaint_state missing and the text shows no rejection/closure, so the trigger cannot be evaluated; Tier B not configured",
                                checks=[check_entry("trigger", "review", "complaint_state missing")])
        trig.append(f"text says: '{text[tm.start():tm.end()]}'")
        trig_src = "text"
    checks.append(check_entry("trigger", "pass", f"{', '.join(trig)} (via {trig_src}; product via {lend_src})"))
    route = any_match(m["route_cues"], f)
    neg = None
    if route:
        sa, sb = seg.sentence_at(route.start())
        neg = any_match(m["route_negated"], f[sa:sb])
    if route and not neg:
        checks.append(check_entry("escalation_route", "pass", f"RBI CMS / Ombudsman route conveyed: '{text[route.start():route.end()]}'"))
        return make_verdict(card, "pass", confidence=0.85, reason="trigger holds and the RBI Complaint Management System / Integrated Ombudsman route is conveyed",
                            checks=checks + [check_entry("semantic", "info", "adequacy of wording is a Tier B question (not configured)")])
    detail = ("reply denies/negates the RBI escalation route" if neg else
              "reply does not tell the borrower they can escalate on the RBI Complaint Management System / Integrated Ombudsman Scheme")
    checks.append(check_entry("escalation_route", "fail", detail))
    if trig_src == "text":
        return make_verdict(card, "review", confidence=0.6,
                            reason=detail + " (trigger inferred from text only; facts.complaint_state would settle it)", checks=checks)
    if neg:
        span = seg.clause_at(route.start())
    else:
        closing = any_match(m["text_trigger"], f)
        span = anchor_span(ctx, [(closing.start(), closing.end())] if closing else None)
    return fail_from_span(ctx, span, reason=detail + f" while a trigger holds ({'; '.join(trig)})", checks=checks, confidence=0.9)
