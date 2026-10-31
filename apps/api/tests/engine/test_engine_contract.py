"""Contract tests: verdict shape, enforceability, rule selection, tier strings, scope gating, card immutability."""
from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path

import pytest

from niyam.engine import load_cards, run_checks

CARDS_DIR = Path(__file__).resolve().parents[4] / "rules" / "cards"
CARDS = load_cards(CARDS_DIR)
IDS = [c["id"] for c in CARDS]


def one(rule, text, facts=None, as_of="2026-10-31"):
    return run_checks(text, facts, CARDS, as_of=as_of, rule_ids=[rule])[0]


def test_load_cards_returns_ten_draft_cards():
    assert len(CARDS) == 10 and {c["status"] for c in CARDS} == {"draft"}


def test_all_cards_one_verdict_each_sorted_and_complete():
    vs = run_checks("hello", None, CARDS, as_of="2026-10-31")
    assert [v["rule_id"] for v in vs] == sorted(IDS)
    for v in vs:
        assert set(v) == {"rule_id", "rule_version", "rule_status", "verdict", "tier", "confidence", "quote", "span", "reason", "checks", "source"}
        assert set(v["source"]) >= {"document", "reference", "locator", "file", "quote"}
        assert all(set(c) == {"name", "result", "detail"} for c in v["checks"])


def test_tier_strings_are_clean():
    """API/DB store tier as 'A' | 'B' | 'A+B'; 'not configured' wording belongs in reason."""
    texts = [("hello", None), ("Key Fact Statement. Your KFS is attached.", {"journey": "loan_offer"}),
             ("We will use your data. You may withdraw consent in settings.", None), ("Complaint rejected.", {"complaint_state": {"rejected": True}})]
    seen = set()
    for t, f in texts:
        for as_of in ("2026-10-31", "2027-06-01"):
            for v in run_checks(t, f, CARDS, as_of=as_of):
                assert v["tier"] in ("A", "B", "A+B"), v["tier"]
                seen.add(v["tier"])
                if v["tier"] == "B" and v["verdict"] == "review":
                    assert "Tier B" in v["reason"] and "not configured" in v["reason"], v["reason"]
    assert "B" in seen


def test_tier_b_abstention_is_review_with_tier_b():
    v = one("DPDP-CONSENT-PURPOSE", "We use your phone number. Withdraw consent in settings.", None, as_of="2027-06-01")
    assert (v["verdict"], v["tier"]) == ("review", "B")
    v = one("RBI-KFS-LOAN", "We will share the KFS soon.", {"journey": "loan_application"})
    assert (v["verdict"], v["tier"]) == ("review", "B")


def test_default_as_of_dpdp_not_yet_enforceable_until_effective_date():
    v = run_checks("You cannot withdraw consent.", None, CARDS, rule_ids=["DPDP-CONSENT-PURPOSE"])[0]
    if date.today() < date(2027, 5, 13):
        assert v["verdict"] == "not_yet_enforceable"
    else:
        assert v["verdict"] == "fail"
    assert one("DPDP-CONSENT-PURPOSE", "x consent", None, "2027-05-12")["verdict"] == "not_yet_enforceable"
    assert one("DPDP-CONSENT-PURPOSE", "x consent", None, date(2027, 5, 13))["verdict"] == "review"


def test_as_of_accepts_date_and_iso_string():
    a = run_checks("It will be back tonight", {"transaction_type": "upi_merchant"}, CARDS, as_of=date(2026, 10, 31))
    b = run_checks("It will be back tonight", {"transaction_type": "upi_merchant"}, CARDS, as_of="2026-10-31")
    assert a == b


def test_rule_ids_filter_and_unknown_id():
    vs = run_checks("hi", None, CARDS, as_of="2026-10-31", rule_ids=["SEBI-NO-ASSURED-RETURNS", "RBI-KFS-LOAN"])
    assert sorted(v["rule_id"] for v in vs) == ["RBI-KFS-LOAN", "SEBI-NO-ASSURED-RETURNS"]
    with pytest.raises(ValueError):
        run_checks("hi", None, CARDS, rule_ids=["NOPE"])


def test_engine_never_mutates_cards_or_status():
    before = copy.deepcopy(CARDS)
    run_checks("The refund will be back tonight 9876543210", {"transaction_type": "upi_merchant", "delay_days": 9}, CARDS, as_of="2027-06-01")
    assert CARDS == before


