"""Personalisation, federated aggregation and net realisation (§6.3)."""

from __future__ import annotations

import pytest

from app.agents.specialists import AgentContext, IntentDetectionAgent, SellDecisionAgent
from app.personalize.federated import (
    CLIP_NORM,
    MIN_CLIENTS,
    SIGNALS,
    aggregate,
    add_noise,
    clip,
    compute_local_update,
    prepare_update,
)
from app.personalize.profile import FarmerProfile, personalise
from app.personalize.transport import (
    best_net,
    distance_between,
    net_realisations,
    transport_cost,
)
from app.schemas import PriceRecord


def _price(market: str, modal: float, district: str = "Patna", state: str = "Bihar"):
    return PriceRecord(
        state=state, district=district, market=market, commodity="Wheat",
        arrival_date="2026-08-01", min_price=modal - 50, max_price=modal + 50,
        modal_price=modal, source="sample",
    )


# --------------------------------------------------------------------------- #
# Profile
# --------------------------------------------------------------------------- #
def test_no_profile_means_no_adjustment():
    """An anonymous farmer must get the unmodified, evidence-only call."""
    result = personalise(None, "Wheat")
    assert result.threshold_shift == 0.0
    assert result.applied is False


def test_a_patient_farmer_is_nudged_towards_holding():
    result = personalise(FarmerProfile(risk_tolerance="patient"), "Wheat")
    assert result.threshold_shift > 0


def test_a_cautious_farmer_is_nudged_towards_selling():
    result = personalise(FarmerProfile(risk_tolerance="cautious"), "Wheat")
    assert result.threshold_shift < 0


def test_storage_only_helps_for_a_crop_that_stores():
    """Telling someone to wait is useless if the crop rots meanwhile."""
    storable = personalise(FarmerProfile(has_storage=True), "Wheat")
    perishable = personalise(FarmerProfile(has_storage=True), "Tomato")
    assert storable.threshold_shift > perishable.threshold_shift


def test_a_perishable_crop_always_leans_towards_selling():
    assert personalise(FarmerProfile(), "Tomato").threshold_shift < 0


def test_a_poor_track_record_leans_towards_selling():
    profile = FarmerProfile(outcomes=(False, False, False, True))
    assert personalise(profile, "Wheat").threshold_shift < 0


def test_history_is_ignored_until_there_is_enough_of_it():
    """Two observations is noise, not a pattern."""
    thin = FarmerProfile(outcomes=(False, False))
    assert personalise(thin, "Wheat").threshold_shift == 0.0


def test_every_adjustment_states_its_reason():
    """A farmer must be able to see why their advice differs from a neighbour's."""
    result = personalise(FarmerProfile(risk_tolerance="patient", has_storage=True), "Wheat")
    assert result.reasons
    assert all(isinstance(r, str) and r for r in result.reasons)


def test_personalisation_can_flip_a_borderline_call():
    """The whole point: identical prices, different farmers, different advice.

    A shift that could never change an outcome would be decoration.
    """
    def decide(profile):
        nlp = IntentDetectionAgent().run("should i sell wheat").nlp
        context = AgentContext(query="should i sell wheat", nlp=nlp)
        # Two mandis a hair apart: the evidence is genuinely balanced.
        context.prices = [_price("A", 2000), _price("B", 1995)]
        context.profile = profile
        SellDecisionAgent().run(context)
        return context.prediction.recommendation

    cautious = decide(FarmerProfile(risk_tolerance="cautious"))
    patient = decide(FarmerProfile(risk_tolerance="patient", has_storage=True))
    assert cautious == "SELL"
    assert patient == "WAIT"


# --------------------------------------------------------------------------- #
# Federated aggregation
# --------------------------------------------------------------------------- #
def test_an_update_carries_only_aggregate_signals():
    """Raw history must never be in what leaves the device."""
    update = compute_local_update(0.5, 1.0, 0.8, 0.2, observations=10)
    assert set(update.values) == set(SIGNALS)


def test_clipping_bounds_a_single_client_contribution():
    """Without a bound, one client could dominate a round or poison it."""
    huge = compute_local_update(100.0, 100.0, 100.0, 100.0, observations=1)
    clipped = clip(huge)
    assert clipped.norm() <= CLIP_NORM + 1e-9
    assert clipped.clipped is True


