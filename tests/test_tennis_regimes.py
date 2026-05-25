from __future__ import annotations

import pytest

from src.models import MarketState
from src.sports.tennis.features import TennisFeatureExtractor
from src.sports.tennis.regimes import RegimeResult, TennisRegime, TennisRegimeClassifier
from src.sports.tennis.state import Server, TennisState


def _state(**kwargs) -> TennisState:
    defaults = dict(match_id="m1", player_a="A", player_b="B", best_of=3)
    return TennisState(**{**defaults, **kwargs})


def _market(mid: float = 55.0, spread: float = 2.0, volume: int = 300) -> MarketState:
    return MarketState(
        market_id="MKT-001",
        game_id="m1",
        title="test",
        yes_ask=mid + spread / 2,
        yes_bid=mid - spread / 2,
        volume=volume,
        open_interest=100,
    )


def _classify(state_kwargs: dict, mid: float = 55.0, spread: float = 2.0, volume: int = 300) -> RegimeResult:
    state = _state(**state_kwargs)
    market = _market(mid=mid, spread=spread, volume=volume)
    features = TennisFeatureExtractor().extract(state, market)
    return TennisRegimeClassifier().classify(features, state)


class TestRetirementRegime:
    def test_retired_is_retirement_risk(self):
        r = _classify({"retired": True})
        assert r.regime == TennisRegime.RETIREMENT_RISK

    def test_retired_confidence_is_1(self):
        r = _classify({"retired": True})
        assert r.confidence == 1.0


class TestSuspendedRegime:
    def test_suspended_is_suspended_or_delayed(self):
        r = _classify({"suspended": True})
        assert r.regime == TennisRegime.SUSPENDED_OR_DELAYED

    def test_suspended_confidence_is_1(self):
        r = _classify({"suspended": True})
        assert r.confidence == 1.0


class TestLowLiquidityRegime:
    def test_wide_spread_is_low_liq(self):
        r = _classify({}, spread=10.0, volume=300)
        assert r.regime == TennisRegime.LOW_LIQUIDITY

    def test_low_volume_is_low_liq(self):
        # liquidity_score = (spread_score + vol_score) / 2
        # spread_score = 1 - 2/20 = 0.9, vol_score = 1/500 ≈ 0.002 → score ≈ 0.45 (not low)
        # Need a wide spread AND low volume to fall below LOW_LIQ_SCORE=0.25
        r = _classify({}, spread=14.0, volume=1)
        assert r.regime == TennisRegime.LOW_LIQUIDITY

    def test_good_liquidity_not_low_liq(self):
        r = _classify({}, spread=2.0, volume=400)
        assert r.regime != TennisRegime.LOW_LIQUIDITY


class TestMatchPointRegime:
    def test_match_point_detected(self):
        r = _classify(
            {
                "best_of": 3, "sets_a": 1, "sets_b": 0,
                "server": Server.A, "games_a": 5, "games_b": 3,
                "points_a": 3, "points_b": 2,
            },
            volume=400,
        )
        assert r.regime == TennisRegime.MATCH_POINT_PRESSURE


class TestTiebreakRegime:
    def test_tiebreak_is_tiebreak_chaos(self):
        r = _classify(
            {"tiebreak": True, "games_a": 6, "games_b": 6,
             "points_a": 3, "points_b": 3},
            volume=400,
        )
        assert r.regime == TennisRegime.TIEBREAK_CHAOS

    def test_tiebreak_confidence_at_least_0_65(self):
        r = _classify(
            {"tiebreak": True, "games_a": 6, "games_b": 6,
             "points_a": 1, "points_b": 0},
            volume=400,
        )
        assert r.confidence >= 0.65


class TestBreakPointRegime:
    def test_break_point_detected(self):
        r = _classify(
            {"server": Server.A, "points_a": 0, "points_b": 3},
            volume=400,
        )
        assert r.regime == TennisRegime.BREAK_POINT_PRESSURE

    def test_break_point_confidence_increases_with_count(self):
        one_bp = _classify(
            {"server": Server.A, "points_a": 2, "points_b": 3}, volume=400
        )
        three_bp = _classify(
            {"server": Server.A, "points_a": 0, "points_b": 3}, volume=400
        )
        assert three_bp.confidence >= one_bp.confidence


class TestPostBreakRegime:
    def test_high_overreaction_gives_post_break(self):
        # mid=80 but A has no set/game lead → implied=0.80, rough_fair≈0.50 → big gap
        r = _classify({"sets_a": 0, "sets_b": 0}, mid=80.0, volume=400)
        assert r.regime == TennisRegime.POST_BREAK_OVERREACTION


class TestCalmRegime:
    def test_calm_when_no_elevated_pressure(self):
        # sets_a=1 → rough_fair ≈ 0.70; use mid=70 so overreaction ≈ 0 → calm
        r = _classify({"sets_a": 1, "sets_b": 0}, mid=70.0, spread=2.0, volume=400)
        assert r.regime in (TennisRegime.CALM_HOLD_PATTERN, TennisRegime.SERVER_PRESSURE)


class TestRegimeResult:
    def test_result_has_reasons(self):
        r = _classify({}, volume=400)
        assert isinstance(r.reasons, list)

    def test_result_confidence_in_range(self):
        r = _classify({}, volume=400)
        assert 0.0 <= r.confidence <= 1.0
