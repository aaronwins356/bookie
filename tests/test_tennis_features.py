from __future__ import annotations

import pytest

from src.models import MarketState
from src.sports.tennis.features import TennisFeatureExtractor, TennisFeatureSet
from src.sports.tennis.state import Server, Surface, TennisState


def _market(mid: float = 55.0, spread: float = 2.0, volume: int = 200) -> MarketState:
    return MarketState(
        market_id="MKT-001",
        game_id="m1",
        title="A vs B match winner",
        yes_ask=mid + spread / 2,
        yes_bid=mid - spread / 2,
        volume=volume,
        open_interest=volume // 2,
    )


def _state(**kwargs) -> TennisState:
    defaults = dict(match_id="m1", player_a="A", player_b="B", best_of=3)
    return TennisState(**{**defaults, **kwargs})


def _extract(**kwargs) -> TennisFeatureSet:
    state = _state(**{k: v for k, v in kwargs.items() if k not in ("mid", "spread", "volume")})
    market_kwargs = {k: v for k, v in kwargs.items() if k in ("mid", "spread", "volume")}
    market = _market(**market_kwargs)
    return TennisFeatureExtractor().extract(state, market)


class TestBasicExtraction:
    def test_market_id_passes_through(self):
        f = _extract()
        assert f.market_id == "MKT-001"

    def test_match_id_passes_through(self):
        f = _extract()
        assert f.match_id == "m1"

    def test_set_lead(self):
        f = _extract(sets_a=1, sets_b=0)
        assert f.set_lead == 1

    def test_game_lead(self):
        f = _extract(games_a=4, games_b=2)
        assert f.game_lead == 2

    def test_point_lead(self):
        f = _extract(points_a=2, points_b=1)
        assert f.point_lead == 1


class TestBreakPointFeatures:
    def test_break_point_true(self):
        f = _extract(server=Server.A, points_a=0, points_b=3)
        assert f.break_point is True

    def test_break_point_false(self):
        f = _extract(server=Server.A, points_a=3, points_b=0)
        assert f.break_point is False

    def test_break_point_count_three(self):
        f = _extract(server=Server.A, points_a=0, points_b=3)
        assert f.break_points_count == 3

    def test_break_point_count_one(self):
        f = _extract(server=Server.A, points_a=2, points_b=3)
        assert f.break_points_count == 1

    def test_break_point_count_zero_when_no_bp(self):
        f = _extract(server=Server.A, points_a=1, points_b=0)
        assert f.break_points_count == 0


class TestPressureFlags:
    def test_tiebreak_flag(self):
        f = _extract(tiebreak=True, games_a=6, games_b=6)
        assert f.tiebreak is True

    def test_deuce_flag(self):
        f = _extract(server=Server.A, points_a=3, points_b=3)
        assert f.deuce is True

    def test_advantage_player_a(self):
        f = _extract(points_a=4, points_b=3)
        assert f.advantage_player == "A"

    def test_match_point(self):
        f = _extract(
            best_of=3, sets_a=1, sets_b=0,
            server=Server.A, games_a=5, games_b=3,
            points_a=3, points_b=2,
        )
        assert f.match_point is True


class TestMarketFeatures:
    def test_market_mid(self):
        f = _extract(mid=60.0, spread=2.0)
        assert f.market_mid == pytest.approx(60.0)

    def test_market_spread(self):
        f = _extract(mid=55.0, spread=4.0)
        assert f.market_spread == pytest.approx(4.0)

    def test_implied_probability(self):
        f = _extract(mid=70.0)
        assert f.implied_probability == pytest.approx(0.70)

    def test_liquidity_score_range(self):
        f = _extract(mid=50.0, spread=2.0, volume=500)
        assert 0.0 <= f.liquidity_score <= 1.0

    def test_low_liquidity(self):
        f = _extract(mid=50.0, spread=18.0, volume=10)
        assert f.liquidity_score < 0.3


class TestMomentum:
    def test_positive_momentum_set_lead(self):
        f = _extract(sets_a=2, sets_b=0)
        assert f.momentum_proxy > 0

    def test_negative_momentum(self):
        f = _extract(sets_a=0, sets_b=2)
        assert f.momentum_proxy < 0

    def test_momentum_clamped(self):
        f = _extract(sets_a=2, sets_b=0, games_a=6, games_b=0)
        assert -1.0 <= f.momentum_proxy <= 1.0


class TestSurfaceBonus:
    def test_grass_higher_than_clay(self):
        fe = TennisFeatureExtractor()
        market = _market()
        grass = fe.extract(_state(surface=Surface.GRASS), market)
        clay = fe.extract(_state(surface=Surface.CLAY), market)
        assert grass.surface_serve_bonus > clay.surface_serve_bonus

    def test_unknown_surface_has_default(self):
        f = _extract(surface=Surface.UNKNOWN)
        assert f.surface_serve_bonus == pytest.approx(0.06)


class TestOverreactionScore:
    def test_overreaction_zero_near_fair(self):
        # mid at ~50, sets even — rough fair ≈ 0.50, so |0.50 - 0.50| = 0
        f = _extract(mid=50.0, sets_a=0, sets_b=0)
        assert f.market_overreaction_score == pytest.approx(0.0, abs=0.1)

    def test_overreaction_high_when_far(self):
        # A leads 2-0 sets, rough fair ≈ 0.80, market at 45 → |0.45-0.80|=0.35
        f = _extract(mid=45.0, sets_a=2, sets_b=0)
        assert f.market_overreaction_score > 0.5
