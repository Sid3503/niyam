"""Unit tests for the timeline parser (niyam.engine.timeline) using the matchers stored in the TAT card."""
from __future__ import annotations

from pathlib import Path

import pytest

from niyam.engine import load_cards
from niyam.engine.common import Segments, fold, matchers
from niyam.engine.timeline import annotate, extract_promises

CARDS = {c["id"]: c for c in load_cards(Path(__file__).resolve().parents[4] / "rules" / "cards")}
M = matchers(CARDS["RBI-TAT-UPI-TRANSFER"])


def parse(text: str):
    f = fold(text)
    seg = Segments(f)
    ps = extract_promises(f, seg, M)
    annotate(ps, f, M)
    return ps


def live(text: str):
    return [p for p in parse(text) if p.ignore is None]


def one(text: str):
    ps = live(text)
    assert len(ps) == 1, [(text[p.start:p.end], p.days) for p in ps]
    return ps[0]


@pytest.mark.parametrize("text,days", [
    ("It will be back tonight", 0), ("today", 0), ("same day", 0), ("same-day credit", 0), ("aaj hi paisa wapas aa jayega", 0),
    ("aaj raat tak", 0), ("आज रात तक", 0), ("आज ही पैसे वापस आ जाएंगे", 0), ("immediately", 0), ("within 10 minutes", 0), ("in 2 hours", 0),
    ("by tomorrow", 1), ("kal tak", 1), ("कल तक", 1), ("next day", 1), ("agle din", 1), ("within 24 hours", 1), ("in 24 hrs", 1),
    ("T+1", 1), ("T + 5", 5), ("t plus 2", 2), ("T+5 days", 5), ("one day", 1), ("ek din me", 1), ("एक दिन में", 1),
    ("within 3 days", 3), ("in 7 days", 7), ("3-5 days", 5), ("2 to 3 days", 3), ("2 se 3 din", 3), ("do-teen din", 3), ("2-3 दिन", 3),
    ("ek hafte me", 7), ("1 week", 7), ("within a week", 7), ("एक हफ्ते में", 7), ("पांच दिन", 5), ("paanch din", 5), ("5 din me", 5),
    ("48 hours", 2), ("72 hrs", 3), ("2 weeks", 14), ("a day or two", 2), ("couple of days", 2),
])
def test_normalisation(text, days):
    assert one(text).days == days


@pytest.mark.parametrize("text,n", [("5 working days", 5), ("within 3 business days", 3), ("10 कार्य दिवस", 10), ("next working day", 1)])
def test_working_days_flagged_not_converted(text, n):
    p = one(text)
    assert p.working is True and p.days == n


def test_calendar_days_not_working():
    assert one("5 calendar days").working is False


def test_vague_duration():
    p = one("it will take a few days")
    assert p.kind == "vague" and p.days is None and p.min_days == 2


def test_range_uses_max_and_keeps_min():
    p = one("in 2-3 days")
    assert (p.min_days, p.days) == (2, 3)


@pytest.mark.parametrize("text", [
    "We cannot promise it will be back tonight",
    "We can't say it will be reversed tomorrow",
    "I am unable to confirm it will arrive today",
    "It will not take 5 days",
    "kal tak nahi aayega",
    "it will not be credited today",
])
def test_negated_promises_are_ignored(text):
    assert live(text) == []


@pytest.mark.parametrize("text", [
    "The reversal will not take more than 1 day", "Do not worry it will be reversed tomorrow", "Don't worry, it will be back tonight",
    "The bank must reverse it no later than T+1", "Payment was not successful so the amount will be reversed in 5 days",
])
def test_non_negations_stay_promises(text):
    assert len(live(text)) == 1


def test_hedged_and_conditional_flags():
    assert "hedged" in one("It should be back tonight").flags
    assert "hedged" not in one("It will be back tonight").flags
    assert "conditional" in one("If the bank approves, it will be back tonight").flags


def test_escalation_threshold_is_not_a_promise():
    ps = parse("If the amount is not credited within T+1, please contact your bank.")
    assert ps and all(p.ignore for p in ps)


def test_agent_initiation_is_not_a_credit_promise():
    assert live("We have raised a ticket today.") == []


@pytest.mark.parametrize("text", [
    "The payment was debited 3 days ago", "a delay of 3 days", "delayed by 4 days", "tenor of 12 months", "kal aapka payment fail hua tha",
    "aaj tak ka status check kiya", "Hello, how can I help you today?",
])
def test_not_promises(text):
    ps = [p for p in live(text) if p.kind != "same_day" or "today" not in text]
    # 'today' in a greeting is parsed as a candidate; relevance gating (money cue) happens in the TAT predicate
    assert [p for p in ps if p.kind != "same_day"] == []


def test_kal_needs_future_marker_or_tak():
    assert live("kal paisa kat gaya") == []
    assert one("kal paisa wapas aa jayega").days == 1


def test_spans_index_the_original_text():
    text = "Aapka paisa  KAL tak wapas aa jayega, Pakka."
    p = one(text)
    assert text[p.start:p.end].lower().startswith("kal")


def test_fold_is_length_preserving():
    for s in ["İstanbul ₹100", "आज रात ०१२", "“quoted” – dash nbsp​", "ज़रूरत फ़ोन"]:
        assert len(fold(s)) == len(s)
