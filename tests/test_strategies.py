import pytest
from src.engine.features import FeatureSet
from src.models import SignalDirection, GamePhase
from src.strategies import (
    FavoriteGrinder, EndgameBonding, MomentumStrategy,
    OverpricedFade, LiquidityVacuum,
)


def make_features(
    market_id: str = "m-001",
    score_diff: int = 7,
    time_pressure: float = 0.5,
    mid_price: float = 55.0,
    spread: float = 4.0,
    volume: int = 300,
) -> FeatureSet:
    return FeatureSet(
        market_id=market_id,
        game_id="g-001",
        score_diff=score_diff,
        total_score=20,
        clock_seconds=600,
        phase=GamePhase.SECOND_HALF.value,
        time_pressure=time_pressure,
        mid_price=mid_price,
        spread=spread,
        volume=volume,
        spread_pct=spread / mid_price,
        implied_prob=mid_price / 100.0,
    )


class TestFavoriteGrinder:
    def test_buy_when_underpriced(self):
        strat = FavoriteGrinder(min_edge=3.0)
        # fair value ~65+ for diff=7 at 50% time, market at 55 → should BUY
        sig = strat.evaluate(make_features(score_diff=7, mid_price=52.0, time_pressure=0.5))
        assert sig.direction == SignalDirection.BUY

    def test_hold_when_close(self):
        strat = FavoriteGrinder()
        sig = strat.evaluate(make_features(score_diff=1, mid_price=52.0))
        assert sig.direction == SignalDirection.HOLD


class TestEndgameBonding:
    def test_buy_big_lead_endgame(self):
        strat = EndgameBonding(time_threshold=0.85, lead_threshold=10)
        sig = strat.evaluate(make_features(score_diff=14, time_pressure=0.92, mid_price=60.0))
        assert sig.direction == SignalDirection.BUY

    def test_hold_early_game(self):
        strat = EndgameBonding()
        sig = strat.evaluate(make_features(score_diff=14, time_pressure=0.3))
        assert sig.direction == SignalDirection.HOLD


class TestMomentumStrategy:
    def test_no_signal_first_tick(self):
        strat = MomentumStrategy()
        sig = strat.evaluate(make_features())
        assert sig.direction == SignalDirection.HOLD

    def test_buy_on_upward_move(self):
        strat = MomentumStrategy(momentum_threshold=5.0)
        strat.evaluate(make_features(mid_price=50.0))  # seed
        sig = strat.evaluate(make_features(mid_price=58.0))
        assert sig.direction == SignalDirection.BUY

    def test_sell_on_downward_move(self):
        strat = MomentumStrategy(momentum_threshold=5.0)
        strat.evaluate(make_features(mid_price=65.0))
        sig = strat.evaluate(make_features(mid_price=55.0))
        assert sig.direction == SignalDirection.SELL


class TestOverpricedFade:
    def test_sell_when_overpriced(self):
        strat = OverpricedFade(fade_threshold=8.0)
        # score_diff=0, time_pressure=0.5 → fair≈50; mid=62 → edge≈-12 → SELL
        sig = strat.evaluate(make_features(score_diff=0, mid_price=62.0, time_pressure=0.5))
        assert sig.direction == SignalDirection.SELL

    def test_hold_when_fair(self):
        strat = OverpricedFade()
        sig = strat.evaluate(make_features(score_diff=0, mid_price=50.0))
        assert sig.direction == SignalDirection.HOLD


class TestLiquidityVacuum:
    def test_sell_extreme_high_illiquid(self):
        strat = LiquidityVacuum(min_spread=6.0, max_volume=200, extreme_threshold=20.0)
        sig = strat.evaluate(make_features(mid_price=85.0, spread=8.0, volume=100))
        assert sig.direction == SignalDirection.SELL

    def test_hold_liquid_market(self):
        strat = LiquidityVacuum()
        sig = strat.evaluate(make_features(mid_price=85.0, spread=2.0, volume=1000))
        assert sig.direction == SignalDirection.HOLD
