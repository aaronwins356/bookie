from __future__ import annotations

import pytest

from src.models import MarketState
from src.sports.tennis.fair_value import TennisFairValueModel, TennisFairValueResult
from src.sports.tennis.features import TennisFeatureExtractor
from src.sports.tennis.state import Server, Surface, TennisState


def _state(**kwargs) -> TennisState:
    defaults = dict(match_id="m1", player_a="A", player_b="B", best_of=3)
    return TennisState(**{**defaults, **kwargs})


def _market(mid: float = 50.0, spread: float = 2.0) -> MarketState:
    return MarketState(
        market_id="MKT-001",
        game_id="m1",
        title="test",
        yes_ask=mid + spread / 2,
        yes_bid=mid - spread / 2,
        volume=300,
        open_interest=150,
    )


def _estimate(state_kwargs: dict, mid: float = 50.0) -> TennisFairValueResult:
    state = _state(**state_kwargs)
    market = _market(mid=mid)
    features = TennisFeatureExtractor().extract(state, market)
    return TennisFairValueModel().estimate(features, state)


class TestFairValueRange:
    def test_probability_between_0_and_1(self):
        r = _estimate({})
        assert 0.02 <= r.fair_probability <= 0.98

    def test_fair_value_cents_matches_probability(self):
        r = _estimate({})
        assert r.fair_value_cents == pytest.approx(r.fair_probability * 100.0, abs=0.01)

    def test_confidence_in_range(self):
        r = _estimate({})
        assert 0.0 <= r.confidence <= 1.0

    def test_reasons_is_list(self):
        r = _estimate({})
        assert isinstance(r.reasons, list)
        assert len(r.reasons) > 0

    def test_heuristic_warning_present(self):
        r = _estimate({})
        combined = " ".join(r.reasons)
        assert "HEURISTIC" in combined


class TestSetScoreEffect:
    def test_a_leads_sets_gives_higher_fair(self):
        a_leads = _estimate({"sets_a": 1, "sets_b": 0})
        even = _estimate({"sets_a": 0, "sets_b": 0})
        assert a_leads.fair_probability > even.fair_probability

    def test_b_leads_sets_gives_lower_fair(self):
        b_leads = _estimate({"sets_a": 0, "sets_b": 1})
        even = _estimate({"sets_a": 0, "sets_b": 0})
        assert b_leads.fair_probability < even.fair_probability

    def test_a_won_match_gives_near_1(self):
        r = _estimate({"sets_a": 2, "sets_b": 0})
        assert r.fair_probability >= 0.90

    def test_b_won_match_gives_near_0(self):
        r = _estimate({"sets_a": 0, "sets_b": 2})
        assert r.fair_probability <= 0.10


class TestServerEffect:
    def test_a_serving_boosts_fair(self):
        serving = _estimate({"server": Server.A, "surface": Surface.GRASS})
        not_serving = _estimate({"server": Server.B, "surface": Surface.GRASS})
        assert serving.fair_probability > not_serving.fair_probability

    def test_grass_server_boost_higher_than_clay(self):
        grass = _estimate({"server": Server.A, "surface": Surface.GRASS})
        clay = _estimate({"server": Server.A, "surface": Surface.CLAY})
        assert grass.fair_probability > clay.fair_probability


class TestTiebreakEffect:
    def test_tiebreak_reduces_confidence(self):
        tb = _estimate({"tiebreak": True, "games_a": 6, "games_b": 6})
        normal = _estimate({})
        assert tb.confidence < normal.confidence

    def test_tiebreak_point_lead_shifts_fair(self):
        leading = _estimate({"tiebreak": True, "points_a": 5, "points_b": 2})
        trailing = _estimate({"tiebreak": True, "points_a": 2, "points_b": 5})
        assert leading.fair_probability > trailing.fair_probability


class TestSuspendedRetired:
    def test_suspended_reduces_confidence(self):
        susp = _estimate({"suspended": True})
        normal = _estimate({})
        assert susp.confidence < normal.confidence

    def test_retired_a_ahead_gives_near_1(self):
        r = _estimate({"retired": True, "sets_a": 1, "sets_b": 0})
        assert r.fair_probability >= 0.95

    def test_retired_b_ahead_gives_near_0(self):
        r = _estimate({"retired": True, "sets_a": 0, "sets_b": 1})
        assert r.fair_probability <= 0.05


class TestEdgeCents:
    def test_edge_positive_when_fair_above_mid(self):
        r = _estimate({"sets_a": 2, "sets_b": 0}, mid=50.0)
        edge = r.edge_cents(50.0)
        assert edge > 0

    def test_edge_negative_when_fair_below_mid(self):
        r = _estimate({"sets_a": 0, "sets_b": 2}, mid=50.0)
        edge = r.edge_cents(50.0)
        assert edge < 0

    def test_edge_zero_when_fair_equals_mid(self):
        r = _estimate({})
        edge = r.edge_cents(r.fair_value_cents)
        assert edge == pytest.approx(0.0, abs=0.01)
