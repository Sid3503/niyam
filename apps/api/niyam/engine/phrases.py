"""Phrase-level detectors shared by several predicates (complaint-required, compensation, escalation)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .common import Ctx, Finding, all_matches, any_match


def find_complaint_required(ctx: Ctx, m: dict) -> list[Finding]:
    """Customer told to raise a complaint / ticket / claim.

    fail  = instruction not negated, not done by the agent, not an escalation route, and
            tied to a reversal / refund / compensation in the same sentence
    review = instruction present but its link to the reversal is unclear
    (negated forms, 'I have raised a ticket on your behalf', 'if not credited, escalate'
    are not findings)."""
    f, seg = ctx.f, ctx.seg
    out: list[Finding] = []
    seen_end = -1
    for mt in all_matches(m["complaint_instruction"], f):
        if mt.start() < seen_end:
            continue
        seen_end = mt.end()
        sa, sb = seg.sentence_at(mt.start())
        around = f[max(sa, mt.start() - 30):min(sb, mt.end() + 25)]
        if any_match(m["complaint_agent_done"], around):
            continue
        if any_match(m["complaint_negation"], f[max(sa, mt.start() - 45):mt.start()]):
            continue
        if any_match(m["complaint_negation_after"], f[mt.end():min(sb, mt.end() + 40)]):
            continue
        sent = f[sa:sb]
        if any_match(m["escalation_context"], sent):
            continue
        ca, cb = seg.clause_at(mt.start())
        span = (ca, cb)
        if any_match(m["reversal_words"], sent) or any_match(m["precondition_cues"], sent):
            out.append(Finding("fail", "complaint_required",
                               "customer is told to raise a complaint/ticket/claim to get the reversal or compensation",
                               span, prio=1))
        else:
            out.append(Finding("review", "complaint_required",
                               "customer is told to raise a complaint/ticket/claim; link to the reversal is unclear",
                               span, prio=3))
    return out


def has_compensation_cue(ctx: Ctx, m: dict):
    return any_match(m["compensation_cues"], ctx.f)


@dataclass
class CompElements:
    """What the reply says about the Rs100/day delay compensation (single predicate shared by
    RBI-TAT-COMP-100 and the two RBI-TAT-UPI-* cards so they cannot disagree about one sentence)."""
    mentioned: bool = False
    amount_per_day: bool = False
    automatic: bool = False
    amount_spans: list = field(default_factory=list)
    wrong_amount: tuple | None = None

    @property
    def complete(self) -> bool:
        return self.amount_per_day and self.automatic


def comp_elements(ctx: Ctx, m: dict) -> CompElements:
    f, seg = ctx.f, ctx.seg
    out = CompElements(mentioned=any_match(m["compensation_cues"], f) is not None)
    sents = [(a, b) for a, b in seg.sentences]
    # a sentence, or two adjacent sentences, may carry the amount and the 'per day' wording
    windows = [(a, b) for a, b in sents] + [(sents[i][0], sents[i + 1][1]) for i in range(len(sents) - 1)]
    for sa, sb in windows:
        s = f[sa:sb]
        a100 = any_match(m["amount_100"], s)
        pday = any_match(m["per_day"], s)
        if a100 and pday:
            out.amount_per_day = True
            out.amount_spans.append((sa, sb))
        elif pday and not a100:
            mm = any_match(m["amount_any"], s)
            if mm and out.wrong_amount is None:
                out.wrong_amount = (mm.group(0), (sa, sb))
    for sa, sb in sents:
        s = f[sa:sb]
        if any_match(m["automatic"], s) and not any_match(m["not_automatic"], s):
            out.automatic = True
    if out.amount_per_day:
        out.wrong_amount = None
    return out
