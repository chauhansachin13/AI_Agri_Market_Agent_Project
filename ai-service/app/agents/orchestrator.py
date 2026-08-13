"""ReAct Orchestrator — the architectural centrepiece of the AI service (§4.2).

The ReAct paradigm interleaves natural-language reasoning (Thought) with tool
invocations (Action) and their results (Observation) until an answer is
reached. Two execution modes share one tool suite and one output schema:

  * **Agentic mode** — LangChain's ``AgentExecutor`` binds the five tools to
    Gemini 2.5 Flash, which selects them dynamically. Every intermediate step
    is captured and surfaced in the Explainable AI panel.
  * **Deterministic mode** — when no LLM is configured, the same tools run in
    the fixed order of the Section 4.3 workflow. The reasoning trail is still
    produced, so the XAI panel and the response schema never change shape.

Both modes end in the same place: the Sell Decision agent, the Fact-Check
agent, and bilingual answer generation.
"""

from __future__ import annotations

import logging
import time

from ..config import get_settings
from ..schemas import (
    AgentResponse,
    ForecastPointModel,
    GeoPoint,
    PriceForecast,
    QueryRequest,
    WeatherDay,
    WeatherSignal,
)
from ..tools import (
    forecast_tool,
    location_tool,
    mandi_tool,
    prediction_tool,
    tavily_tool,
    vector_tool,
    weather_tool,
)
from .answer import AnswerGenerationAgent
from .llm import get_llm
from .specialists import (
    AgentContext,
    BuyerConnectAgent,
    ContextRetrievalAgent,
    FactCheckAgent,
    IntentDetectionAgent,
    LocationResolutionAgent,
    MandiIntelligenceAgent,
    PriceForecastingAgent,
    PricePredictionAgent,
    ReasoningAgent,
    SellDecisionAgent,
    TavilySearchAgent,
    WeatherImpactAgent,
)

logger = logging.getLogger(__name__)

TOOLS = [
    mandi_tool.TOOL,
    tavily_tool.TOOL,
    location_tool.TOOL,
    vector_tool.TOOL,
    prediction_tool.TOOL,
    # Added by Section 6.3: a trained forecaster and a weather supply signal.
    forecast_tool.TOOL,
    weather_tool.TOOL,
]

REACT_SYSTEM_PROMPT = """You are the reasoning core of an agricultural market
intelligence system serving Indian farmers.

You answer questions about mandi prices, buyers, selling decisions and price
trends. You have tools that reach live government data. Use them — never answer
a price question from memory.

Work in Thought / Action / Observation cycles:
  Thought: what you still need to know and why
  Action: the tool to call, with its arguments
  Observation: what the tool returned

Rules:
- Resolve the farmer's location before fetching prices.
- Every price you report must have come from the mandi_prices tool.
- Check the historical context before judging whether a price is good.
- Stop as soon as you have enough evidence; do not call tools you do not need.
"""


def _build_langchain_agent():  # pragma: no cover - requires credentials
    """Bind the tool suite to Gemini through LangChain's AgentExecutor."""
    from langchain.agents import AgentExecutor, create_tool_calling_agent
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.tools import StructuredTool

    handle = get_llm()
    if handle is None or handle.flavour != "langchain":
        return None

    settings = get_settings()

    def wrap(tool):
        def _run(**kwargs):
            return tool(**kwargs).as_observation()

        return StructuredTool.from_function(
            func=_run, name=tool.name, description=tool.description
        )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", REACT_SYSTEM_PROMPT),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )
    agent = create_tool_calling_agent(handle.client, [wrap(t) for t in TOOLS], prompt)
    return AgentExecutor(
        agent=agent,
        tools=[wrap(t) for t in TOOLS],
        max_iterations=settings.agent_max_iterations,
        return_intermediate_steps=True,
        handle_parsing_errors=True,
        verbose=False,
    )


