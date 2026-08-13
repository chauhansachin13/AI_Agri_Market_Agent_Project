"""Shared fixtures. Every test runs the service in offline mode so the suite
never depends on network access or API credentials."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("OFFLINE_MODE", "1")

from app.config import get_settings  # noqa: E402
from app.rag import embeddings, faiss_store  # noqa: E402


@pytest.fixture(autouse=True)
def _offline_environment(monkeypatch):
    monkeypatch.setenv("OFFLINE_MODE", "1")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("AGMARKNET_API_KEY", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def store():
    embeddings.reset_encoder()
    faiss_store.reset_store()
    return faiss_store.get_store()


@pytest.fixture
def orchestrator():
    from app.agents.orchestrator import ReActOrchestrator

    return ReActOrchestrator()
