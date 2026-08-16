# AI-Powered Local Agri-Market Intelligence and Farmer–Buyer Connect System

A multi-agent, multilingual, explainable AI platform that lets Indian farmers
ask about mandi prices, buyers and selling decisions in **their own language** —
Hindi, Bhojpuri, Maithili, Marathi, Bengali, Tamil or English — and answers them
from **live Government of India data**, never from the language model's memory.

Farmers can reach it through the web app or over **WhatsApp**, see a **trained
price forecast** for the week ahead, get a **weather-driven supply warning**,
and sell directly through a **farmer–buyer marketplace**.

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

| **Price Forecasting** | Fits a trained model to the price history and projects it forward |
| **Weather Impact** | Turns the district forecast into an anticipated supply signal |

### The seven tools

`mandi_prices` · `internet_search` · `resolve_location` · `historical_context` ·
`price_trend` · `price_forecast` · `weather_outlook`

The same tool implementations back both execution modes, so the offline
pipeline exercises exactly the code the live agent runs.

### Channels

| Surface | What it offers |
|---|---|
| Web app | Voice chat, mandi board, trend + forecast charts, XAI panel, marketplace |
| WhatsApp | The same answers over the channel rural India actually uses |

### Languages

हिंदी · भोजपुरी · मैथिली · मराठी · বাংলা · தமிழ் · English

Detection separates the four Devanagari languages by dialect markers, including
morphological ones. See [docs/LANGUAGES.md](docs/LANGUAGES.md).

---

## Running it

Requirements: **Python 3.11+** and **Node.js 20+**. That is all — MongoDB and
every API key are optional.

```bash
git clone https://github.com/chauhansachin13/AI_Agri_Market_Agent_Project.git
cd AI_Agri_Market_Agent_Project
./run.sh
```

That installs everything, builds the frontend, starts both services and prints
the URL — the whole app on **one port**, typically <http://localhost:4000>.

| Command | What it does |
|---|---|
| `./run.sh` | Build and serve everything on one port |
| `./run.sh dev` | Hot-reloading dev servers (Vite on 5173) |
| `./run.sh test` | Run all three test suites |
| `./run.sh stop` | Stop everything it started |
| `docker compose up --build` | Same thing, in containers |

It picks a free port if the default is taken — worth knowing on macOS, where
AirPlay Receiver permanently occupies port 5000.

### Running the pieces separately

<details>
<summary>Manual, three-terminal setup</summary>

#### 1. AI service

```bash
cd ai-service
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-core.txt     # or requirements.txt for Gemini/FAISS
cp .env.example .env
OFFLINE_MODE=1 uvicorn app.main:app --reload --port 8000
```

#### 2. Backend gateway

```bash
cd backend
npm install
cp .env.example .env
npm run dev
```

#### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>.

</details>

## Deploying it

The gateway serves the built frontend, so the whole product is **two services**:
the Python AI service, and one Node service that is both the API and the web
app. Neither needs a secret to boot.

### Render (one click, free tier)

The repo ships a [`render.yaml`](render.yaml) blueprint:

1. Render dashboard → **New** → **Blueprint** → pick this repo
2. Deploy

It wires the gateway to the AI service automatically and generates a
`JWT_SECRET`. Add any API keys afterwards in the dashboard — the app runs
offline against its bundled dataset until you do, and labels every answer
accordingly.

### Docker

```bash
docker compose up --build
```

Two containers; the app is on <http://localhost:4000>.

### Anywhere else

Any host that can run a Node process and a Python process will do:

```bash
# AI service
cd ai-service && pip install -r requirements-core.txt
uvicorn app.main:app --host 0.0.0.0 --port $PORT

# Web app + API (build the frontend first)
cd frontend && npm ci && npm run build
cd ../backend && npm ci && NODE_ENV=production node src/server.js
```

Set `AI_SERVICE_URL` on the gateway to wherever the AI service is listening. A
bare `host:port` is fine — the scheme is filled in automatically. In production
`JWT_SECRET` must be set to a real secret; the server refuses to start
otherwise.

Both services expose `/health`, which also reports which integrations are
active — use it as your platform's health check.

### Going live

Everything above runs offline against the bundled dataset, and every answer
says so. To use real data, put the keys you have in `ai-service/.env` — each one
is independent, and the system reports which are active on `/health`:

| Key | Enables |
|---|---|
| `AGMARKNET_API_KEY` | Live government mandi prices ([data.gov.in](https://data.gov.in)) |
| `GEMINI_API_KEY` | The Gemini ReAct loop and LLM-written answers |
| `TAVILY_API_KEY` | Internet search for market news |
| `MONGO_URI` | Persistent accounts, history and listings |
| `WHATSAPP_*` | The WhatsApp channel (see `backend/.env.example`) |

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
| `GET` | `/mandi/forecast` | Trained forecast with prediction intervals |
| `GET` | `/weather/outlook` | Weather outlook and its supply implication |
| `GET` | `/languages` | Supported languages, for the picker |
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
| `GET` | `/api/prices/forecast` | — | Trained price forecast |
| `GET` | `/api/prices/weather` | — | Weather supply signal |
| `PATCH` | `/api/users/profile` | ✓ | Update profile |
| `GET` | `/api/market/listings` | — | Browse produce listings |
| `POST` | `/api/market/listings` | ✓ | List your produce |
| `POST` | `/api/market/listings/:id/offers` | ✓ | Bid on a listing |
| `POST` | `/api/market/offers/:id/accept` | ✓ | Accept a bid (closes the rest) |
| `GET` | `/api/whatsapp/webhook` | — | Meta verification handshake |
| `POST` | `/api/whatsapp/webhook` | HMAC | Inbound WhatsApp messages |

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

## Tests and measured accuracy

```bash
./run.sh test                                          # all three suites
cd ai-service && .venv/bin/python -m eval.run_eval     # accuracy report
```

The suites run fully offline — no API keys, no database, no network.

```bash
cd ai-service && .venv/bin/python -m pytest tests/ -q   # 289 tests
cd backend    && npm test                               # 108 tests
cd frontend   && npm test                               # 40 tests
```

### What the accuracy harness measures

A held-out set of **124 labelled queries across all seven languages**, covering
the four intents plus the tail that actually breaks parsers: code-switching,
romanised Hindi, Marathi/Bengali/Tamil case inflection, plurals, terse
fragments, pincodes, districts named in every supported script, and questions
that sit genuinely between two intents.

| Metric | Measured | Report target |
|---|---|---|
| Intent classification accuracy | **99.2%** | ≥ 90% |
| Intent weighted F1 | **0.992** | — |
| Language detection accuracy | **99.2%** | — |
| Crop extraction accuracy | **100%** | ≥ 90% |
| Location resolution accuracy | **100%** | ≥ 85% |
| Price claims traceable to a source | **100%** (326/326) | ≥ 95% |
| Unsupported figures reaching an answer | **0** | 0 |
| Forecast beats the naive baseline | **91.4%** of series | — |
| Mean forecast error reduction vs naive | **57.2%** | — |
| End-to-end latency (offline) | 31 ms mean, 40 ms p95 | < 3 s |

Per-intent:

| Intent | Precision | Recall | F1 | n |
|---|---|---|---|---|
| price_query | 0.985 | 1.000 | 0.992 | 64 |
| buyer_search | 1.000 | 1.000 | 1.000 | 21 |
| sell_advice | 1.000 | 1.000 | 1.000 | 21 |
| trend_analysis | 1.000 | 0.944 | 0.971 | 18 |

**Read these honestly.** Two caveats matter:

- The forecast figures are measured on the bundled reference series, which is
  generated from smooth seasonal curves that a linear autoregressor fits far
  more easily than real mandi prices. The *skill score* — how often it beats
  the naive baseline on the same series — is the meaningful number; the
  absolute error is a sanity check on the implementation, not a real-world
  claim. The harness prints this warning itself.
- The evaluation set was authored alongside the system, so it measures whether
  the pipeline handles the phenomena it was built for, not how it performs on
  unseen traffic.

The thresholds are pinned as tests (`tests/test_accuracy.py`) and run in CI, so
an accuracy regression fails the build rather than waiting to be noticed.

Coverage is otherwise weighted toward what would actually hurt a farmer: that a
price in an answer is always traceable, that a recommendation never cites
reasoning which contradicts it, that a neighbouring district is queried under
the state it truly belongs to, and that answers come back in the script they
were asked in.

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
hallucinate by construction. It also means nothing that matters is
machine-translated — a mistranslated "₹2,714 per quintal" is a real risk to a
farmer. It runs when no LLM is configured, for every language, and it is the
fallback when the LLM's output fails fact-checking.

**Why report a forecast's error next to a baseline?** Because a confidently
drawn projection that cannot beat guessing would still move the sell/wait
advice. Confidence is scaled by measured skill, and the UI says plainly when a
model is no better than a naive guess. See
[docs/FORECASTING.md](docs/FORECASTING.md).

---

## Known limitations

- Speech recognition relies on the browser Web Speech API. Bhojpuri and
  Maithili have no recogniser and borrow Hindi, which degrades on those accents.
- The intent classifier weakens on queries spanning two intents; multi-label
  classification is the intended fix.
- Agmarknet data freshness varies by state, lagging 24–48 hours in some. The UI
  labels record age, but cannot correct it.
- The forecaster sees only price history. Arrival volumes, MSP announcements and
  export policy all move prices and none are inputs. Recursive multi-step
  forecasting compounds error beyond about two weeks.
- The offline dataset is smooth by construction, so backtested errors on it
  flatter the model; real Agmarknet series are noisier.
- The marketplace has no payments, escrow or identity verification. It connects
  a farmer to a buyer; the transaction itself happens offline.

## Still on the roadmap

A React Native offline-capable mobile app, federated learning for
personalisation without centralising farmer data, and satellite-based crop
monitoring alongside the weather signal.

---

## Licence

MIT — see [LICENSE](LICENSE).

Price data belongs to the Government of India, published via
[Agmarknet](https://agmarknet.gov.in/) and [eNAM](https://www.enam.gov.in/).
Recommendations are decision support, not financial advice.
