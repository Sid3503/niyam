import os
from pathlib import Path

os.environ.setdefault("NIYAM_DATA_ROOT", str(Path(__file__).resolve().parents[3]))
from niyam.config import get_settings
from niyam.llm import ollama, router
from niyam.review import circulars


def _with(monkeypatch, **kw):
    s = get_settings()
    for k, v in kw.items():
        monkeypatch.setattr(s, k, v)


def test_auto_prefers_ollama_then_sarvam_then_none(monkeypatch):
    _with(monkeypatch, llm_provider="auto", ollama_api_key="o", sarvam_api_key="s")
    assert router.provider_name() == "ollama"
    _with(monkeypatch, ollama_api_key=None)
    assert router.provider_name() == "sarvam"
    _with(monkeypatch, sarvam_api_key=None)
    assert router.provider_name() is None and not router.configured()


def test_explicit_provider_is_respected(monkeypatch):
    _with(monkeypatch, llm_provider="sarvam", ollama_api_key="o", sarvam_api_key="s")
    assert router.provider_name() == "sarvam"
    _with(monkeypatch, llm_provider="sarvam", sarvam_api_key=None)
    assert router.provider_name() is None          # an explicit choice never silently switches vendor


def test_circular_cleaning_fills_missing_fields():
    r = circulars._clean({"quote": "A shall not B.", "title": ""})
    assert r["severity"] == "medium" and r["claim_keywords"] == [] and r["obligation_type"] == "must_not_claim" and r["title"]


def test_circular_focus_keeps_short_text_and_trims_long_with_exact_slices():
    assert circulars.focus("short text", "x") == ("short text", False)
    para = "The payment aggregator shall disclose all settlement fees to the merchant before onboarding begins.\n\n"
    long_text = ("Filler paragraph that has no duty in it at all and is just padding. " * 5 + "\n\n") * 400 + para * 3
    snip, trimmed = circulars.focus(long_text, "payment settlement")
    assert trimmed and len(snip) <= circulars.MAX_CHARS and "shall disclose" in snip
    assert all(p in long_text for p in snip.split("\n\n"))
