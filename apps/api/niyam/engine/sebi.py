"""SEBI-NO-ASSURED-RETURNS (must_not_claim) and DPDP-CONSENT-PURPOSE (Tier B + a cheap Tier A sub-check)."""
from __future__ import annotations

from .common import Ctx, all_matches, any_match, check_entry, fail_from_span, make_verdict, str_fact, tidy_span

B_TIER = "B"


def check_sebi(ctx: Ctx) -> dict:
    card, m, f, text, seg = ctx.card, ctx.m, ctx.f, ctx.text, ctx.seg
    spans: list[tuple[int, int, str, str]] = []
    for item in m["claims"]:
        for mt in all_matches([item["regex"]], f):
            if mt.end() > mt.start():
                spans.append((mt.start(), mt.end(), item["label"], item.get("kind", "claim")))
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    kept: list[tuple[int, int, str, str]] = []
    for s in spans:
        if kept and s[0] < kept[-1][1]:
            continue
        kept.append(s)

    def classify(a: int, b: int) -> str:
        ca, cb = seg.clause_at(a)
        sa, sb = seg.sentence_at(a)
        before = f[max(ca, a - 55):a]
        after = f[b:min(cb, b + 38)]
        if any_match(m["negation_guard"], before):
            neg = False
        else:
            neg = any_match(m["negation"], before) is not None
        if neg or any_match(m["negation_after"], after):
            return "negated"
        if any_match(m["warning_cues"], f[sa:a]):
            return "warning"
        if f[sb - 1:sb] == "?":
            return "question"
        return "live"

    checks: list[dict] = []
    live = []
    questions = []
    ambiguous = []
    disclaimers = 0
    for a, b, label, kind in kept:
        c = classify(a, b)
        checks.append(check_entry(label, {"live": "fail" if kind == "claim" else "review", "negated": "pass",
                                          "warning": "pass", "question": "review"}[c],
                                  f"'{text[a:b]}': {c}" + (" (ambiguous phrase)" if kind != "claim" and c == "live" else "")))
        if c in ("negated", "warning"):
            disclaimers += 1
        elif c == "question":
            questions.append((a, b))
        elif kind == "claim":
            live.append((a, b, label))
        else:
            ambiguous.append((a, b))

    if live:
        a, b, label = live[0]
        sa0, sb0 = seg.sentence_at(a)
        if any_match(m.get("exemption_cues", []), f[sa0:sb0]):
            checks.append(check_entry("exemption", "review", "claim made together with a government/sovereign guarantee wording: not an adviser's own promise?"))
            qa, qb = tidy_span(text, (sa0, sb0))
            return make_verdict(card, "review", confidence=0.5, quote=text[qa:qb], span=(qa, qb),
                                reason="assured-return wording appears next to a government / sovereign guarantee (e.g. PPF); a person must decide whether it is the adviser's own promise",
                                checks=checks)
        return fail_from_span(ctx, seg.clause_at(a), reason=f"forbidden claim of assured/guaranteed/risk-free returns: '{text[a:b]}' ({label})",
                              checks=checks, confidence=0.95)
    for grp, why in ((questions, "claim wording appears only inside a question, so it is not clearly an assertion"),
                     (ambiguous, "phrase can imply an assured return but is also used legitimately; a person must decide")):
        if grp:
            a, b = grp[0]
            sa, sb = seg.sentence_at(a)
            qa, qb = tidy_span(text, (sa, sb))
            return make_verdict(card, "review", confidence=0.5, quote=text[qa:qb], span=(qa, qb), reason=why, checks=checks)

    # bare guarantee words not tied to returns
    covered = [(a, b) for a, b, _, _ in kept]
    bare_live = []
    for mt in all_matches([m["bare_guarantee"]], f):
        if any(x <= mt.start() < y for x, y in covered):
            continue
        c = classify(mt.start(), mt.end())
        if c == "live":
            bare_live.append(mt)
        else:
            disclaimers += 1
            checks.append(check_entry("guarantee_word", "pass", f"'{text[mt.start():mt.end()]}': {c}"))
    invest = (any_match(m["invest_cues"], f) is not None) or (str_fact(ctx.facts, "journey") in ("advice", "advertisement")) or bool(
        str_fact(ctx.facts, "product") and any(w in str_fact(ctx.facts, "product") for w in ("invest", "research", "fund", "advice", "equity", "stock", "market")))
    if disclaimers:
        checks.append(check_entry("semantic", "info", "implied guarantees are Tier B not configured"))
        return make_verdict(card, "pass", confidence=0.85,
                            reason="forbidden wording appears only negated, disclaimed or as a warning; no live assured-return claim",
                            checks=checks)
    if bare_live and invest:
        mt = bare_live[0]
        sa, sb = seg.sentence_at(mt.start())
        qa, qb = tidy_span(text, (sa, sb))
        checks.append(check_entry("guarantee_word", "review", f"'{text[mt.start():mt.end()]}' in an investment context but not tied to returns"))
        return make_verdict(card, "review", confidence=0.5, quote=text[qa:qb], span=(qa, qb),
                            reason="the word 'guarantee' appears in an investment context without a clear link to returns: needs a person (or Tier B)",
                            checks=checks)
    if invest:
        checks.append(check_entry("scan", "pass", "no assured-return wording found"))
        checks.append(check_entry("semantic", "info", "implied guarantees are Tier B not configured"))
        return make_verdict(card, "pass", confidence=0.8, reason="no forbidden assured/guaranteed/risk-free return wording found (implied guarantees not checked)", checks=checks)
    return make_verdict(card, "not_applicable", confidence=0.8,
                        reason="text contains no investment, returns or advice wording; the card covers investment advice",
                        checks=[check_entry("topic", "skip", "no investment context")])


