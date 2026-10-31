"""run_checks: applies enforceability, blank-text and scope gates, then the card's Tier A predicate."""
from __future__ import annotations

from datetime import date, datetime
from typing import Callable

from .common import Ctx, Segments, check_entry, finalize, fold, is_blank, make_verdict, matchers, str_fact
from .lending import check_cooling, check_kfs, check_omb
from .payments import check_charges, check_comp100, check_mask
from .sebi import check_dpdp, check_sebi
from .tat import check_tat

PREDICATES: dict[str, Callable[[Ctx], dict]] = {
    "RBI-TAT-UPI-TRANSFER": check_tat,
    "RBI-TAT-UPI-MERCHANT": check_tat,
    "RBI-TAT-COMP-100": check_comp100,
    "RBI-KFS-LOAN": check_kfs,
    "RBI-COOLING-OFF": check_cooling,
    "NPCI-UPI-CHARGES-PRE": check_charges,
    "DPDP-CONSENT-PURPOSE": check_dpdp,
    "RBI-OMB-ESCALATION": check_omb,
    "SEBI-NO-ASSURED-RETURNS": check_sebi,
    "NPCI-UPI-MASK-IDENTIFIERS": check_mask,
}
_INACTIVE = {"superseded", "retired", "rejected"}


def _as_date(v) -> date:
    if v is None:
        return date.today()
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))


def _scope_mismatch(card: dict, facts: dict) -> str | None:
    sc = card.get("scope", {}) or {}
    surface = str_fact(facts, "surface")
    if surface and sc.get("surfaces") and surface not in [s.lower() for s in sc["surfaces"]]:
        return f"surface '{surface}' is outside this card's scope {sc['surfaces']}"
    journey = str_fact(facts, "journey")
    if journey and sc.get("journeys") and journey not in [j.lower() for j in sc["journeys"]]:
        return f"journey '{journey}' is outside this card's scope {sc['journeys']}"
    product = str_fact(facts, "product")
    prods = [p.lower() for p in sc.get("products", [])]
    if product and prods and not any(p.startswith("all ") for p in prods):
        if not any(p in product or product in p for p in prods):
            return f"product '{product}' is outside this card's scope {sc['products']}"
    return None


def _run_one(card: dict, text: str, facts: dict, as_of: date) -> dict:
    tier = card["check"].get("tier", "A")
    eff = date.fromisoformat(card["effective_from"])
    if eff > as_of:
        return make_verdict(card, "not_yet_enforceable", tier=tier, confidence=1.0,
                            reason=f"effective_from {eff.isoformat()} is after as_of {as_of.isoformat()}",
                            checks=[check_entry("enforceability", "skip", f"effective_from={eff.isoformat()} as_of={as_of.isoformat()}")])
    et = card.get("effective_to")
    if et and date.fromisoformat(et) < as_of:
        return make_verdict(card, "not_applicable", tier=tier, confidence=1.0,
                            reason=f"card ended on {et}, before as_of {as_of.isoformat()}", checks=[])
    if is_blank(text):
        return make_verdict(card, "review", tier="A", confidence=1.0,
                            reason="empty or blank text: no evidence to check, so a person must review",
                            checks=[check_entry("evidence", "review", "text is empty")])
    mm = _scope_mismatch(card, facts)
    if mm:
        return make_verdict(card, "not_applicable", tier="A", confidence=1.0, reason=mm,
                            checks=[check_entry("scope", "skip", mm)])
    fn = PREDICATES.get(card["id"])
    m = matchers(card)
    if fn is None or not m:
        return make_verdict(card, "review", tier="B", confidence=0.0,
                            reason="no Tier A matchers are configured for this card; Tier B not configured, so a person must review",
                            checks=[check_entry("matchers", "review", "missing predicate or check.config.matchers")])
    f = fold(text)
    ctx = Ctx(card=card, text=text, f=f, facts=facts, seg=Segments(f), m=m)
    try:
        return fn(ctx)
    except Exception as exc:                      # never let one card break the batch; surface it
        return make_verdict(card, "review", tier="A", confidence=0.0,
                            reason=f"internal engine error ({type(exc).__name__}: {exc}); a person must review",
                            checks=[check_entry("engine", "review", "exception in predicate")])


def run_checks(text, facts: dict | None, cards: list[dict], as_of=None, rule_ids: list[str] | None = None) -> list[dict]:
    """Run Tier A checks. Returns one Verdict dict per selected card (in card-id order).

    * ``rule_ids`` given: exactly those cards (ValueError on an unknown id; retired/superseded
      cards run too, echoing their status).
    * ``rule_ids`` None: every card that is not retired/superseded/rejected.
    * ``as_of`` defaults to today's date; a card whose effective_from is later yields
      ``not_yet_enforceable``.
    """
    if text is None:
        text = ""
    if not isinstance(text, str):
        text = str(text)
    facts = dict(facts) if isinstance(facts, dict) else {}
    as_of_d = _as_date(as_of)
    by_id = {c["id"]: c for c in cards}
    if rule_ids is not None:
        unknown = [r for r in rule_ids if r not in by_id]
        if unknown:
            raise ValueError(f"unknown rule_id(s): {unknown}")
        chosen = [by_id[r] for r in dict.fromkeys(rule_ids)]
    else:
        chosen = [c for c in cards if c.get("status") not in _INACTIVE]
    chosen = sorted(chosen, key=lambda c: (c["id"], c["version"]))
    return [finalize(text, _run_one(c, text, facts, as_of_d)) for c in chosen]
