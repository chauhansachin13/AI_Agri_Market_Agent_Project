# AI-Powered Local Agri-Market Intelligence and Farmer–Buyer Connect System

A multi-agent, bilingual, explainable AI platform that lets Indian farmers ask
about mandi prices, buyers and selling decisions in plain Hindi or English, and
answers them from **live Government of India data** — never from the language
model's memory.

> Sachin Chauhan (25CSM1S13) · M.Tech CSE, National Institute of Technology
> Warangal · Summer Internship Project

---

## The problem

India's agricultural output is not the bottleneck; what happens *after* the
harvest is. A farmer usually cannot find out which nearby mandi is paying best
for their crop today, or whether prices are likely to rise next week. Agmarknet
and eNAM publish the data, but as dense tables in English, with no
personalisation, no trend analysis and no answer to the only question that
matters: *should I sell now, or wait?*

This system closes that gap. It turns raw government price records into a
conversation in the farmer's own language, and shows its working.

## What makes it different

**Government data is the only source of truth for prices.** The LLM reasons and
explains; it is never permitted to produce a price. Every rupee figure in an
answer is traced back to a fetched record, a moving average over those records,
or arithmetic across them — and a dedicated Fact-Check Agent verifies that
claim by claim before the answer is released. Anything it cannot substantiate
is *stripped from the response*, not merely labelled.

**Every step is visible.** The reasoning trail is returned with each answer and
rendered in an Explainable AI panel. The farmer study in the report found this
to be the single most valued feature: seeing what the assistant checked is what
made participants willing to act on its advice.

**It runs without any API keys.** With no credentials configured the service
still executes the complete pipeline — deterministic tool orchestration, a
384-dimensional hashing encoder in place of the transformer, a bundled
reference dataset, and grounded response templates. Responses are flagged
`degraded: true` and the UI says so plainly, so simulated figures can never be
mistaken for live government data.

---

## Architecture

Three tiers, communicating over REST.

```
┌─────────────────────────────────────────────────────────────┐
│  Presentation — React 18 + Tailwind + Framer Motion         │
│  voice chat · mandi board · trend charts · XAI panel        │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST + JWT
┌───────────────────────────▼─────────────────────────────────┐
│  Business logic — Node.js + Express + MongoDB               │
│  auth · query history · price cache · API gateway           │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST
┌───────────────────────────▼─────────────────────────────────┐
│  Intelligence — Python + FastAPI                            │
│  ReAct orchestrator · 10 agents · 5 tools · FAISS RAG       │
└───────────────────────────┬─────────────────────────────────┘
                            │
              Agmarknet API · eNAM · Tavily · Gemini 2.5 Flash
```

### The ten agents

| Agent | Responsibility |
|---|---|
| **ReAct Orchestrator** | Drives Thought–Action–Observation cycles; selects tools dynamically |
| **Intent Detection** | Classifies into `price_query`, `buyer_search`, `sell_advice`, `trend_analysis` |
| **Location Resolution** | Resolves via text → pincode → IP → GPS, then maps to nearby mandis |
| **Mandi Intelligence** | Fetches and normalises live Agmarknet records; finds the best-price mandi |
| **Buyer Connect** | Retrieves APMC and buyer contacts from eNAM |
| **Internet Search** | Pulls current trends, demand signals and farm news via Tavily |
| **Historical Context** | FAISS similarity search over indexed price history |
| **Price Prediction** | EMA-7/14/30 trend classification with volatility-aware confidence |
| **Reasoning** | Synthesises all evidence into a structured analysis |
| **Sell Decision** | Weighs trend, range position and cross-mandi spread into SELL/WAIT |
| **Fact-Check** | Verifies each claim against government data; suppresses unsupported figures |
| **Answer Generation** | Produces the bilingual, farmer-friendly answer |

### The five tools

`mandi_prices` · `internet_search` · `resolve_location` · `historical_context` ·
`price_trend`

The same tool implementations back both execution modes, so the offline
pipeline exercises exactly the code the live agent runs.

---

## Running it

Requirements: **Python 3.11+**, **Node.js 20+**. MongoDB and all API keys are
optional.

### 1. AI service

```bash
cd ai-service
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-core.txt     # or requirements.txt for Gemini/FAISS
cp .env.example .env
OFFLINE_MODE=1 uvicorn app.main:app --reload --port 8000
```

### 2. Backend gateway

```bash
cd backend
npm install
cp .env.example .env
npm run dev
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

### Everything at once

```bash
docker compose up --build
```

---

## Trying it from the command line

```bash
curl -s -X POST http://localhost:8000/agent/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"क्या मुझे अभी गेहूं बेच देना चाहिए?"}'
```

```
intent          : sell_advice
crop            : Wheat
best mandi      : Biharsharif, Nalanda
recommendation  : WAIT (confidence 0.63)
trend           : downward
fact check      : partially_verified