def test_non_active_cards_skipped_by_default_but_run_when_asked():
    c = copy.deepcopy(CARDS)
    for x in c:
        if x["id"] == "RBI-KFS-LOAN":
            x["status"] = "retired"
    assert "RBI-KFS-LOAN" not in [v["rule_id"] for v in run_checks("hi", None, c, as_of="2026-10-31")]
    v = run_checks("hi", None, c, as_of="2026-10-31", rule_ids=["RBI-KFS-LOAN"])[0]
    assert v["rule_status"] == "retired"


def test_missing_matchers_abstains():
    c = copy.deepcopy(CARDS)
    for x in c:
        if x["id"] == "SEBI-NO-ASSURED-RETURNS":
            del x["check"]["config"]["matchers"]
    v = run_checks("guaranteed returns", None, c, as_of="2026-10-31", rule_ids=["SEBI-NO-ASSURED-RETURNS"])[0]
    assert v["verdict"] == "review" and v["tier"] == "B"


def test_facts_robustness_garbage_inputs_do_not_crash():
    for facts in ({"delay_days": "x"}, {"delay_days": True}, {"complaint_state": "bad"}, {"product": 5}, {"transaction_type": 7}, "notadict", []):
        for v in run_checks("The refund will arrive in 5 days. 9876543210", facts, CARDS, as_of="2027-06-01"):
            assert "internal engine error" not in v["reason"]


def test_json_serialisable():
    json.dumps(run_checks("Guaranteed returns! call 9876543210", None, CARDS, as_of="2027-06-01"), ensure_ascii=False)


# ---- cross-card agreement on the compensation sentence (coordinator bug 1)
SENTENCES = [
    "The beneficiary bank must reverse it by T+1. For each extra day, ₹100 is credited automatically, no complaint needed.",
    "Compensation applies for the delay.",
    "You get ₹100 per day, but you must raise a claim.",
    "₹100 per day of delay, automatically.",
    "Please wait while we check.",
]


@pytest.mark.parametrize("text", SENTENCES)
@pytest.mark.parametrize("tt,delay", [("upi_transfer", 3), ("upi_merchant", 8)])
def test_comp_and_tat_cards_agree_on_compensation(text, tt, delay):
    facts = {"transaction_type": tt, "delay_days": delay}
    tat = "RBI-TAT-UPI-TRANSFER" if tt == "upi_transfer" else "RBI-TAT-UPI-MERCHANT"
    a, b = one("RBI-TAT-COMP-100", text, facts), one(tat, text, facts)
    tat_comp = [c for c in b["checks"] if c["name"] == "compensation"]
    assert len(tat_comp) == 1
    assert (a["verdict"] == "pass") == (tat_comp[0]["result"] == "pass"), (a["reason"], tat_comp)


# ---- scope gating audit (coordinator bug 2): facts say the card applies, text has no cue => review, never not_applicable
@pytest.mark.parametrize("rule,facts,as_of", [
    ("RBI-COOLING-OFF", {"product": "digital lending", "journey": "loan_cancellation"}, "2026-10-31"),
    ("RBI-COOLING-OFF", {"product": "pay later", "journey": "prepayment"}, "2026-10-31"),
    ("RBI-KFS-LOAN", {"journey": "loan_offer"}, "2026-10-31"),
    ("RBI-KFS-LOAN", {"product": "personal loan"}, "2026-10-31"),
    ("RBI-TAT-UPI-TRANSFER", {"transaction_type": "upi_transfer"}, "2026-10-31"),
    ("RBI-TAT-UPI-MERCHANT", {"transaction_type": "upi_merchant"}, "2026-10-31"),
    ("RBI-TAT-UPI-MERCHANT", {"journey": "merchant_payment"}, "2026-10-31"),
    ("RBI-TAT-COMP-100", {"transaction_type": "upi_merchant", "delay_days": 9}, "2026-10-31"),
    ("NPCI-UPI-CHARGES-PRE", {"journey": "checkout"}, "2026-10-31"),
    ("DPDP-CONSENT-PURPOSE", {"journey": "consent_capture"}, "2027-06-01"),
    ("RBI-OMB-ESCALATION", {"product": "digital lending", "journey": "complaint"}, "2026-10-31"),
])
def test_facts_say_applies_but_no_text_cue_is_not_not_applicable(rule, facts, as_of):
    v = one(rule, "Thank you, we will help you.", facts, as_of)
    assert v["verdict"] != "not_applicable", (rule, v["reason"])
    assert v["verdict"] in ("review", "fail"), (rule, v["verdict"])


def test_cooling_off_denial_without_keywords_fails():
    v = one("RBI-COOLING-OFF", "Once the money is in your account the loan is final, there is no way out of it.",
            {"product": "digital lending", "journey": "loan_cancellation"})
    assert v["verdict"] == "fail" and v["quote"] in "Once the money is in your account the loan is final, there is no way out of it."
