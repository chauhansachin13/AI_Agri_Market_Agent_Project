"""FAISS-backed vector store for the RAG pipeline (§4.5).

The index holds historical mandi price records, seasonal pattern summaries and
market news, each encoded to a 384-dimensional vector.  At query time the k
nearest documents (k=5 by default) are retrieved by cosine similarity and
injected into the prompt as source-attributed context, so the model reasons
about current prices against real historical precedent rather than its
parametric memory.

`faiss` is used when installed (`IndexFlatIP` over L2-normalised vectors gives
exact cosine search).  Otherwise an equivalent brute-force search runs in pure
Python — same ranking, slower on large corpora, which is acceptable at the
corpus sizes this service holds in memory.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from ..config import get_settings
from .embeddings import cosine_similarity, get_encoder

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """One retrievable unit of historical context."""

    text: str
    metadata: dict = field(default_factory=dict)

    @property
    def citation(self) -> str:
        """Source-attributed one-liner handed to the LLM and the fact-checker."""
        parts = [
            self.metadata.get("commodity"),
            self.metadata.get("market") or self.metadata.get("district"),
            self.metadata.get("arrival_date"),
        ]
        label = " / ".join(str(p) for p in parts if p)
        source = self.metadata.get("source", "corpus")
        return f"[{source}{': ' + label if label else ''}] {self.text}"


@dataclass
class SearchHit:
    document: Document
    score: float


class VectorStore:
    """Dense retrieval index with an exact-search fallback."""

    def __init__(self) -> None:
        self._documents: list[Document] = []
        self._vectors: list[list[float]] = []
        self._faiss_index = None
        self._encoder = get_encoder()

    # --- construction -------------------------------------------------------

    def add(self, documents: list[Document]) -> None:
        if not documents:
            return
        vectors = self._encoder.encode([d.text for d in documents])
        self._documents.extend(documents)
        self._vectors.extend(vectors)
        self._faiss_index = None  # invalidate; rebuilt lazily on next search

    def _build_faiss(self):  # pragma: no cover - optional dependency
        try:
            import faiss  # type: ignore
            import numpy as np
        except Exception:
            return None
        if not self._vectors:
            return None
        matrix = np.asarray(self._vectors, dtype="float32")
        faiss.normalize_L2(matrix)
        index = faiss.IndexFlatIP(matrix.shape[1])
        index.add(matrix)
        return index

    # --- retrieval ----------------------------------------------------------

    def search(self, query: str, k: int | None = None) -> list[SearchHit]:
        """Return the k most semantically similar documents."""
        if not self._documents:
            return []

        k = k or get_settings().rag_top_k
        k = min(k, len(self._documents))
        query_vector = self._encoder.encode_one(query)

        if self._faiss_index is None:
            self._faiss_index = self._build_faiss()

        if self._faiss_index is not None:  # pragma: no cover - optional dependency
            import numpy as np

            probe = np.asarray([query_vector], dtype="float32")
            import faiss  # type: ignore

            faiss.normalize_L2(probe)
            scores, indices = self._faiss_index.search(probe, k)
            return [
                SearchHit(document=self._documents[idx], score=float(score))
                for score, idx in zip(scores[0], indices[0])
                if idx >= 0
            ]

        ranked = sorted(
            (
                (cosine_similarity(query_vector, vector), index)
                for index, vector in enumerate(self._vectors)
            ),
            reverse=True,
        )
        return [SearchHit(document=self._documents[i], score=score) for score, i in ranked[:k]]

    # --- persistence --------------------------------------------------------

    def save(self, path=None) -> None:
        settings = get_settings()
        path = path or settings.corpus_path
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [{"text": d.text, "metadata": d.metadata} for d in self._documents]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, path=None) -> int:
        settings = get_settings()
        path = path or settings.corpus_path
        if not path.exists():
            return 0
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.add([Document(text=item["text"], metadata=item.get("metadata", {})) for item in payload])
        return len(payload)

    def __len__(self) -> int:
        return len(self._documents)

    @property
    def encoder_name(self) -> str:
        return self._encoder.name


_store: VectorStore | None = None


def get_store() -> VectorStore:
    """Return the process-wide store, building the corpus on first access."""
    global _store
    if _store is not None:
        return _store

    _store = VectorStore()
    loaded = _store.load()
    if loaded == 0:
        from .corpus import build_default_corpus

        documents = build_default_corpus()
        _store.add(documents)
        logger.info("Built default RAG corpus: %d documents", len(documents))
    else:
        logger.info("Loaded RAG corpus from disk: %d documents", loaded)

    return _store


def reset_store() -> None:
    """Drop the cached store — used by the test suite."""
    global _store
    _store = None
