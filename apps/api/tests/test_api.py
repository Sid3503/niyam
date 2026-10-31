import pytest
from fastapi.testclient import TestClient

from niyam.main import app

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_and_ready(client):
    assert client.get("/healthz").json() == {"ok": True}
    assert client.get("/readyz").json()["ok"] is True


def test_all_cards_are_draft_and_quotes_verified(client):
    rules = client.get("/api/v1/rules").json()
    assert len(rules) >= 10
    assert all(r["status"] == "draft" for r in rules)             # nothing is approved: the API must never imply otherwise
    assert all(r["quotes_verified"] for r in rules)


def test_dpdp_card_is_not_yet_enforceable_at_default_date(client):
    r = client.get("/api/v1/rules", params={"as_of": "2026-10-31"}).json()
    dpdp = next(x for x in r if x["id"] == "DPDP-CONSENT-PURPOSE")
    assert dpdp["enforceability"] == "not_yet_enforceable"
    assert next(x for x in client.get("/api/v1/rules", params={"as_of": "2027-06-01"}).json() if x["id"] == "DPDP-CONSENT-PURPOSE")["enforceability"] == "live"


def test_rule_detail_has_validation_and_unknown_is_404_with_error_shape(client):
    d = client.get("/api/v1/rules/RBI-TAT-UPI-MERCHANT").json()
    assert d["check"]["config"]["deadline_days"] == 5 and d["validation"]["quotes_verified"]
    r = client.get("/api/v1/rules/NOPE")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_search_finds_merchant_row_first_with_marked_snippet(client):
    h = client.get("/api/v1/kb/search", params={"q": "payment to merchant confirmation not received auto-reversal T+5", "limit": 5}).json()["hits"]
    assert h and "T + 5" in h[0]["text"] and "<mark>" in h[0]["snippet"]
    assert len({x["text"] for x in h}) == len(h)                  # duplicate copies collapse


def test_surfaces_excluded_from_default_search_and_marked(client):
    hits = client.get("/api/v1/kb/search", params={"q": "Paytm wallet add money charges"}).json()["hits"]
    assert all(h["corpus_kind"] == "regulation" for h in hits)
    s = client.get("/api/v1/kb/search", params={"q": "wallet add money charges", "corpus_kind": "surface"}).json()["hits"]
    assert s and all(h["regulator"] == "Paytm" for h in s)


def test_ocr_documents_are_flagged(client):
    docs = client.get("/api/v1/kb/documents", params={"q": "oc234"}).json()
    assert docs and docs[0]["text_basis"] == "ocr"


def test_unit_has_neighbours_and_bad_ids_404(client):
    hit = client.get("/api/v1/kb/search", params={"q": "cooling-off period digital loan"}).json()["hits"][0]
    u = client.get(f"/api/v1/kb/units/{hit['unit_id']}").json()
    assert u["text"] and (u["prev"] or u["next"])
    assert client.get("/api/v1/kb/units/not-a-uuid").status_code == 404


def test_check_rejects_oversized_text_and_unknown_rule(client):
    assert client.post("/api/v1/check", json={"text": "x" * 20_001}).status_code in (422, 503)
    r = client.post("/api/v1/check", json={"text": "hi", "rule_ids": ["NOPE"]})
    assert r.status_code in (422, 503)


def test_api_key_enforced_when_configured(monkeypatch):
    from niyam.config import get_settings
    monkeypatch.setattr(get_settings(), "api_key", "secret-key")
    with TestClient(app) as c:
        assert c.get("/api/v1/rules").status_code == 401
        assert c.get("/api/v1/rules", headers={"X-API-Key": "wrong"}).status_code == 401
        assert c.get("/api/v1/rules", headers={"X-API-Key": "secret-key"}).status_code == 200
        assert c.get("/healthz").status_code == 200                   # probes stay open
