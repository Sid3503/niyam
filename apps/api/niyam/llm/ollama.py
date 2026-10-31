"""Ollama (cloud) chat client with the same contract as llm/sarvam.py: structured JSON in, ChatResult out.

- POST https://ollama.com/api/chat, `Authorization: Bearer <OLLAMA_API_KEY>`, stream=false, `format` = JSON schema.
- Reasoning models (gpt-oss, nemotron, ...) accept `think`; we pass "low" where supported and fall back without it if the model rejects it.
- The key is read from the environment only and never logged. Retries only 429/5xx.
"""
from __future__ import annotations

import json
import logging
import random
import time

import httpx

from niyam.config import get_settings
from niyam.llm.sarvam import ChatResult, LLMUnavailable

log = logging.getLogger("niyam.llm")
BASE = "https://ollama.com"


def configured() -> bool:
    return bool(get_settings().ollama_api_key)


def chat_json(system: str, user: str, schema: dict, *, name: str, model: str | None = None, max_tokens: int = 1500,
              reasoning_effort: str = "low", temperature: float = 0.0, timeout: float = 60.0, max_attempts: int = 2) -> ChatResult:
    st = get_settings()
    if not st.ollama_api_key:
        raise LLMUnavailable("OLLAMA_API_KEY is not set", "llm_not_configured")
    model = model or st.ollama_model
    body = {"model": model, "stream": False, "format": schema, "think": reasoning_effort,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"temperature": temperature, "num_predict": max(max_tokens, 2048)}}
    headers = {"Authorization": f"Bearer {st.ollama_api_key}", "Content-Type": "application/json"}
    t0 = time.perf_counter()
    last = "no attempt made"
    for attempt in range(1, max_attempts + 1):
        try:
            r = httpx.post(f"{BASE}/api/chat", json=body, headers=headers, timeout=timeout)
        except httpx.HTTPError as e:
            last = f"network error: {type(e).__name__}"
            if attempt == max_attempts:
                raise LLMUnavailable(last, "llm_network") from e
            time.sleep(min(6, 2 ** attempt * 0.4) + random.random() * 0.3)
            continue
        if r.status_code == 200:
            j = r.json()
            try:
                data = json.loads((j.get("message") or {})["content"])
            except Exception as e:  # noqa: BLE001
                raise LLMUnavailable(f"model returned unusable output: {type(e).__name__}", "llm_bad_output") from e
            props = schema.get("properties", {})
            if isinstance(data, list) and schema.get("type") == "object" and len(props) == 1 and next(iter(props.values())).get("type") == "array":
                data = {next(iter(props)): data}        # some models drop the single wrapper key; restore it
            if not isinstance(data, dict):
                raise LLMUnavailable("model returned JSON of the wrong shape", "llm_bad_output")
            return ChatResult(data=data, model=j.get("model", model), prompt_tokens=j.get("prompt_eval_count", 0) or 0,
                              completion_tokens=j.get("eval_count", 0) or 0, reasoning_tokens=0,
                              latency_ms=round((time.perf_counter() - t0) * 1000), request_id=r.headers.get("x-request-id"), attempts=attempt)
        last = f"HTTP {r.status_code}"
        msg = ""
        try:
            msg = str((r.json() or {}).get("error", ""))[:200]
        except Exception:  # noqa: BLE001
            pass
        if r.status_code == 400 and "think" in body and "think" in msg.lower():
            body.pop("think")                              # this model does not take a reasoning level
            continue
        if r.status_code in (400, 401, 402, 403, 404):
            log.warning("ollama %s: %s", r.status_code, msg)
            raise LLMUnavailable(f"{last}: {msg}" if msg else last, {400: "llm_bad_request", 401: "llm_auth", 402: "llm_quota", 403: "llm_auth", 404: "llm_bad_request"}[r.status_code])
        if (r.status_code == 429 or r.status_code >= 500) and attempt < max_attempts:
            time.sleep(min(8, 2 ** attempt * 0.5) + random.random() * 0.4)
            continue
        raise LLMUnavailable(last, "llm_rate_limited" if r.status_code == 429 else "llm_error")
    raise LLMUnavailable(last)
