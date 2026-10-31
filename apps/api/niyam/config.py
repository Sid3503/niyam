"""Runtime configuration. Every secret comes from the environment (.env, never committed)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NIYAM_", env_file=".env", extra="ignore")

    env: str = "dev"                                   # dev | prod
    database_url: str = "postgresql+psycopg://niyam:niyam@db:5432/niyam"
    tenant_id: str = "default"
    # Data roots (mounted read-only in Docker). corpus_roots maps a kind to a directory.
    data_root: Path = Path("/data")
    regulations_dir: str = "regulations"               # corpus_kind=regulation
    surfaces_dir: str = "paytm-terms"                  # corpus_kind=surface (statements to TEST, not sources of obligation)
    rules_dir: str = "rules/cards"
    blob_dir: str = ""                                 # PDF/audio bytes (object-store stand-in). Empty: <data_root>/var/blobs, else /tmp/niyam-blobs if that is read-only
    library_dir: str = "library"                       # monitored proposal/contract folder (synthetic demo documents)
    api_key: str | None = None                         # if set, X-API-Key is required on /api/*
    store_check_text: bool = True                      # demo/synthetic data only; set false for anything real
    max_check_chars: int = 20_000
    sync_rules_on_start: bool = True
    tier_b_min_confidence: float = 0.7
    tier_b_max_calls_per_check: int = 6
    guard_budget_ms: int = 3000
    log_level: str = "INFO"
    as_of_override: str | None = None                  # ISO date, for reproducible demos/tests
    sarvam_api_key: str | None = Field(default=None, validation_alias="SARVAM_API_KEY")
    ollama_api_key: str | None = Field(default=None, validation_alias="OLLAMA_API_KEY")
    ollama_model: str = Field(default="gpt-oss:120b", validation_alias="NIYAM_OLLAMA_MODEL")
    llm_provider: str = Field(default="auto", validation_alias="NIYAM_LLM_PROVIDER")   # auto | sarvam | ollama

    @property
    def regulations_path(self) -> Path:
        return self.data_root / self.regulations_dir

    @property
    def surfaces_path(self) -> Path:
        return self.data_root / self.surfaces_dir

    @property
    def blob_path(self) -> Path:
        if self.blob_dir:
            return Path(self.blob_dir)
        p = self.data_root / "var" / "blobs"
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except OSError:
            q = Path("/tmp/niyam-blobs")
            q.mkdir(parents=True, exist_ok=True)
            return q

    @property
    def library_path(self) -> Path:
        return self.data_root / self.library_dir

    @property
    def rules_path(self) -> Path:
        return self.data_root / self.rules_dir


@lru_cache
def get_settings() -> Settings:
    return Settings()
