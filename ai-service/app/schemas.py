"""Pydantic contracts shared by the FastAPI layer and the agent pipeline.

The response schema mirrors Section 4.7 of the report verbatim, so a client
written against the thesis specification will deserialise it unchanged.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Intent = Literal["price_query", "buyer_search", "sell_advice", "trend_analysis"]
TrendDirection = Literal["upward", "downward", "stable"]
Recommendation = Literal["SELL", "WAIT"]
FactCheckStatus = Literal["verified", "partially_verified", "insufficient_evidence"]
Language = Literal["hi", "en", "mixed"]


class GeoPoint(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query: str = Field(..., min_length=1, max_length=1000)
    coordinates: GeoPoint | None = None
    ip_address: str | None = None
    pincode: str | None = None
    session_id: str | None = None
    language_override: Language | None = None


class PriceRecord(BaseModel):
    """A normalised Agmarknet daily-price record (Section 4.4.1)."""

    state: str
    district: str
    market: str
    commodity: str
    variety: str = "Other"
    grade: str = "FAQ"
    arrival_date: str
    min_price: float
    max_price: float
    modal_price: float
    price_range: float = 0.0
    source: str = "agmarknet"

    def model_post_init(self, __context: Any) -> None:  # noqa: D105
        object.__setattr__(self, "price_range", round(self.max_price - self.min_price, 2))


class BuyerRecord(BaseModel):
    """An eNAM APMC / buyer contact record (Section 4.4.2)."""

    apmc_name: str
    state: str
    district: str
    address: str = ""
    contact: str = ""
    trading_hours: str = ""
    commodities: list[str] = Field(default_factory=list)
    source: str = "enam"


class TrendAnalysis(BaseModel):
    direction: TrendDirection
    ema_7: float
    ema_14: float
    ema_30: float
    volatility: float = 0.0
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    samples: int = 0


class Prediction(BaseModel):
    recommendation: Recommendation
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str


class FactCheckClaim(BaseModel):
    claim: str
    status: FactCheckStatus
    evidence: list[str] = Field(default_factory=list)


class LocationContext(BaseModel):
    state: str | None = None
    district: str | None = None
    pincode: str | None = None
    resolved_by: str = "unresolved"
    confidence: float = 0.0


class NLPResult(BaseModel):
    language: Language
    intent: Intent
    intent_confidence: float = Field(0.0, ge=0.0, le=1.0)
    crop: str | None = None
    crop_hindi: str | None = None
    quantity_value: float | None = None
    quantity_unit: str | None = None
    location: LocationContext = Field(default_factory=LocationContext)


class AgentResponse(BaseModel):
    """The standardised bilingual response object of Section 4.7."""

    intent: Intent
    crop: str | None
    location: str
    live_mandi_prices: list[PriceRecord] = Field(default_factory=list)
    buyers: list[BuyerRecord] = Field(default_factory=list)
    best_mandi: str | None = None
    trend_analysis: TrendAnalysis | None = None
    prediction: Prediction | None = None
    confidence_score: float = Field(0.0, ge=0.0, le=1.0)
    fact_check_status: FactCheckStatus = "insufficient_evidence"
    fact_check_claims: list[FactCheckClaim] = Field(default_factory=list)
    english_answer: str = ""
    hindi_answer: str = ""
    reasoning_steps: list[str] = Field(default_factory=list)
    retrieved_context: list[str] = Field(default_factory=list)
    search_snippets: list[str] = Field(default_factory=list)
    elapsed_ms: int = 0
    degraded: bool = False


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    llm_enabled: bool
    tavily_enabled: bool
    agmarknet_live: bool
    vector_documents: int
