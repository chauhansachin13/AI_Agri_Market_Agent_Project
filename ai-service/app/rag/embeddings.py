"""Document encoders for the RAG pipeline (§4.5).

The production encoder is ``sentence-transformers/all-MiniLM-L6-v2``, which
produces the 384-dimensional dense vectors the report specifies.  Loading a
transformer is a heavyweight dependency, so a deterministic hashing encoder of
the same dimensionality stands in when it is unavailable.

The hashing encoder is a genuine bag-of-features vector space — character
n-grams and word unigrams projected into 384 buckets with signed hashing — so
cosine similarity still ranks lexically related mandi records sensibly.  It is
weaker at paraphrase than a transformer, and the service reports which encoder
is active so results are never misread as transformer-quality.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from abc import ABC, abstractmethod

from ..config import get_settings

logger = logging.getLogger(__name__)

_TOKEN_PATTERN = re.compile(r"[\wऀ-ॿ]+", re.UNICODE)


class Encoder(ABC):
    """Common interface for both encoder implementations."""

    name: str
    dimension: int

    @abstractmethod
    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode a batch of documents into unit-norm dense vectors."""

    def encode_one(self, text: str) -> list[float]:
        return self.encode([text])[0]


def _normalise(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0.0:
        return vector
    return [v / norm for v in vector]


class HashingEncoder(Encoder):
    """Signed-hashing bag-of-features encoder — the dependency-free fallback."""

    name = "hashing-384"

    def __init__(self, dimension: int = 384, ngram_range: tuple[int, int] = (3, 5)):
        self.dimension = dimension
        self.ngram_range = ngram_range

    def _features(self, text: str) -> list[str]:
        lowered = text.lower()
        tokens = _TOKEN_PATTERN.findall(lowered)
        features = list(tokens)
        # Word bigrams capture phrases like "modal price" or "टमाटर भाव".
        features += [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
        # Character n-grams give robustness to spelling and transliteration drift.
        compact = " ".join(tokens)
        low, high = self.ngram_range
        for size in range(low, high + 1):
            features += [compact[i : i + size] for i in range(len(compact) - size + 1)]
        return features

    def encode(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimension
            features = self._features(text)
            if not features:
                vectors.append(vector)
                continue
            for feature in features:
                digest = hashlib.md5(feature.encode("utf-8")).digest()
                bucket = int.from_bytes(digest[:4], "big") % self.dimension
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vector[bucket] += sign
            # Sub-linear scaling damps the effect of very long documents.
            vector = [math.copysign(math.log1p(abs(v)), v) for v in vector]
            vectors.append(_normalise(vector))
        return vectors


class SentenceTransformerEncoder(Encoder):  # pragma: no cover - optional dependency
    """The all-MiniLM-L6-v2 encoder named in the report."""

    def __init__(self, model_name: str, dimension: int):
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        self.name = model_name
        self.dimension = dimension

    def encode(self, texts: list[str]) -> list[list[float]]:
        raw = self._model.encode(texts, normalize_embeddings=True)
        return [list(map(float, vector)) for vector in raw]


_encoder: Encoder | None = None


def get_encoder() -> Encoder:
    """Return the process-wide encoder, preferring the transformer."""
    global _encoder
    if _encoder is not None:
        return _encoder

    settings = get_settings()
    if not settings.offline_mode:
        try:
            _encoder = SentenceTransformerEncoder(
                settings.embedding_model, settings.embedding_dimension
            )
            logger.info("RAG encoder: %s", _encoder.name)
            return _encoder
        except Exception as exc:
            logger.info("sentence-transformers unavailable (%s); using hashing encoder", exc)

    _encoder = HashingEncoder(settings.embedding_dimension)
    return _encoder


def reset_encoder() -> None:
    """Drop the cached encoder — used by the test suite."""
    global _encoder
    _encoder = None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors (unit-norm inputs give the dot product)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
