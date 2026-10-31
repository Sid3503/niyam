"""Document-review logic: clause offsets, product-fact checks, missing disclosures. No database needed."""
import os
from pathlib import Path

os.environ.setdefault("NIYAM_DATA_ROOT", str(Path(__file__).resolve().parents[3]))

from niyam.review import claims
from niyam.review.segment import parse_front_matter, segment, sentences


def _hits(text):
    out = []
    for c in segment(text):
        out += claims.check_clause(c)
    return out


def test_offsets_index_the_content_exactly():
    body = "# H\n\n1.2 Your settlement is guaranteed within two hours. Next.\n\n- Instant settlement 24x7.\n"
    for c in segment(body):
        assert body[c.start:c.end] == c.text
        for a, b, t in sentences(c):
            assert body[a:b] == t
    assert segment(body)[0].locator == "§1.2" and not sentences(segment(body)[0])[0][2].startswith("1.2")


def test_guaranteed_two_hours_contradicts_the_fact():
    h = _hits("1.2 Your settlement is guaranteed within two hours of every payment.")
    assert [x.status for x in h] == ["contradiction"] and h[0].fact_id == "PF-PG-SETTLEMENT" and h[0].severity == "critical"


def test_t2_current_t3_outdated_t1_needs_condition():
    assert _hits("Settlements follow a T+2 business-day cycle.")[0].status == "current"
    assert _hits("Settlements are processed on a T+3 cycle.")[0].status == "outdated"
    assert _hits("Settlement happens on T+1.")[0].status == "review"


def test_fees_current_outdated_contradiction():
    assert _hits("Domestic cards are charged an MDR of 1.90% plus applicable GST.")[0].status == "current"
    assert _hits("Domestic cards are charged an MDR of 2.25% plus GST.")[0].status == "outdated"
    assert _hits("UPI payments are charged 0.5% per transaction.")[0].status == "contradiction"


def test_kyc_waiver_is_critical_and_not_duplicated():
    h = _hits("Guaranteed approval in 24 hours with no KYC hassles.")
    assert len(h) == 1 and h[0].severity == "critical"


def test_unverifiable_text_yields_no_current():
    assert _hits("We value your business and look forward to working with you.") == []


def test_missing_disclosures_by_document_type():
    ids = {d["id"] for d in claims.missing_disclosures("agreement", "This agreement is governed by Indian law.")}
    assert {"DISC-GRIEVANCE", "DISC-KYC", "DISC-SETTLEMENT-REF", "DISC-FEES-REF"} <= ids
    assert not claims.missing_disclosures("agreement", "grievance redressal officer. KYC. settlement cycle. fee schedule.")


def test_approved_wording_passes_its_own_checks():
    for f in claims.load_facts()["facts"]:
        assert claims.validate_wording(f["id"], f["approved_wording"]), f["id"]


def test_front_matter():
    meta, body = parse_front_matter("---\ntitle: X\nowner: a@b\n---\n# Body\n")
    assert meta == {"title": "X", "owner": "a@b"} and body.startswith("# Body")
