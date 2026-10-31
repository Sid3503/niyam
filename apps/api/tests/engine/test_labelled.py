"""Labelled evaluation of the Tier A engine, plus hard-invariant checks on EVERY labelled case.

Run:   cd apps/api && PYTHONPATH=. python -m pytest tests/engine -q -s
Report only:   cd apps/api && PYTHONPATH=. python tests/engine/test_labelled.py [dev|test|all]

Each JSONL row: {id, split ('dev'|'test'), rule_id, text, facts, expected_verdict, note[, as_of]}.
The TEST split was written before the engine existed and matchers were tuned on DEV only.
Accuracy thresholds below are regression guards, not claims of correctness: see docs/ENGINE.md.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import pytest

from niyam.engine import load_cards, run_checks

HERE = Path(__file__).resolve().parent
LABELLED = HERE / "labelled"
CARDS_DIR = HERE.parents[3] / "rules" / "cards"
DEFAULT_AS_OF = "2026-10-31"
VERDICTS = ["pass", "fail", "review", "not_applicable", "not_yet_enforceable"]
ROW_UNDETERMINED = "cannot determine which RBI TAT row applies"

CARDS = load_cards(CARDS_DIR)


def load_cases() -> list[dict]:
    rows: list[dict] = []
    for p in sorted(LABELLED.glob("*.jsonl")):
        for ln, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                d = json.loads(line)
                d["_src"] = f"{p.name}:{ln}"
                rows.append(d)
    return rows


CASES = load_cases()


def run_case(case: dict, cards=None) -> dict:
    return run_checks(case["text"], case.get("facts"), cards or CARDS,
                      as_of=case.get("as_of") or DEFAULT_AS_OF, rule_ids=[case["rule_id"]])[0]


_RESULTS: dict[str, dict] = {}


def result(case: dict) -> dict:
    if case["id"] not in _RESULTS:
        _RESULTS[case["id"]] = run_case(case)
    return _RESULTS[case["id"]]


# ------------------------------------------------------------------ scoring

def score(split: str | None = None) -> dict:
    """Per rule: n, correct, accuracy, per-verdict confusion, precision/recall of `fail`, failures."""
    out: dict[str, dict] = {}
    for c in CASES:
        if split and c["split"] != split:
            continue
        r = result(c)
        s = out.setdefault(c["rule_id"], {"n": 0, "ok": 0, "conf": defaultdict(Counter), "bad": []})
        s["n"] += 1
        s["conf"][c["expected_verdict"]][r["verdict"]] += 1
        if r["verdict"] == c["expected_verdict"]:
            s["ok"] += 1
        else:
            s["bad"].append((c, r))
    for s in out.values():
        tp = s["conf"]["fail"]["fail"]
        fp = sum(s["conf"][e]["fail"] for e in VERDICTS if e != "fail")
        fn = sum(n for v, n in s["conf"]["fail"].items() if v != "fail")
        s["acc"] = s["ok"] / s["n"]
        s["prec"] = tp / (tp + fp) if tp + fp else None
        s["rec"] = tp / (tp + fn) if tp + fn else None
        s["fail_n"] = tp + fn
    return out


def _pct(x):
    return "  n/a" if x is None else f"{100 * x:4.0f}%"


def format_report(split: str | None, show_failures: bool = False) -> str:
    sc = score(split)
    lines = [f"\n=== split: {split or 'all'} ===",
             f"{'rule':27s} {'n':>3s} {'acc':>5s} {'fail-prec':>9s} {'fail-rec':>8s}  (n_fail)"]
    tot_n = tot_ok = 0
    big = Counter()
    for rule in sorted(sc):
        s = sc[rule]
        tot_n += s["n"]
        tot_ok += s["ok"]
        lines.append(f"{rule:27s} {s['n']:3d} {_pct(s['acc'])} {_pct(s['prec']):>9s} {_pct(s['rec']):>8s}  ({s['fail_n']})")
        for e, row in s["conf"].items():
            for v, n in row.items():
                big[(e, v)] += n
    lines.append(f"{'ALL':27s} {tot_n:3d} {_pct(tot_ok / tot_n if tot_n else None)}")
    lines.append("\nconfusion (rows = expected, cols = got), all rules:")
    lines.append(f"{'':22s}" + "".join(f"{v[:9]:>10s}" for v in VERDICTS))
    for e in VERDICTS:
        lines.append(f"{e:22s}" + "".join(f"{big[(e, v)]:10d}" for v in VERDICTS))
    if show_failures:
        lines.append("\nmismatches:")
        for rule in sorted(sc):
            for c, r in sc[rule]["bad"]:
                lines.append(f"  [{c['id']}] expected={c['expected_verdict']} got={r['verdict']}  text={c['text'][:90]!r}\n"
                             f"      reason: {r['reason'][:160]}")
    return "\n".join(lines)


# ------------------------------------------------------------------ hard invariants (ALL cases)

@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_invariants_every_case(case):
    v = result(case)
    # contract fields
    for k in ("rule_id", "rule_version", "rule_status", "verdict", "tier", "confidence", "quote", "span", "reason", "checks", "source"):
        assert k in v, k
    assert v["rule_id"] == case["rule_id"]
    assert v["rule_status"] == "draft", "engine must echo the card status, never change it"
    assert v["verdict"] in VERDICTS
    assert isinstance(v["confidence"], (int, float)) and 0.0 <= v["confidence"] <= 1.0
    assert isinstance(v["reason"], str) and v["reason"]
    assert "internal engine error" not in v["reason"], v["reason"]
    # a fail carries a verbatim quote and spans that index it
    if v["verdict"] == "fail":
        assert isinstance(v["quote"], str) and v["quote"]
        a, b = v["span"]
        assert 0 <= a < b <= len(case["text"])
        assert case["text"][a:b] == v["quote"]
    else:
        if v["quote"] is not None:
            a, b = v["span"]
            assert case["text"][a:b] == v["quote"]
    # empty / blank text is never a pass
    if not case["text"].strip():
        assert v["verdict"] in ("review", "not_yet_enforceable")
    # a not_yet_enforceable verdict must be justified by the card date
    if v["verdict"] == "not_yet_enforceable":
        card = next(c for c in CARDS if c["id"] == case["rule_id"])
        assert date.fromisoformat(card["effective_from"]) > date.fromisoformat(case.get("as_of") or DEFAULT_AS_OF)


def test_determinism_all_cases():
    for c in CASES:
        a = json.dumps(run_case(c), sort_keys=True, ensure_ascii=False)
        b = json.dumps(run_case(c), sort_keys=True, ensure_ascii=False)
        assert a == b, c["id"]


def test_determinism_batch_and_order():
    c = next(x for x in CASES if x["rule_id"] == "RBI-TAT-UPI-MERCHANT")
    a = run_checks(c["text"], c["facts"], CARDS, as_of=DEFAULT_AS_OF)
    b = run_checks(c["text"], c["facts"], list(reversed(CARDS)), as_of=DEFAULT_AS_OF)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True), "result must not depend on card order"


def test_blank_text_never_passes_any_card():
    for blank in ("", " ", "\n\t  ", " ​"):
        for as_of in ("2026-10-31", "2027-06-01"):
            for facts in (None, {"transaction_type": "upi_merchant", "delay_days": 9, "convenience_fee_shown": False,
                                 "complaint_state": {"rejected": True}, "product": "digital lending"}):
                for v in run_checks(blank, facts, CARDS, as_of=as_of):
                    assert v["verdict"] in ("review", "not_yet_enforceable", "not_applicable"), (v["rule_id"], blank, v["verdict"])
                    assert v["verdict"] != "pass" and v["verdict"] != "fail"


# transfer-vs-merchant guard: independent list of words that count as 'clear' row cues
_CLEAR_CUES = re.compile(
    r"merchant|shop|store|\bqr\b|scan|retailer|vendor|seller|checkout|commerce|online (order|purchase|shopping)|paid at|pos |dukaan|dukan|restaurant|petrol|"
    r"friend|family|relative|send money|money transfer|transfer|sent to|send to|paid to|p2p|peer|brother|sister|mother|father|mom|dad|wife|husband|cousin|dost|bhai|recipient|"
    r"दुकान|मर्चेंट|मर्चेण्ट|व्यापारी|विक्रेता|दोस्त|भाई|रिश्तेदार|परिवार", re.I)


def test_transfer_vs_merchant_guard_on_all_labelled_texts():
    """Without facts about the row and without a clear text cue, a TAT card may only review / not_applicable."""
    tat = ["RBI-TAT-UPI-TRANSFER", "RBI-TAT-UPI-MERCHANT"]
    n = 0
    for c in CASES:
        if c["rule_id"] not in tat or not c["text"].strip():
            continue
        if _CLEAR_CUES.search(c["text"]):
            continue
        facts = {k: v for k, v in (c.get("facts") or {}).items() if k not in ("transaction_type", "journey")}
        for v in run_checks(c["text"], facts, CARDS, as_of=DEFAULT_AS_OF, rule_ids=tat):
            n += 1
            assert v["verdict"] in ("review", "not_applicable"), (c["id"], v["rule_id"], v["verdict"], v["reason"])
            if v["verdict"] == "review" and "cannot determine" in v["reason"]:
                assert v["reason"] == ROW_UNDETERMINED
    assert n >= 40


def test_row_cannot_be_guessed_from_thin_evidence():
    thin = ["Your payment will be reversed within 5 days.", "The refund will arrive by T+1.", "It will be back tonight.",
            "Raise a complaint to get your money back.", "आपका पैसा 7 दिन में वापस आएगा।"]
    for t in thin:
        for v in run_checks(t, None, CARDS, as_of=DEFAULT_AS_OF,
                            rule_ids=["RBI-TAT-UPI-TRANSFER", "RBI-TAT-UPI-MERCHANT"]):
            assert v["verdict"] == "review" and v["reason"] == ROW_UNDETERMINED, (t, v["rule_id"], v["verdict"], v["reason"])


def test_facts_transaction_type_selects_the_row():
    t = "Your refund will arrive by T+1."
    tr = run_checks(t, {"transaction_type": "upi_transfer"}, CARDS, as_of=DEFAULT_AS_OF, rule_ids=["RBI-TAT-UPI-TRANSFER"])[0]
    me = run_checks(t, {"transaction_type": "upi_merchant"}, CARDS, as_of=DEFAULT_AS_OF, rule_ids=["RBI-TAT-UPI-MERCHANT"])[0]
    assert tr["verdict"] == "pass"
    assert me["verdict"] == "fail" and "T+1" in me["quote"]
    assert run_checks(t, {"transaction_type": "upi_merchant"}, CARDS, as_of=DEFAULT_AS_OF, rule_ids=["RBI-TAT-UPI-TRANSFER"])[0]["verdict"] == "not_applicable"


# ------------------------------------------------------------------ scores

# Regression guards on DEV (matchers were tuned there) and a deliberately lower floor on TEST.
# These numbers are guards against silent regressions, not a quality claim.
DEV_FLOOR = 0.90
TEST_FLOOR = 0.70


def test_corpus_size_requirements():
    by = Counter(c["rule_id"] for c in CASES)
    for rule in ("RBI-TAT-UPI-TRANSFER", "RBI-TAT-UPI-MERCHANT", "SEBI-NO-ASSURED-RETURNS", "NPCI-UPI-MASK-IDENTIFIERS"):
        assert by[rule] >= 40, (rule, by[rule])
    for card in CARDS:
        assert by[card["id"]] >= 15, (card["id"], by[card["id"]])
    sp = Counter(c["split"] for c in CASES)
    assert 0.35 <= sp["test"] / len(CASES) <= 0.45, sp
    assert len({c["id"] for c in CASES}) == len(CASES)
    for c in CASES:
        assert c["split"] in ("dev", "test") and c["expected_verdict"] in VERDICTS


def test_report_and_floors(capsys):
    with capsys.disabled():
        for sp in ("dev", "test"):
            print(format_report(sp, show_failures=True))
    for sp, floor in (("dev", DEV_FLOOR), ("test", TEST_FLOOR)):
        sc = score(sp)
        n = sum(s["n"] for s in sc.values())
        ok = sum(s["ok"] for s in sc.values())
        assert ok / n >= floor, f"{sp} accuracy {ok / n:.3f} below floor {floor}"


if __name__ == "__main__":
    import sys
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for sp in (["dev", "test"] if which == "all" else [which]):
        print(format_report(sp, show_failures=True))
