"""Tests for the government data layer (§4.4) and the RAG pipeline (§4.5)."""

from __future__ import annotations

from datetime import date

import pytest

from app.data import agmarknet_gov, enam
from app.data.sample_dataset import synthesize_price_series
from app.rag.corpus import build_default_corpus
from app.rag.embeddings import HashingEncoder, cosine_similarity
from app.rag.faiss_store import Document, VectorStore
from app.schemas import PriceRecord


# --- Agmarknet integration --------------------------------------------------
def test_offline_fetch_returns_records_and_flags_degradation():
    result = agmarknet_gov.fetch_prices(commodity="Wheat", state="Bihar", district="Patna")
    assert result.records
    assert result.degraded is True
    assert all(r.source == "sample" for r in result.records)


def test_fetch_respects_the_record_limit():
    result = agmarknet_gov.fetch_prices(commodity="Wheat", state="Bihar", limit=3)
    assert len(result.records) <= 3


def test_price_record_computes_its_own_range():
    record = PriceRecord(
        state="Bihar", district="Patna", market="Patna City", commodity="Wheat",
        arrival_date="2026-08-01", min_price=2200, max_price=2400, modal_price=2300,
    )
    assert record.price_range == 200.0


def test_normalise_handles_alternate_portal_field_casing():
    raw = {
        "State": "Bihar", "District": "Patna", "Market": "Patna City",
        "Commodity": "Wheat", "Arrival_Date": "2026-08-01",
        "Min_Price": "2,200", "Max_Price": "2,400", "Modal_Price": "2,300",
    }
    record = agmarknet_gov._normalise(raw)
    assert record is not None
    assert record.modal_price == 2300.0
    assert record.state == "Bihar"


def test_normalise_rejects_a_record_without_a_usable_price():
    assert agmarknet_gov._normalise({"market": "X", "commodity": "Wheat", "modal_price": "0"}) is None


def test_normalise_rejects_a_record_without_a_market():
    assert agmarknet_gov._normalise({"commodity": "Wheat", "modal_price": "2300"}) is None


def test_best_price_mandi_picks_the_highest_modal():
    records = agmarknet_gov.fetch_prices(commodity="Onion", state="Bihar").records
    best = agmarknet_gov.best_price_mandi(records)
    assert best.modal_price == max(r.modal_price for r in records)


def test_best_price_mandi_of_empty_list_is_none():
    assert agmarknet_gov.best_price_mandi([]) is None


def test_price_dispersion_is_zero_for_a_single_record():
    records = agmarknet_gov.fetch_prices(commodity="Wheat", state="Bihar", limit=1).records
    assert agmarknet_gov.price_dispersion_index(records) == 0.0


def test_price_dispersion_is_positive_when_mandis_differ():
    records = agmarknet_gov.fetch_prices(commodity="Wheat", state="Bihar").records
    assert agmarknet_gov.price_dispersion_index(records) > 0


# --- deterministic dataset --------------------------------------------------
def test_sample_dataset_is_reproducible():
    reference = date(2026, 5, 1)
    first = synthesize_price_series("Wheat", "Bihar", "Patna", days=5, reference_date=reference)
    second = synthesize_price_series("Wheat", "Bihar", "Patna", days=5, reference_date=reference)
    assert [r.modal_price for r in first] == [r.modal_price for r in second]


def test_sample_dataset_spans_the_requested_number_of_days():
    series = synthesize_price_series("Wheat", "Bihar", "Patna", days=10)
    assert len({r.arrival_date for r in series}) == 10


def test_sample_prices_are_ordered_min_modal_max():
    for record in synthesize_price_series("Tomato", "Bihar", "Patna", days=3):
        assert record.min_price <= record.modal_price <= record.max_price


def test_price_series_has_no_month_boundary_discontinuity():
    """The synthetic drift must be smooth across a month boundary.

    Keying the drift to the day of the month produced a sawtooth that the EMA
    model read as a genuine trend reversal every 30 days.
    """
    series = synthesize_price_series(
        "Wheat", "Bihar", "Patna", days=8, reference_date=date(2026, 6, 3)
    )
    by_date = {}
    for record in series:
        if record.market == "Patna City":
            by_date[record.arrival_date] = record.modal_price
    prices = [price for _, price in sorted(by_date.items())]
    steps = [abs(b - a) / a for a, b in zip(prices, prices[1:])]
    assert max(steps) < 0.10  # no single-day jump above 10%


