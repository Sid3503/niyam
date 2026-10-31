"""Pick the LLM provider. NIYAM_LLM_PROVIDER = auto | ollama | sarvam. auto: Ollama if OLLAMA_API_KEY is set (faster in our benchmark), else Sarvam.
Every caller goes through here, so a provider or model change is one setting, and each model_calls row records the real provider and model."""
from __future__ import annotations

from niyam.config import get_settings
from niyam.llm import ollama, sarvam
from niyam.llm.sarvam import ChatResult, LLMUnavailable  # noqa: F401  (re-exported)


def provider_name() -> str | None:
    s = get_settings()
    want = (s.llm_provider or "auto").lower()
    if want == "ollama":
        return "ollama" if ollama.configured() else None
    if want == "sarvam":
        return "sarvam" if sarvam.configured() else None
    if ollama.configured():
        return "ollama"
    return "sarvam" if sarvam.configured() else None


def model_name() -> str:
    p = provider_name()
    return get_settings().ollama_model if p == "ollama" else "sarvam-105b"


def configured() -> bool:
    return provider_name() is not None


def chat_json(system: str, user: str, schema: dict, **kw) -> ChatResult:
    p = provider_name()
    if p == "ollama":
        return ollama.chat_json(system, user, schema, **kw)
    if p == "sarvam":
        return sarvam.chat_json(system, user, schema, **kw)
    raise LLMUnavailable("no LLM provider is configured (set OLLAMA_API_KEY or SARVAM_API_KEY)", "llm_not_configured")