def test_a_small_update_is_left_alone_by_clipping():
    small = compute_local_update(0.1, 0.1, 0.1, 0.1, observations=1)
    assert clip(small).clipped is False


def test_noise_actually_changes_the_transmitted_values():
    update = compute_local_update(0.5, 0.5, 0.5, 0.5, observations=5)
    noised = add_noise(update, seed="fixed")
    assert noised.noised is True
    assert any(noised.values[s] != update.values[s] for s in SIGNALS)


def test_noise_is_reproducible_for_a_given_seed():
    a = add_noise(compute_local_update(0.5, 0.5, 0.5, 0.5, 5), seed="same")
    b = add_noise(compute_local_update(0.5, 0.5, 0.5, 0.5, 5), seed="same")
    assert a.values == b.values


def test_a_nonpositive_epsilon_is_refused():
    with pytest.raises(ValueError):
        add_noise(compute_local_update(0.1, 0.1, 0.1, 0.1, 1), epsilon=0)


def test_the_client_pipeline_clips_before_it_noises():
    """Noising first would shrink the noise with the signal and void the guarantee."""
    prepared = prepare_update(compute_local_update(50.0, 50.0, 50.0, 50.0, 3), seed="x")
    assert prepared.clipped is True
    assert prepared.noised is True


def test_a_round_with_too_few_clients_is_refused():
    """Averaging two updates would let the server back out an individual's."""
    updates = [prepare_update(compute_local_update(0.5, 0.5, 0.5, 0.5, 3), seed=str(i))
               for i in range(MIN_CLIENTS - 1)]
    with pytest.raises(ValueError, match="at least"):
        aggregate(updates)


def test_aggregation_produces_a_population_model():
    updates = [prepare_update(compute_local_update(0.6, 0.9, 0.8, 0.2, 8), seed=str(i))
               for i in range(6)]
    model = aggregate(updates)
    assert model.rounds == 1
    assert model.clients_seen == 6
    assert set(model.values) == set(SIGNALS)


def test_rounds_accumulate_without_one_round_dominating():
    first = aggregate([prepare_update(compute_local_update(1, 1, 1, 1, 5), seed=f"a{i}")
                       for i in range(5)])
    before = dict(first.values)
    second = aggregate(
        [prepare_update(compute_local_update(-1, -1, -1, -1, 5), seed=f"b{i}") for i in range(5)],
        model=first,
    )
    assert second.rounds == 2
    # A single opposing round must move, but not overwrite, the shared model.
    assert second.values != before


# --------------------------------------------------------------------------- #
# Net realisation
# --------------------------------------------------------------------------- #
def test_a_local_mandi_costs_nothing_to_reach():
    assert distance_between(("Bihar", "Patna"), ("Bihar", "Patna")) == 0.0
    assert transport_cost(0) == 0.0


def test_transport_cost_grows_with_distance():
    assert transport_cost(150) > transport_cost(50) > 0


def test_net_price_is_gross_minus_transport():
    rows = net_realisations([_price("Far", 2500, "Bhagalpur")], ("Bihar", "Patna"))
    row = rows[0]
    assert row.net_price == pytest.approx(row.gross_price - row.transport_cost, abs=0.01)


def test_a_distant_mandi_can_lose_to_a_closer_cheaper_one():
    """The reason this exists: a headline price can be swallowed by the journey."""
    records = [
        _price("Distant", 2600, "Bhagalpur"),   # ~190 km from Patna
        _price("Local", 2560, "Patna"),
    ]
    best = best_net(records, ("Bihar", "Patna"))
    assert best.market == "Local"


def test_a_genuinely_better_mandi_still_wins_after_transport():
    records = [
        _price("Distant", 3000, "Bhagalpur"),
        _price("Local", 2560, "Patna"),
    ]
    assert best_net(records, ("Bihar", "Patna")).market == "Distant"


def test_unknown_geography_is_treated_as_local_rather_than_guessed():
    """Inventing a distance would silently penalise a real option."""
    assert distance_between(("Bihar", "Nowhere"), ("Bihar", "Elsewhere")) == 0.0
