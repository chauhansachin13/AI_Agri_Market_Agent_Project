"""FastAPI application exposing the multi-agent intelligence layer (§3.4)."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from .agents.orchestrator import get_orchestrator
from .config import get_settings
from .data import agmarknet_gov, enam
from .nlp import pipeline as nlp_pipeline
from .rag.faiss_store import get_store
from .schemas import (
    AgentResponse,
    BuyerRecord,
    HealthResponse,
    NLPResult,
    PriceRecord,
    QueryRequest,
    TrendAnalysis,
)
from .tools import prediction_tool

VERSION = "1.0.0"

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Agri-Market Intelligence Service",
    description=(
        "Multi-agent AI service providing government-grounded, bilingual "
        "agricultural market intelligence for Indian farmers."
    ),
    version=VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Liveness probe that also reports which integrations are active."""
    return HealthResponse(
        version=VERSION,
        llm_enabled=settings.llm_enabled,
        tavily_enabled=settings.tavily_enabled,
        agmarknet_live=settings.agmarknet_live,
        vector_documents=len(get_store()),
    )


@app.post("/agent/query", response_model=AgentResponse, tags=["agent"])
def agent_query(payload: QueryRequest, request: Request) -> AgentResponse:
    """Primary endpoint: run the full multi-agent pipeline over a farmer query."""
    if not payload.query.strip():
        raise HTTPException(status_code=422, detail="Query must not be empty.")

    # The backend forwards the farmer's IP; fall back to the socket peer.
    if payload.ip_address is None and request.client is not None:
        payload = payload.model_copy(update={"ip_address": request.client.host})

    try:
        return get_orchestrator().run(payload)
    except Exception as exc:
        logger.exception("Agent pipeline failed")
        raise HTTPException(status_code=500, detail=f"Agent pipeline failed: {exc}") from exc


@app.post("/nlp/parse", response_model=NLPResult, tags=["nlp"])
def parse_query(payload: QueryRequest) -> NLPResult:
    """Expose the NLP pipeline on its own — useful for debugging and evaluation."""
    return nlp_pipeline.run(
        payload.query,
        pincode=payload.pincode,
        ip_address=payload.ip_address,
        coordinates=payload.coordinates,
        language_override=payload.language_override,
    )


@app.get("/mandi/prices", response_model=list[PriceRecord], tags=["data"])
def mandi_prices(
    crop: str | None = None,
    state: str | None = None,
    district: str | None = None,
    limit: int = 50,
) -> list[PriceRecord]:
    """Raw normalised Agmarknet records, for the dashboard and the price cache."""
    result = agmarknet_gov.fetch_prices(
        commodity=crop, state=state, district=district, limit=limit
    )
    return result.records


@app.get("/mandi/buyers", response_model=list[BuyerRecord], tags=["data"])
def mandi_buyers(
    state: str | None = None,
    district: str | None = None,
    crop: str | None = None,
) -> list[BuyerRecord]:
    """APMC and buyer contacts from eNAM."""
    return enam.fetch_buyers(state=state, district=district, commodity=crop).buyers


@app.get("/mandi/trend", response_model=TrendAnalysis, tags=["data"])
def mandi_trend(
    crop: str,
    state: str | None = None,
    district: str | None = None,
    days: int = 45,
) -> TrendAnalysis:
    """EMA trend analysis for one crop-location pair."""
    result = prediction_tool.TOOL(crop=crop, state=state, district=district, days=days)
    if not result.ok:
        raise HTTPException(status_code=404, detail=result.error or "No trend available")
    return result.data["analysis"]


@app.get("/mandi/series", tags=["data"])
def mandi_series(
    crop: str,
    state: str | None = None,
    district: str | None = None,
    days: int = 45,
) -> dict:
    """Daily modal price series powering the frontend trend chart."""
    history = agmarknet_gov.fetch_price_history(
        commodity=crop, state=state, district=district, days=days
    )
    by_date: dict[str, list[float]] = {}
    for record in history:
        by_date.setdefault(record.arrival_date, []).append(record.modal_price)

    points = [
        {"date": day, "modal_price": round(sum(prices) / len(prices), 2)}
        for day, prices in sorted(by_date.items())
    ]
    return {"crop": crop, "state": state, "district": district, "points": points}
