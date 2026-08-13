"""Tavily Search Tool — current market trends, demand signals and farm news.

Per §4.4 this tool never supplies price values that reach the farmer unchecked;
Agmarknet remains the source of truth for numbers.  What it contributes is
context the government dataset cannot carry — weather disruption, export
policy, demand chatter — which the reasoning and fact-check agents weigh at a
lower evidentiary weight than the API data.
"""

from __future__ import annotations

import logging

from ..config import get_settings
from .base import Tool, ToolResult

logger = logging.getLogger(__name__)


def _build_query(crop: str | None, location: str | None, topic: str | None) -> str:
    parts = [crop or "agricultural commodity", "mandi price trend"]
    if location:
        parts.append(location)
    if topic:
        parts.append(topic)
    parts.append("India latest")
    return " ".join(parts)


def search_market_intelligence(
    crop: str | None = None,
    location: str | None = None,
    topic: str | None = None,
    max_results: int = 5,
) -> ToolResult:
    """Search the live internet for market context around a crop and location."""
    settings = get_settings()
    query = _build_query(crop, location, topic)

    if not settings.tavily_enabled:
        return ToolResult(
            ok=True,
            data=[],
            summary=(
                "Internet search unavailable (no Tavily API key configured). "
                "Proceeding on government mandi data and historical context only."
            ),
            source="tavily",
            degraded=True,
            error="TAVILY_API_KEY not configured",
        )

    try:  # pragma: no cover - requires network credentials
        from tavily import TavilyClient

        client = TavilyClient(api_key=settings.tavily_api_key)
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=max_results,
            topic="news",
        )
        results = response.get("results", [])
        snippets = [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": (item.get("content") or "")[:400],
                "score": item.get("score", 0.0),
            }
            for item in results
        ]
        if not snippets:
            return ToolResult(
                ok=True,
                data=[],
                summary=f"No recent news found for '{query}'.",
                source="tavily",
            )

        lines = [f"{len(snippets)} recent items for '{query}':"]
        lines += [f"  - {s['title']}: {s['content'][:200]}" for s in snippets]
        return ToolResult(ok=True, data=snippets, summary="\n".join(lines), source="tavily")

    except Exception as exc:
        logger.warning("Tavily search failed: %s", exc)
        return ToolResult(
            ok=True,
            data=[],
            summary="Internet search failed; continuing without it.",
            source="tavily",
            degraded=True,
            error=str(exc),
        )


TOOL = Tool(
    name="internet_search",
    description=(
        "Search the internet for current agricultural market trends, demand "
        "signals, weather impact, agricultural news and government policy "
        "announcements relevant to a crop and location. Use this for context "
        "that the government price dataset cannot provide. Do not treat any "
        "price figure found here as authoritative."
    ),
    func=search_market_intelligence,
    args_schema={
        "crop": "Crop name",
        "location": "District or state",
        "topic": "Optional focus, e.g. 'export policy', 'rainfall'",
        "max_results": "Number of results (integer)",
    },
)