# ------------------------------------------------------------------ DPDP-CONSENT-PURPOSE

def check_dpdp(ctx: Ctx) -> dict:
    card, m, f, text, seg = ctx.card, ctx.m, ctx.f, ctx.text, ctx.seg
    if not any_match(m["consent_topic"], f):
        if str_fact(ctx.facts, "journey") in ("onboarding", "consent_capture", "consent_withdrawal"):
            return make_verdict(card, "review", tier=B_TIER, confidence=0.5,
                                reason="facts say this is a consent journey but the text has no recognisable consent wording; Tier B not configured, so a person must review",
                                checks=[check_entry("topic", "review", "consent journey without consent wording")])
        return make_verdict(card, "not_applicable", confidence=0.85, reason="text does not ask for, describe or withdraw consent / personal-data use",
                            checks=[check_entry("topic", "skip", "no consent or personal-data wording")])
    checks: list[dict] = []
    for mt in all_matches(m["withdrawal_forbidden"], f):
        sa, sb = seg.sentence_at(mt.start())
        if any_match(m["forbidden_negation"], f[max(sa, mt.start() - 20):mt.start()]):
            continue
        checks.append(check_entry("withdrawal_wording", "fail", f"forbidden: '{text[mt.start():mt.end()]}'"))
        return fail_from_span(ctx, seg.clause_at(mt.start()), reason="withdrawal of consent is denied or not allowed; s.6(4) requires withdrawal to be comparably easy",
                              checks=checks)
    online = any_match(m["consent_online"], f)
    offline = any_match(m["withdraw_offline_only"], f)
    if online and offline:
        checks.append(check_entry("withdrawal_wording", "fail",
                                  f"consent given online ('{text[online.start():online.end()]}') but withdrawal only offline ('{text[offline.start():offline.end()]}')"))
        return fail_from_span(ctx, seg.clause_at(offline.start()),
                              reason="consent was given online/in-app but withdrawal is offered only by call/visit/post: not comparable in ease",
                              checks=checks, confidence=0.85)
    checks.append(check_entry("withdrawal_wording", "pass", "no forbidden withdrawal wording"))
    for name, pats in m["notice_elements"].items():
        hit = any_match(pats, f)
        checks.append(check_entry(name, "info", f"keyword evidence found: '{text[hit.start():hit.end()]}'" if hit else "no keyword evidence"))
    return make_verdict(card, "review", tier=B_TIER, confidence=0.5,
                        reason="notice completeness (data and purpose, how to exercise rights incl. withdrawal, how to complain to the Board) is a Tier B judgement; Tier B not configured",
                        checks=checks)
