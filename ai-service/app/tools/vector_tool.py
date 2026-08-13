"""Vector Tool — FAISS similarity search over historical mandi context (§4.5)."""

from __future__ import annotations

from ..config import get_settings
from ..rag.faiss_store import get_store
from .base import Tool, ToolResult


def retrieve_context(
    query: str,
    crop: str | None = None,
    location: str | None = None,
    k: int | None = None,
) -> ToolResult:
    """Retrieve the k most semantically similar historical documents."""
    settings = get_settings()
    k = k or settings.rag_top_k

    # Crop and location are folded into the probe so retrieval is anchored to
    # the same entities the mandi tool queried.
    probe = " ".join(part for part in (query, crop, location) if part)

    store = get_store()
    hits = store.search(probe, k=k)

    if not hits:
        return ToolResult(
            ok=False,
            data=[],
            summary="No historical context available in the vector index.",
            source="faiss",
            error="empty_index",
        )

    citations = [hit.document.citation for hit in hits]
    lines = [f"Retrieved {len(hits)} historical context passages:"]
    lines += [f"  ({hit.score:.3f}) {hit.document.citation}" for hit in hits]

    return ToolResult(
        ok=True,
        data={
            "citations": citations,
            "hits": [
                {
                    "text": hit.document.text,
                    "metadata": hit.document.metadata,
                    "score": round(hit.score, 4),
                }
                for hit in hits
            ],
            "encoder": store.encoder_name,
        },
        summary="\n".join(lines),
        source="faiss",
        degraded=not store.encoder_name.startswith("sentence-transformers"),
    )


TOOL = Tool(
    name="historical_context",
    description=(
        "Search the FAISS vector index of historical mandi price records, "
        "seasonal price patterns and market notes for context relevant to the "
        "query. Use this to reason about whether a current price is high or low "
        "relative to precedent. Each passage carries its own source attribution."
    ),
    func=retrieve_context,
    args_schema={
        "query": "Natural language query text",
        "crop": "Crop name to anchor retrieval",
        "location": "District or state to anchor retrieval",
        "k": "Number of passages to retrieve (integer, default 5)",
    },
)
