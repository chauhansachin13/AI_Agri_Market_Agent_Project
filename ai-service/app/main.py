"""FastAPI application exposing the multi-agent intelligence layer (§3.4)."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from .agents.orchestrator import _forecast_model, _weather_model, get_orchestrator
from .config import get_settings
from .data import agmarknet_gov, enam
from .nlp import pipeline as nlp_pipeline
from .rag.faiss_store import get_store
from .schemas import (
    AgentResponse,
    BuyerRecord,
    HealthResponse,
    NLPResult,
    PriceForecast,
    PriceRecord,
    QueryRequest,
    TrendAnalysis,
    WeatherSignal,
)
from .tools import forecast_tool, prediction_tool, weather_tool

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


@app.get("/languages", tags=["system"])
def languages() -> dict:
    """The supported languages, for the frontend picker (§6.3)."""
    from .i18n.translate import available as translation_available, language_options

    return {
        "languages": language_options(),
        "default": "hi",
        "neural_translation": translation_available(),
    }


@app.get("/mandi/forecast", response_model=PriceForecast, tags=["data"])
def mandi_forecast(
    crop: str,
    state: str | None = None,
    district: str | None = None,
    horizon: int = 7,
    history_days: int = 90,
) -> PriceForecast:
    """Trained multi-step price forecast with prediction intervals (§6.3)."""
    result = forecast_tool.TOOL(
        crop=crop,
        state=state,
        district=district,
        horizon=horizon,
        history_days=history_days,
    )
    if not result.ok:
        raise HTTPException(status_code=404, detail=result.error or "No forecast available")

    model = _forecast_model(result.data["forecast"])
    if model is None:
        raise HTTPException(status_code=404, detail="No forecast available")
    return model


@app.get("/weather/outlook", response_model=WeatherSignal, tags=["data"])
def weather_outlook(
    state: str | None = None,
    district: str | None = None,
    crop: str | None = None,
    days: int = 7,
) -> WeatherSignal:
    """Weather outlook and its implication for mandi supply (§6.3)."""
    result = weather_tool.TOOL(state=state, district=district, crop=crop, days=days)
    model = _weather_model(result.data)
    if model is None:
        raise HTTPException(status_code=404, detail="No weather outlook available")
    return model


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
