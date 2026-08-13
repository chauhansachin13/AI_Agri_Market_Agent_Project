"""Corpus construction for the RAG index (§4.5).

Three document classes are indexed, matching the report:

  1. historical daily mandi price records,
  2. seasonal price-pattern summaries per crop,
  3. agricultural market notes (arrival, storage and transport context).

Each document is written as a short natural-language sentence carrying its own
source attribution, so a retrieved passage is directly quotable as evidence by
the fact-check agent.
"""

from __future__ import annotations

from datetime import date

from ..data.sample_dataset import CROP_BASELINES, synthesize_price_series
from ..nlp.lexicon import CROP_HINDI_LABEL
from ..schemas import PriceRecord
from .faiss_store import Document

# Kept modest so the default corpus builds in well under a second; the
# deployment corpus described in the report is loaded from disk instead.
DEFAULT_HISTORY_DAYS = 30
DEFAULT_CROPS = ["Tomato", "Onion", "Wheat", "Potato", "Rice"]
DEFAULT_LOCATIONS = [
    ("Bihar", "Patna"),
    ("Bihar", "Muzaffarpur"),
    ("Bihar", "Gaya"),
    ("Uttar Pradesh", "Lucknow"),
    ("Madhya Pradesh", "Indore"),
]

SEASONAL_NOTES: dict[str, str] = {
    "Tomato": (
        "Tomato prices in the Hindi belt peak in June-July when summer crop "
        "arrivals thin out, and fall sharply from November as the winter crop "
        "reaches mandis. Short shelf life makes prices volatile week to week."
    ),
    "Onion": (
        "Onion prices typically rise between August and October as stored rabi "
        "stock depletes, and soften from December with kharif arrivals. Storage "
        "losses and export policy changes drive most large swings."
    ),
    "Wheat": (
        "Wheat prices are anchored by the Minimum Support Price and stay stable "
        "through the April-June procurement window, drifting upward in the lean "
        "months from October to February."
    ),
    "Potato": (
        "Potato prices bottom out during the February-March harvest glut and "
        "climb through the monsoon as cold-storage stock is released. Storage "
        "capacity in a district strongly affects the local price floor."
    ),
    "Rice": (
        "Paddy prices firm up during October-December kharif arrivals and hold "
        "steady afterwards, largely tracking the procurement price and the "
        "milling demand from local rice mills."
    ),
}

MARKET_NOTES: list[str] = [
    "Modal price is the price at which most transactions in a mandi took place "
    "on the arrival day; it is a better guide for a farmer than the maximum "
    "price, which usually reflects a small premium-grade lot.",
    "A wide gap between the minimum and maximum price in a mandi on the same day "
    "usually indicates mixed produce quality rather than a genuine price rise.",
    "Transport cost between districts in the Hindi belt runs roughly 40 to 90 "
    "rupees per quintal for distances under 150 km, so a price gap smaller than "
    "that between two mandis is rarely worth travelling for.",
    "Arrival volumes and prices move inversely: a sudden jump in arrivals at a "
    "mandi is usually followed by a softening of the modal price within days.",
    "Agmarknet publishes prices per quintal. One quintal is 100 kg, and one ton "
    "is 10 quintals.",
    "Prices reported on Agmarknet can lag by 24 to 48 hours in some states, so a "
    "quoted price should be read as the most recent reported arrival, not "
    "necessarily today's spot rate.",
]


def _price_document(record: PriceRecord) -> Document:
    hindi = CROP_HINDI_LABEL.get(record.commodity, record.commodity)
    text = (
        f"On {record.arrival_date}, {record.commodity} ({hindi}) traded at "
        f"{record.market} mandi in {record.district}, {record.state} with a modal "
        f"price of Rs {record.modal_price:.0f} per quintal "
        f"(range Rs {record.min_price:.0f} to Rs {record.max_price:.0f})."
    )
    return Document(
        text=text,
        metadata={
            "type": "price_record",
            "commodity": record.commodity,
            "state": record.state,
            "district": record.district,
            "market": record.market,
            "arrival_date": record.arrival_date,
            "modal_price": record.modal_price,
            "source": record.source,
        },
    )


def _seasonal_documents() -> list[Document]:
    documents: list[Document] = []
    for crop, note in SEASONAL_NOTES.items():
        base, swing = CROP_BASELINES.get(crop, (0.0, 0.0))
        text = (
            f"{crop} seasonal pattern: {note} Typical modal price is around "
            f"Rs {base:.0f} per quintal with an annual swing of about "
            f"{swing * 100:.0f} percent."
        )
        documents.append(
            Document(
                text=text,
                metadata={"type": "seasonal_summary", "commodity": crop, "source": "corpus"},
            )
        )
    return documents


def _market_note_documents() -> list[Document]:
    return [
        Document(text=note, metadata={"type": "market_note", "source": "corpus"})
        for note in MARKET_NOTES
    ]


def build_default_corpus(
    crops: list[str] | None = None,
    days: int = DEFAULT_HISTORY_DAYS,
    reference_date: date | None = None,
) -> list[Document]:
    """Assemble the default in-memory corpus."""
    crops = crops or DEFAULT_CROPS
    documents: list[Document] = []

    for state, district in DEFAULT_LOCATIONS:
        for crop in crops:
            records = synthesize_price_series(
                commodity=crop,
                state=state,
                district=district,
                days=days,
                reference_date=reference_date,
            )
            # One record per day per district — the best-price market — keeps
            # the index informative without flooding it with near-duplicates.
            by_day: dict[str, PriceRecord] = {}
            for record in records:
                current = by_day.get(record.arrival_date)
                if current is None or record.modal_price > current.modal_price:
                    by_day[record.arrival_date] = record
            documents.extend(_price_document(r) for r in by_day.values())

    documents.extend(_seasonal_documents())
    documents.extend(_market_note_documents())
    return documents
