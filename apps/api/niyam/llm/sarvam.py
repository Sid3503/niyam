"""Thin Sarvam chat client (OpenAI-compatible endpoint). Conventions are from docs/SARVAM-AI-LOGIC.md section 1.2.

- Auth header `api-subscription-key`; model `sarvam-105b`; base https://api.sarvam.ai
- reasoning_effort is ALWAYS set explicitly. VERIFIED LIVE 31 Oct 2026: the API REJECTS "none" (HTTP 400: only 'low', 'medium', 'high'), which
  contradicts the earlier note in docs/SARVAM-AI-LOGIC.md. We use "low". Reasoning tokens bill as output and consume max_tokens, so budgets
  must be generous (a 300-token budget was truncated with finish_reason=length); on truncation we retry once with a larger budget.
- Retry 429/503 with exponential backoff + jitter; never retry 400/402/403.
- Structured output via response_format json_schema; the reply is a JSON *string* that we parse and validate ourselves.
- The key is read from the environment only and is never logged.
"""
from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass

import httpx

from niyam.config import get_settings

log = logging.getLogger("niyam.llm")
BASE = "https://api.sarvam.ai"
RETRYABLE = {429, 503}
FATAL = {400, 402, 403}


class LLMUnavailable(RuntimeError):
    """Key missing, quota exhausted, rate-limited past retries, timeout, or unusable output."""

    def __init__(self, message: str, code: str = "llm_unavailable"):
        super().__init__(message)
        self.code = code


@dataclass
class ChatResult:
    data: dict            # parsed JSON the model returned
    model: str
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    latency_ms: int
    request_id: str | None
    attempts: int


def configured() -> bool:
    return bool(get_settings().sarvam_api_key)


def chat_json(system: str, user: str, schema: dict, *, name: str, model: str = "sarvam-105b", max_tokens: int = 1500,
              reasoning_effort: str = "low", temperature: float = 0.0, timeout: float = 30.0, max_attempts: int = 3) -> ChatResult:
    key = get_settings().sarvam_api_key
    if not key:
        raise LLMUnavailable("SARVAM_API_KEY is not set", "llm_not_configured")
    body = {
        "model": model, "temperature": temperature, "max_tokens": max_tokens, "reasoning_effort": reasoning_effort,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}},
    }
    if reasoning_effort not in ("low", "medium", "high"):
        raise LLMUnavailable(f"reasoning_effort must be low|medium|high (the API rejects {reasoning_effort!r})", "llm_bad_request")
    headers = {"api-subscription-key": key, "Content-Type": "application/json"}
    t0 = time.perf_counter()
    last = "no attempt made"
    for attempt in range(1, max_attempts + 1):
        try:
            r = httpx.post(f"{BASE}/v1/chat/completions", json=body, headers=headers, timeout=timeout)
        except httpx.HTTPError as e:
            last = f"network error: {type(e).__name__}"
            if attempt == max_attempts:
                raise LLMUnavailable(last, "llm_network") from e
            time.sleep(min(8, 2 ** attempt * 0.4) + random.random() * 0.3)
            continue
        if r.status_code == 200:
            j = r.json()
            if (j.get("choices") or [{}])[0].get("finish_reason") == "length":
                if body["max_tokens"] < 4096 and attempt < max_attempts:       # reasoning ate the budget: retry once, bigger
                    body["max_tokens"] = min(4096, body["max_tokens"] * 2)
                    last = "truncated (finish_reason=length)"
                    continue
                raise LLMUnavailable("model output truncated even at the maximum budget", "llm_truncated")
            try:
                content = j["choices"][0]["message"]["content"]
                data = json.loads(content)
            except Exception as e:  # noqa: BLE001
                raise LLMUnavailable(f"model returned unusable output: {type(e).__name__}", "llm_bad_output") from e
            u = j.get("usage") or {}
            rt = ((u.get("completion_tokens_details") or {}).get("reasoning_tokens")) or 0
            return ChatResult(data=data, model=j.get("model", model), prompt_tokens=u.get("prompt_tokens", 0), completion_tokens=u.get("completion_tokens", 0),
                              reasoning_tokens=rt, latency_ms=round((time.perf_counter() - t0) * 1000),
                              request_id=r.headers.get("x-request-id") or j.get("id"), attempts=attempt)
        last = f"HTTP {r.status_code}"
        if r.status_code in FATAL:
            try:
                msg = (r.json().get("error") or {}).get("message", "")[:200]
            except Exception:  # noqa: BLE001
                msg = ""
            log.warning("sarvam %s: %s", r.status_code, msg)          # the message never contains the key
            raise LLMUnavailable(f"{last}: {msg}" if msg else last, {400: "llm_bad_request", 402: "llm_quota", 403: "llm_auth"}[r.status_code])
        if r.status_code in RETRYABLE and attempt < max_attempts:
            ra = r.headers.get("retry-after")
            time.sleep(min(10, float(ra)) if ra and ra.replace(".", "", 1).isdigit() else min(8, 2 ** attempt * 0.5) + random.random() * 0.4)
            continue
        raise LLMUnavailable(last, "llm_rate_limited" if r.status_code == 429 else "llm_error")
    raise LLMUnavailable(last)
