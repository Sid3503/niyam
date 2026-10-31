"""Sarvam speech-to-text (REST, clips up to ~30 s). Two passes per clip:
  codemix   -> what was actually said, shown to the human (Hindi/English/Hinglish as spoken)
  translate -> normalised English; spoken numbers and durations become digits ("do ghante" -> "two hours"). Tier A runs on THIS text.
The key is read from the environment only and never logged."""
from __future__ import annotations

import logging
import time

import httpx

from niyam.config import get_settings
from niyam.llm.sarvam import LLMUnavailable

log = logging.getLogger("niyam.speech")
URL = "https://api.sarvam.ai/speech-to-text"
MODEL = "saaras:v3"


def configured() -> bool:
    return bool(get_settings().sarvam_api_key)


def _call(data: bytes, filename: str, ctype: str, mode: str, timeout: float = 60.0) -> dict:
    key = get_settings().sarvam_api_key
    if not key:
        raise LLMUnavailable("SARVAM_API_KEY is not set (speech needs it even when Ollama does the judging)", "llm_not_configured")
    last = "no attempt"
    for attempt in (1, 2):
        try:
            r = httpx.post(URL, headers={"api-subscription-key": key}, files={"file": (filename, data, ctype)},
                           data={"model": MODEL, "mode": mode, "with_timestamps": "true"}, timeout=timeout)
        except httpx.HTTPError as e:
            last = f"network error: {type(e).__name__}"
            time.sleep(1.0)
            continue
        if r.status_code == 200:
            return r.json()
        msg = ""
        try:
            msg = (r.json().get("error") or {}).get("message", "")[:200]
        except Exception:  # noqa: BLE001
            pass
        if r.status_code in (400, 413, 422):
            raise LLMUnavailable(msg or f"HTTP {r.status_code}", "speech_bad_audio")
        if r.status_code in (401, 403):
            raise LLMUnavailable("speech API key rejected", "llm_auth")
        last = f"HTTP {r.status_code}"
        if r.status_code in (429, 500, 502, 503) and attempt == 1:
            time.sleep(1.5)
            continue
        raise LLMUnavailable(last, "llm_rate_limited" if r.status_code == 429 else "llm_error")
    raise LLMUnavailable(last, "llm_network")


def transcribe(data: bytes, filename: str, ctype: str) -> dict:
    """-> {original, english, language, language_probability, duration, segments:[{text,start,end}] (of the English pass)}"""
    orig = _call(data, filename, ctype, "codemix")
    en = _call(data, filename, ctype, "translate")
    ts = en.get("timestamps") or {}
    texts, starts, ends = ts.get("words") or [], ts.get("start_time_seconds") or [], ts.get("end_time_seconds") or []
    segs = [{"text": t, "start": float(s), "end": float(e)} for t, s, e in zip(texts, starts, ends)] if texts else []
    return {"original": (orig.get("transcript") or "").strip(), "english": (en.get("transcript") or "").strip(),
            "language": orig.get("language_code"), "language_probability": float(orig.get("language_probability") or 0.0),
            "duration": max([x["end"] for x in segs] or [0.0]), "segments": segs}