class ReActOrchestrator:
    """Runs the full multi-agent workflow for one farmer query."""

    name = "ReAct Orchestrator"

    def __init__(self) -> None:
        self.intent_agent = IntentDetectionAgent()
        self.location_agent = LocationResolutionAgent()
        self.mandi_agent = MandiIntelligenceAgent()
        self.buyer_agent = BuyerConnectAgent()
        self.search_agent = TavilySearchAgent()
        self.retrieval_agent = ContextRetrievalAgent()
        self.prediction_agent = PricePredictionAgent()
        self.forecasting_agent = PriceForecastingAgent()
        self.weather_agent = WeatherImpactAgent()
        self.reasoning_agent = ReasoningAgent()
        self.sell_agent = SellDecisionAgent()
        self.fact_check_agent = FactCheckAgent()
        self.answer_agent = AnswerGenerationAgent()

    # ----------------------------------------------------------------- #
    def run(self, request: QueryRequest) -> AgentResponse:
        started = time.perf_counter()

        coordinates: GeoPoint | None = request.coordinates
        context = self.intent_agent.run(
            request.query,
            pincode=request.pincode,
            ip_address=request.ip_address,
            coordinates=coordinates,
            language_override=request.language_override,
        )

        self.location_agent.run(
            context,
            pincode=request.pincode,
            ip_address=request.ip_address,
            coordinates=coordinates,
        )

        self._gather_evidence(context)

        agentic_steps = self._run_agentic_loop(request, context)
        if agentic_steps:
            context.reasoning_steps.extend(agentic_steps)

        self.reasoning_agent.run(context)
        self.sell_agent.run(context)

        answers, primary, status = self.answer_agent.run(context)

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return self._assemble(context, answers, primary, status, elapsed_ms)

    # ----------------------------------------------------------------- #
    def _gather_evidence(self, context: AgentContext) -> None:
        """Invoke the data-gathering agents the detected intent calls for.

        Prices and history are fetched for every intent — a buyer question is
        far more useful when the answer also says what the crop is fetching —
        but the eNAM lookup is reserved for the intents that actually need it,
        since it is the slowest upstream call.
        """
        intent = context.nlp.intent

        self.mandi_agent.run(context)
        self.retrieval_agent.run(context)

        if intent in ("buyer_search", "sell_advice"):
            self.buyer_agent.run(context)

        if intent in ("trend_analysis", "sell_advice", "price_query"):
            self.prediction_agent.run(context)

        # The trained forecast and the weather signal only change the answer for
        # forward-looking questions, and both cost real work, so they are not
        # run for a plain "what is the rate today".
        if intent in ("trend_analysis", "sell_advice"):
            self.forecasting_agent.run(context)
            self.weather_agent.run(context)
            self.search_agent.run(context)

    # ----------------------------------------------------------------- #
    def _run_agentic_loop(self, request: QueryRequest, context: AgentContext) -> list[str]:
        """Run the LLM-driven ReAct loop and return its reasoning trail."""
        settings = get_settings()
        if not settings.llm_enabled:
            context.observe(
                self.name,
                "Running the deterministic tool pipeline (no language model configured).",
            )
            return []

        executor = _build_langchain_agent()
        if executor is None:
            return []

        try:  # pragma: no cover - requires credentials
            payload = executor.invoke(
                {
                    "input": (
                        f"{request.query}\n\n"
                        f"Known context — intent: {context.nlp.intent}, "
                        f"crop: {context.nlp.crop}, location: {context.location_label}."
                    )
                }
            )
            steps: list[str] = []
            for action, observation in payload.get("intermediate_steps", []):
                tool_name = getattr(action, "tool", "tool")
                tool_input = getattr(action, "tool_input", {})
                log = (getattr(action, "log", "") or "").strip().splitlines()
                thought = next((line for line in log if line.strip()), "")
                if thought:
                    steps.append(f"Thought: {thought}")
                steps.append(f"Action: {tool_name}({tool_input})")
                steps.append(f"Observation: {str(observation)[:400]}")
            if payload.get("output"):
                steps.append(f"Thought: {str(payload['output'])[:400]}")
            return steps
        except Exception as exc:
            logger.warning("ReAct loop failed (%s); deterministic evidence stands", exc)
            context.observe(
                self.name,
                "The agentic loop could not complete; the answer rests on the "
                "deterministic tool pipeline.",
            )
            return []

    # ----------------------------------------------------------------- #
    def _assemble(
        self,
        context: AgentContext,
        answers: dict[str, str],
        primary: str,
        status: str,
        elapsed_ms: int,
    ) -> AgentResponse:
        best = context.prices[0] if context.prices else None

        return AgentResponse(
            intent=context.nlp.intent,
            crop=context.nlp.crop,
            location=context.location_label,
            live_mandi_prices=context.prices[:20],
            buyers=context.buyers,
            best_mandi=f"{best.market}, {best.district}" if best else None,
            trend_analysis=context.trend,
            forecast=_forecast_model(context.forecast),
            weather=_weather_model(context.weather),
            prediction=context.prediction,
            confidence_score=self._confidence(context, status),
            fact_check_status=status,  # type: ignore[arg-type]
            fact_check_claims=context.claims,
            english_answer=answers.get("en", ""),
            hindi_answer=answers.get("hi", ""),
            answer=answers.get(primary, ""),
            answer_language=primary,  # type: ignore[arg-type]
            answers=answers,
            reasoning_steps=context.reasoning_steps,
            retrieved_context=context.retrieved_context,
            search_snippets=context.search_snippets,
            elapsed_ms=elapsed_ms,
            degraded=context.degraded,
        )

    @staticmethod
    def _confidence(context: AgentContext, status: str) -> float:
        """Overall response confidence.

        Blends the four signals a farmer's trust actually rests on: how sure we
        are of the intent, whether the location was pinned down, whether real
        price records were found, and whether the claims survived fact-checking.
        """
        signals: list[float] = [context.nlp.intent_confidence]
        signals.append(context.nlp.location.confidence)
        signals.append(1.0 if context.prices else 0.0)

        if context.trend is not None:
            signals.append(context.trend.confidence)

        status_weight = {
            "verified": 1.0,
            "partially_verified": 0.75,
            "insufficient_evidence": 0.35,
        }[status]

        base = sum(signals) / len(signals)
        score = base * status_weight

        # Offline data is usable but should never present as fully trustworthy.
        if context.degraded:
            score *= 0.85

        return round(min(max(score, 0.0), 1.0), 3)