# --- eNAM integration -------------------------------------------------------
def test_buyer_lookup_returns_contacts():
    result = enam.fetch_buyers(state="Bihar", district="Patna")
    assert result.buyers
    assert all(b.apmc_name for b in result.buyers)


def test_buyer_lookup_never_returns_empty_for_an_unstocked_crop():
    # An APMC list with no commodity metadata is still more useful than nothing.
    result = enam.fetch_buyers(state="Bihar", district="Patna", commodity="Dragonfruit")
    assert result.buyers


def test_buyer_lookup_respects_the_limit():
    result = enam.fetch_buyers(state="Bihar", limit=2)
    assert len(result.buyers) <= 2


# --- embeddings -------------------------------------------------------------
def test_hashing_encoder_produces_unit_norm_vectors_of_the_right_size():
    encoder = HashingEncoder(384)
    vector = encoder.encode_one("tomato price in Patna mandi")
    assert len(vector) == 384
    assert 0.99 < sum(v * v for v in vector) ** 0.5 < 1.01


def test_encoder_is_deterministic():
    encoder = HashingEncoder(384)
    assert encoder.encode_one("wheat price") == encoder.encode_one("wheat price")


def test_related_text_scores_higher_than_unrelated():
    encoder = HashingEncoder(384)
    probe = encoder.encode_one("tomato modal price in Patna mandi")
    related = encoder.encode_one("tomato traded at Patna mandi with modal price")
    unrelated = encoder.encode_one("irrigation pump maintenance schedule")
    assert cosine_similarity(probe, related) > cosine_similarity(probe, unrelated)


def test_empty_text_encodes_without_error():
    assert len(HashingEncoder(384).encode_one("")) == 384


def test_cosine_similarity_of_mismatched_vectors_is_zero():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0


# --- vector store -----------------------------------------------------------
@pytest.fixture
def small_store():
    store = VectorStore()
    store.add(
        [
            Document(
                text="Tomato traded at Patna City mandi with a modal price of Rs 1800 per quintal.",
                metadata={"commodity": "Tomato", "market": "Patna City", "source": "sample"},
            ),
            Document(
                text="Wheat traded at Ludhiana mandi with a modal price of Rs 2400 per quintal.",
                metadata={"commodity": "Wheat", "market": "Ludhiana", "source": "sample"},
            ),
            Document(
                text="Onion prices usually rise between August and October across north India.",
                metadata={"commodity": "Onion", "source": "corpus"},
            ),
        ]
    )
    return store


def test_search_ranks_the_relevant_document_first(small_store):
    hits = small_store.search("tomato price at Patna City mandi", k=3)
    assert hits[0].document.metadata["commodity"] == "Tomato"


def test_search_respects_k(small_store):
    assert len(small_store.search("price", k=2)) == 2


def test_search_k_is_clamped_to_corpus_size(small_store):
    assert len(small_store.search("price", k=50)) == 3


def test_search_on_an_empty_index_returns_nothing():
    assert VectorStore().search("anything") == []


def test_document_citation_carries_its_source(small_store):
    hits = small_store.search("wheat Ludhiana", k=1)
    assert "sample" in hits[0].document.citation


def test_store_round_trips_through_disk(small_store, tmp_path):
    path = tmp_path / "corpus.json"
    small_store.save(path)
    reloaded = VectorStore()
    assert reloaded.load(path) == 3
    assert len(reloaded) == 3


def test_loading_a_missing_corpus_returns_zero(tmp_path):
    assert VectorStore().load(tmp_path / "absent.json") == 0


# --- corpus -----------------------------------------------------------------
def test_default_corpus_contains_all_three_document_types():
    documents = build_default_corpus(crops=["Tomato"], days=3)
    types = {d.metadata.get("type") for d in documents}
    assert {"price_record", "seasonal_summary", "market_note"} <= types


def test_corpus_price_documents_state_a_price():
    documents = build_default_corpus(crops=["Wheat"], days=2)
    price_docs = [d for d in documents if d.metadata.get("type") == "price_record"]
    assert price_docs
    assert all("modal price" in d.text for d in price_docs)