पटना, बिहार के पास Biharsharif मंडी में गेहूं का भाव लगभग 2714 रुपये प्रति
क्विंटल है। … हमारी सलाह है कि अभी रुक जाएँ।
```

---

## API

### AI service (port 8000)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/agent/query` | Full multi-agent pipeline; returns the §4.7 response schema |
| `POST` | `/nlp/parse` | NLP pipeline only — intent, crop, quantity, location |
| `GET` | `/mandi/prices` | Normalised Agmarknet records |
| `GET` | `/mandi/buyers` | eNAM APMC and buyer contacts |
| `GET` | `/mandi/trend` | EMA trend classification |
| `GET` | `/mandi/series` | Daily modal price series for charting |
| `GET` | `/health` | Liveness, plus which integrations are active |

### Gateway (port 5000)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/auth/register` | — | Create an account |
| `POST` | `/api/auth/login` | — | Sign in |
| `GET` | `/api/auth/me` | ✓ | Current profile |
| `POST` | `/api/queries` | optional | Ask the assistant |
| `POST` | `/api/queries/parse` | — | Parse without answering |
| `GET` | `/api/queries/history` | ✓ | Past questions |
| `GET` | `/api/queries/stats` | — | Aggregate query statistics |
| `GET` | `/api/mandis` | — | Cached price records |
| `GET` | `/api/mandis/buyers` | — | Buyer contacts |
| `GET` | `/api/prices/trend` | — | Trend analysis |
| `GET` | `/api/prices/series` | — | Price series |
| `PATCH` | `/api/users/profile` | ✓ | Update profile |

### Response schema

```jsonc
{
  "intent": "sell_advice",
  "crop": "Wheat",
  "location": "Patna, Bihar",
  "live_mandi_prices": [ /* normalised Agmarknet records */ ],
  "buyers": [ /* eNAM APMC contacts */ ],
  "best_mandi": "Biharsharif, Nalanda",
  "trend_analysis": { "direction": "downward", "ema_7": 2260, "ema_14": 2280,
                      "ema_30": 2294, "volatility": 0.021, "confidence": 0.68 },
  "prediction": { "recommendation": "WAIT", "confidence": 0.63, "reason": "…" },
  "confidence_score": 0.477,
  "fact_check_status": "partially_verified",
  "fact_check_claims": [ { "claim": "…", "status": "verified", "evidence": ["…"] } ],
  "english_answer": "…",
  "hindi_answer": "…",
  "reasoning_steps": ["Intent Detection: …", "Mandi Intelligence: …"],
  "degraded": true
}
```

---

## Tests

```bash
cd ai-service && .venv/bin/python -m pytest tests/ -q   # 162 tests
cd backend    && npm test                               # 43 tests
cd frontend   && npm test                               # 22 tests
```

The suites run fully offline — no API keys, no database, no network.

Coverage is weighted toward the things that would actually hurt a farmer if
they broke: that a price in an answer is always traceable to a source, that a
recommendation never cites reasoning which contradicts it, that a neighbouring
district is queried under the state it truly belongs to, and that Hindi answers
come back in Devanagari rather than transliteration.

---

## Design notes

**Why a rule-based intent classifier?** Predictability. The output is advice a
farmer will act on, so the classification path stays auditable rather than
opaque. A fine-tuned multilingual model is the documented next step.

**Why is the offline dataset seeded, not random?** Reproducibility. The same
query returns the same series on every run, which is what makes the tests and
the demo trustworthy. It is tagged `source: "sample"` end to end so the
fact-checker downgrades anything resting on it.

**Why does the fact-checker recognise derived figures?** Because answers
legitimately contain arithmetic over government records — the gap between two
mandis, an average across them. An earlier version flagged its own correct
subtraction as a hallucination and silently deleted the recommendation
sentence. Traceable arithmetic is now `partially_verified` with the derivation
recorded as its evidence.

**Why is the template generator not a stub?** It is the guaranteed-grounded
generator: every number it emits is copied from a fetched record, so it cannot
hallucinate by construction. It runs when no LLM is configured, and it is also
the fallback when the LLM's output fails fact-checking.

---

## Known limitations

- Hindi speech recognition relies on the browser Web Speech API and degrades on
  Bhojpuri- and Maithili-accented speech.
- The intent classifier weakens on queries spanning two intents; multi-label
  classification is the intended fix.
- Agmarknet data freshness varies by state, lagging 24–48 hours in some. The UI
  labels record age, but cannot correct it.
- Trend analysis uses exponential moving averages, not a trained time-series
  model, so it does not capture non-linear harvest or policy shocks.

## Roadmap

WhatsApp Business API delivery · regional language expansion via IndicBERT and
NLLB-200 · LSTM/Transformer price forecasting · a transactional farmer–buyer
marketplace · a React Native offline-capable app · federated personalisation ·
IMD weather and satellite crop signals.

---

## Licence

MIT — see [LICENSE](LICENSE).

Price data belongs to the Government of India, published via
[Agmarknet](https://agmarknet.gov.in/) and [eNAM](https://www.enam.gov.in/).
Recommendations are decision support, not financial advice.
