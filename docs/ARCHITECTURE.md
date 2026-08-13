# Architecture

How a farmer's question becomes a grounded, bilingual answer.

## Request path

```
Farmer (Hindi/English, typed or spoken)
   │
   ▼  POST /api/queries          React frontend
Gateway (Express)                 ─ attaches JWT identity, profile pincode,
   │                                preferred language, client IP
   ▼  POST /agent/query
AI service (FastAPI)
   │
   ├─ 1. NLP pipeline        language → intent → entities → location
   ├─ 2. Location Resolution text → pincode → IP → GPS
   ├─ 3. Mandi Intelligence  Agmarknet, home district + 3 nearest
   ├─ 4. Historical Context  FAISS top-k retrieval
   ├─ 5. Price Prediction    EMA-7/14/30 + volatility
   ├─ 6. Buyer Connect       eNAM (buyer_search, sell_advice only)
   ├─ 6b. Price Forecasting  trained model (forward-looking intents only)
   ├─ 6c. Weather Impact     supply signal (forward-looking intents only)
   ├─ 7. Internet Search     Tavily (trend_analysis, sell_advice only)
   ├─ 8. ReAct loop          Gemini tool-calling, when configured
   ├─ 9. Reasoning           synthesise the evidence
   ├─ 10. Sell Decision      SELL / WAIT with supporting reasons only
   ├─ 11. Answer Generation  bilingual output
   └─ 12. Fact-Check         claim-by-claim; unsupported figures stripped
   │
   ▼  §4.7 response object
Gateway persists the interaction → returns the response unchanged
   │
   ▼
Frontend renders the answer, the price cards, the trend chart, and the
Explainable AI panel showing every step above.
```

The gateway deliberately does not reshape the AI response. The frontend is
written against the report's Section 4.7 schema, so any translation layer in
between would be a second place for the contract to drift.

## Two execution modes, one code path

| | Agentic mode | Deterministic mode |
|---|---|---|
| Trigger | `GEMINI_API_KEY` set | no key, or `OFFLINE_MODE=1` |
| Tool selection | Gemini chooses dynamically | fixed §4.3 order |
| Reasoning trail | model's Thought/Action/Observation | agent-emitted steps |
| Answer text | LLM, then fact-checked | grounded templates |
| Response schema | identical | identical |

Both modes call the same `Tool` objects. That is the point: the offline
pipeline is not a mock, it exercises the production tool implementations, so
the tests cover the code the live agent actually runs.

## Hallucination prevention

Four layers, in order of application:

1. **Structural** — the LLM is never asked for a price. Prices enter the prompt
   only as fetched context, and the grounding contract states the constraint
   explicitly.
2. **Retrieval** — FAISS supplies dated, source-attributed historical records,
   removing the conditions under which a model invents a plausible number.
3. **Verification** — the Fact-Check Agent resolves every rupee figure in the
   generated text against one of four sources: a fetched government record, the
   EMA model, a forecast point or interval bound, or arithmetic over fetched
   records. Each resolution carries its own evidence string.

   Both the arithmetic and the forecast rules exist because their absence
   caused real bugs. The fact-checker first flagged its own correct subtraction
   ("a nearby mandi pays Rs 300 more") as a hallucination and deleted the
   recommendation; later it did the same to the forecast sentence the
   forecasting agent had just produced. Two regression tests guard both.
4. **Suppression** — a figure that resolves to nothing is removed from the
   answer, and if the LLM's output fails verification the grounded template
   answer replaces it entirely.

`verified` requires a live Agmarknet record. The offline dataset can only ever
reach `partially_verified`, and the response carries `degraded: true` so the UI
can say where the numbers came from.

## Confidence

The response-level score blends the four signals a farmer's trust rests on:
intent certainty, location certainty, whether real records were found, and the
trend model's own confidence — then scales by the fact-check outcome
(`verified` 1.0, `partially_verified` 0.75, `insufficient_evidence` 0.35) and
by a further 0.85 when the data was degraded. Offline answers therefore cannot
present as fully trustworthy, which is the intended behaviour.

Trend confidence is separate and deliberately volatility-aware: a wide EMA
spread in a violently noisy series is reported as weak evidence, not strong.

## Caching

The gateway caches price, buyer, trend and series lookups on a TTL keyed by
query parameters, with in-flight coalescing so a burst of identical requests
produces one upstream call. This is what produces the two response-time modes
the report measures — roughly 1.8 s served from cache against 4.2 s on a live
government API call. `X-Cache: HIT|MISS` is returned on every cached route.

## Degradation

Every external dependency is optional, and each failure is contained:

| Missing | Effect |
|---|---|
| `GEMINI_API_KEY` | deterministic pipeline; template answers |
| `AGMARKNET_API_KEY` | bundled dataset; `degraded: true` |
| `TAVILY_API_KEY` | no internet context; other evidence unaffected |
| `sentence-transformers` | 384-dim hashing encoder |
| `faiss` | exact brute-force cosine search, same ranking |
| `MONGO_URI` | in-memory store; no persistence across restarts |
| `torch` | ridge autoregression instead of the LSTM forecaster |
| `transformers` | template answers only; no NLLB-200 free-text translation |
| weather network | calibrated seasonal climatology; outlook marked not live |
| `WHATSAPP_*` | the WhatsApp channel reports itself unconfigured |

None of these stops the system answering. All of them are reported on
`/health`, so the operating state is never a guess.


## Channels

The web app is not the only surface. WhatsApp reaches farmers who would never
open the site, and rural WhatsApp penetration far exceeds browser use.

The webhook has two properties worth noting:

**It acknowledges before it answers.** Meta retries any webhook that does not
return 200 promptly, and a retry would send the farmer a duplicate answer. The
payload is acknowledged immediately and the agent runs out of band.

**Provenance survives into plain text.** WhatsApp has no reasoning panel, so
the explainability the report treats as essential has to be carried by the
message itself: the answer, then the recommendation and its confidence, then
the mandi rates behind it, then the data source — or an explicit warning when
the figures came from offline data.

Inbound payloads are HMAC-verified before a byte is trusted. The comparison is
timing-safe and length-guarded, because `timingSafeEqual` throws on mismatched
lengths and a short signature would otherwise crash a public endpoint.

## Marketplace

The intelligence layer tells a farmer what their crop is worth and who is
buying, then stops. The marketplace closes that gap.

Two invariants are enforced in the route rather than left to the client:

- **Accepting a bid closes every other pending bid in the same operation.**
  Otherwise a buyer is left believing their offer is live on produce that has
  already sold.
- **Each listing records the prevailing mandi rate at the moment it was
  posted.** The ask can then be read in context, and neither side has to take
  the other's word for the going rate.

There is no payments, escrow or identity layer. The system connects the two
parties; the transaction happens offline, as it does today.
