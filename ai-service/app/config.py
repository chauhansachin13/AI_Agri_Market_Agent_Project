"""Runtime configuration for the AI intelligence layer.

Every external dependency (Gemini, Tavily, the Agmarknet open-data API) is
optional at import time.  When a key is absent the corresponding component
falls back to a deterministic offline implementation so that the full
multi-agent pipeline remains runnable — and testable — without network access.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    """Immutable settings snapshot, resolved once per process."""

    # --- LLM (Chapter 4.2.1) -------------------------------------------------
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    llm_temperature: float = 0.3
    llm_max_output_tokens: int = 1024
    agent_max_iterations: int = 8

    # --- Tools ---------------------------------------------------------------
    tavily_api_key: str | None = None
    agmarknet_api_key: str | None = None
    agmarknet_base_url: str = "https://api.data.gov.in/resource"
    agmarknet_resource_id: str = "9ef84268-d588-465a-a308-a864a43d0070"
    enam_base_url: str = "https://enam.gov.in/web/dashboard"
    http_timeout_seconds: float = 10.0
    http_max_retries: int = 3
    agmarknet_record_limit: int = 50

    # --- RAG (Chapter 4.5) ---------------------------------------------------
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    rag_top_k: int = 5
    faiss_index_path: Path = field(default_factory=lambda: DATA_DIR / "faiss_index")
    corpus_path: Path = field(default_factory=lambda: DATA_DIR / "mandi_corpus.json")

    # --- Prediction (Chapter 4.6.1) -----------------------------------------
    ema_windows: tuple[int, int, int] = (7, 14, 30)

    # --- Service -------------------------------------------------------------
    offline_mode: bool = False
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://localhost:3000")
    log_level: str = "INFO"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.gemini_api_key) and not self.offline_mode

    @property
    def tavily_enabled(self) -> bool:
        return bool(self.tavily_api_key) and not self.offline_mode

    @property
    def agmarknet_live(self) -> bool:
        return bool(self.agmarknet_api_key) and not self.offline_mode


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    origins = os.getenv("CORS_ORIGINS")
    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        llm_temperature=_env_float("LLM_TEMPERATURE", 0.3),
        llm_max_output_tokens=_env_int("LLM_MAX_OUTPUT_TOKENS", 1024),
        agent_max_iterations=_env_int("AGENT_MAX_ITERATIONS", 8),
        tavily_api_key=os.getenv("TAVILY_API_KEY") or None,
        agmarknet_api_key=os.getenv("AGMARKNET_API_KEY") or os.getenv("DATA_GOV_API_KEY") or None,
        http_timeout_seconds=_env_float("HTTP_TIMEOUT_SECONDS", 10.0),
        http_max_retries=_env_int("HTTP_MAX_RETRIES", 3),
        agmarknet_record_limit=_env_int("AGMARKNET_RECORD_LIMIT", 50),
        rag_top_k=_env_int("RAG_TOP_K", 5),
        offline_mode=_env_flag("OFFLINE_MODE", False),
        cors_origins=tuple(o.strip() for o in origins.split(",")) if origins
        else ("http://localhost:5173", "http://localhost:3000"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