def _forecast_model(forecast) -> PriceForecast | None:
    """Convert the internal Forecast dataclass into its wire schema."""
    if forecast is None or not getattr(forecast, "points", None):
        return None

    beats_baseline = None
    if forecast.mape is not None and forecast.baseline_mape is not None:
        beats_baseline = forecast.mape < forecast.baseline_mape

    return PriceForecast(
        model_name=forecast.model,
        points=[
            ForecastPointModel(
                horizon=p.horizon, value=p.value, lower=p.lower, upper=p.upper
            )
            for p in forecast.points
        ],
        horizon_days=forecast.horizon_days,
        expected_change_pct=forecast.expected_change_pct,
        mape=forecast.mape,
        baseline_mape=forecast.baseline_mape,
        beats_baseline=beats_baseline,
        trained_on=forecast.trained_on,
        confidence=forecast.confidence,
        notes=list(forecast.notes),
    )


def _weather_model(outlook) -> WeatherSignal | None:
    """Convert the internal WeatherOutlook dataclass into its wire schema."""
    if outlook is None:
        return None
    return WeatherSignal(
        district=outlook.district,
        state=outlook.state,
        source=outlook.source,
        live=outlook.live,
        days=[
            WeatherDay(
                day=d.day,
                rainfall_mm=d.rainfall_mm,
                max_temp_c=d.max_temp_c,
                min_temp_c=d.min_temp_c,
            )
            for d in outlook.days
        ],
        total_rain_mm=outlook.total_rain_mm,
        heavy_rain_days=outlook.heavy_rain_days,
        wet_days=outlook.wet_days,
        heat_stress_days=outlook.heat_stress_days,
        supply_risk=outlook.supply_risk,
        price_pressure=outlook.price_pressure,
        confidence=outlook.confidence,
        summary=outlook.summary,
        summary_hi=outlook.summary_hi,
    )


_orchestrator: ReActOrchestrator | None = None


def get_orchestrator() -> ReActOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ReActOrchestrator()
    return _orchestrator
