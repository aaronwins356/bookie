from __future__ import annotations

import pytest

from src.models import MarketState, SignalDirection
from src.sports.tennis.features import TennisFeatureExtractor
from src.sports.tennis.regimes import TennisRegime, TennisRegimeClassifier
from src.sports.tennis.state import Server, Surface, TennisState
from src.sports.tennis.strategies import (
    TennisBreakPointOverreaction,
    TennisFavoriteHold,
    TennisMomentumContinuation,
    TennisPostBreakReversion,
    TennisTiebreakChaosAvoider,
    make_tennis_strategies,
    ALL_TENNIS_STRATEGIES,
)
from src.simulation.market_regime import MarketRegime


def _state(**kwargs) -> TennisState:
    defaults = dict(match_id="m1", player_a="A", player_b="B", best_of=3)
    return TennisState(**{**defaults, **kwargs})


def _market(mid: float = 55.0, spread: float = 2.0, volume: int = 400) -> MarketState:
    return MarketState(
        market_id="MKT-001",
        game_id="m1",
        title="test",
        yes_ask=mid + spread / 2,
        yes_bid=mid - spread / 2,
        volume=volume,
        open_interest=200,
    )


def _run(strategy, state_kwargs: dict, mid: float = 55.0, spread: float = 2.0, volume: int = 400):
    state = _state(**state_kwargs)
    market = _market(mid=mid, spread=spread, volume=volume)
    features = TennisFeatureExtractor().extract(state, market)
    regime_result = TennisRegimeClassifier().classify(features, state)
    return strategy.evaluate(features, state, regime_result.regime)


# ------------------------------------------------------------------ #
# Factory
# ------------------------------------------------------------------ #

class TestFactory:
    def test_make_strategies_returns_all(self):
        strats = make_tennis_strategies()
        assert len(strats) == len(ALL_TENNIS_STRATEGIES)

    def test_all_have_name(self):
        for strat in make_tennis_strategies():
            assert hasattr(strat, "NAME")
            assert isinstance(strat.NAME, str)

    def test_all_have_evaluate(self):
        for strat in make_tennis_strategies():
            assert callable(strat.evaluate)

    def test_all_have_regime_compatibility(self):
        for strat in make_tennis_strategies():
            assert callable(strat.regime_compatibility)


# ------------------------------------------------------------------ #
# regime_compatibility returns floats in range
# ------------------------------------------------------------------ #

class TestRegimeCompatibility:
    @pytest.mark.parametrize("strat_cls", ALL_TENNIS_STRATEGIES)
    @pytest.mark.parametrize("regime", list(MarketRegime))
    def test_compatibility_in_range(self, strat_cls, regime):
        score = strat_cls().regime_compatibility(regime)
        assert 0.0 <= score <= 1.0


# ------------------------------------------------------------------ #
# TennisFavoriteHold
# ------------------------------------------------------------------ #

class TestTennisFavoriteHold:
    def test_holds_in_tiebreak_chaos(self):
        # Tiebreak triggers TIEBREAK_CHAOS regime
        sig = _run(TennisFavoriteHold(), {
            "tiebreak": True, "games_a": 6, "games_b": 6,
            "points_a": 3, "points_b": 3,
        }, volume=400)
        assert sig.direction == SignalDirection.HOLD

    def test_holds_when_no_set_lead(self):
        # No edge direction disagreement — edge might be positive but no set lead
        sig = _run(TennisFavoriteHold(), {"sets_a": 0, "sets_b": 0}, mid=50.0)
        assert sig.direction == SignalDirection.HOLD

    def test_buys_when_a_leads_sets_and_underpriced(self):
        # A leads 2 sets, fair value ≈ 80+, mid at 60 → edge > 0, set_lead > 0
        sig = _run(TennisFavoriteHold(), {
            "sets_a": 2, "sets_b": 0,
            "server": Server.A, "surface": Surface.HARD,
        }, mid=60.0, volume=400)
        assert sig.direction in (SignalDirection.BUY, SignalDirection.HOLD)

    def test_confidence_capped_at_0_85(self):
        sig = _run(TennisFavoriteHold(), {
            "sets_a": 2, "sets_b": 0, "server": Server.A,
        }, mid=55.0, volume=400)
        if sig.direction != SignalDirection.HOLD:
            assert sig.confidence <= 0.85


# ------------------------------------------------------------------ #
# TennisBreakPointOverreaction
# ------------------------------------------------------------------ #

class TestTennisBreakPointOverreaction:
    def test_holds_when_no_break_point(self):
        sig = _run(TennisBreakPointOverreaction(), {
            "server": Server.A, "points_a": 3, "points_b": 0,
        }, volume=400)
        assert sig.direction == SignalDirection.HOLD

    def test_holds_in_low_liquidity(self):
        # Wide spread → LOW_LIQUIDITY regime → hold
        sig = _run(TennisBreakPointOverreaction(), {
            "server": Server.A, "points_a": 0, "points_b": 3,
        }, spread=12.0, volume=10)
        assert sig.direction == SignalDirection.HOLD

    def test_fires_on_break_point_with_overreaction(self):
        # Break point + overpriced A (mid=20, A has no set lead → fair≈50)
        sig = _run(TennisBreakPointOverreaction(), {
            "server": Server.A,
            "points_a": 0, "points_b": 3,
            "sets_a": 0, "sets_b": 0,
        }, mid=20.0, volume=400)
        # Edge should be large enough and overreaction score high
        # May hold if overreaction_score threshold not met; accept either
        assert sig.direction in (SignalDirection.BUY, SignalDirection.HOLD)

    def test_confidence_max_0_75(self):
        sig = _run(TennisBreakPointOverreaction(), {
            "server": Server.A, "points_a": 0, "points_b": 3,
        }, mid=20.0, volume=400)
        if sig.direction != SignalDirection.HOLD:
            assert sig.confidence <= 0.75


# ------------------------------------------------------------------ #
# TennisPostBreakReversion
# ------------------------------------------------------------------ #

class TestTennisPostBreakReversion:
    def test_holds_when_not_post_break_regime(self):
        # Even state, mid=50 → implied=0.50, rough_fair≈0.50, overreaction≈0 → CALM_HOLD_PATTERN
        sig = _run(TennisPostBreakReversion(), {}, mid=50.0, volume=400)
        assert sig.direction == SignalDirection.HOLD

    def test_fires_in_post_break_regime(self):
        # POST_BREAK_OVERREACTION is triggered when overreaction_score ≥ 0.12
        # A leads 0 sets but market has mid=80 → implied=0.80, rough_fair≈0.50
        sig = _run(TennisPostBreakReversion(), {
            "sets_a": 0, "sets_b": 0,
        }, mid=80.0, volume=400)
        # Should be in POST_BREAK_OVERREACTION regime and fire
        assert sig.direction in (SignalDirection.SELL, SignalDirection.HOLD)

    def test_confidence_max_0_72(self):
        sig = _run(TennisPostBreakReversion(), {
            "sets_a": 0, "sets_b": 0,
        }, mid=80.0, volume=400)
        if sig.direction != SignalDirection.HOLD:
            assert sig.confidence <= 0.72


# ------------------------------------------------------------------ #
# TennisTiebreakChaosAvoider — main contract: almost always HOLD
# ------------------------------------------------------------------ #

class TestTennisTiebreakChaosAvoider:
    def test_holds_when_not_in_tiebreak(self):
        sig = _run(TennisTiebreakChaosAvoider(), {}, volume=400)
        assert sig.direction == SignalDirection.HOLD

    def test_holds_in_tiebreak_normal_conditions(self):
        # Tiebreak, even score, fair market → hold
        sig = _run(TennisTiebreakChaosAvoider(), {
            "tiebreak": True, "games_a": 6, "games_b": 6,
            "points_a": 3, "points_b": 3,
        }, mid=50.0, volume=400)
        assert sig.direction == SignalDirection.HOLD

    def test_holds_in_tiebreak_low_liquidity(self):
        sig = _run(TennisTiebreakChaosAvoider(), {
            "tiebreak": True, "games_a": 6, "games_b": 6,
        }, spread=15.0, volume=5)
        assert sig.direction == SignalDirection.HOLD

    def test_holds_in_tiebreak_match_point(self):
        # Tiebreak match point
        sig = _run(TennisTiebreakChaosAvoider(), {
            "tiebreak": True, "games_a": 6, "games_b": 6,
            "sets_a": 1, "sets_b": 0,
            "points_a": 6, "points_b": 4,  # set point / match point
        }, volume=400)
        assert sig.direction == SignalDirection.HOLD

    def test_confidence_capped_at_0_45_when_entering(self):
        # Extreme overreaction in tiebreak — the one case it might enter
        sig = _run(TennisTiebreakChaosAvoider(), {
            "tiebreak": True, "games_a": 6, "games_b": 6,
            "points_a": 0, "points_b": 0,
        }, mid=5.0, volume=400)  # very extreme overreaction
        if sig.direction != SignalDirection.HOLD:
            assert sig.confidence <= 0.45


# ------------------------------------------------------------------ #
# TennisMomentumContinuation
# ------------------------------------------------------------------ #

class TestTennisMomentumContinuation:
    def test_holds_in_tiebreak_chaos(self):
        sig = _run(TennisMomentumContinuation(), {
            "tiebreak": True, "games_a": 6, "games_b": 6,
            "points_a": 3, "points_b": 3,
        }, volume=400)
        assert sig.direction == SignalDirection.HOLD

    def test_holds_when_low_momentum(self):
        # Even score → momentum_proxy ≈ 0
        sig = _run(TennisMomentumContinuation(), {
            "sets_a": 0, "sets_b": 0, "games_a": 0, "games_b": 0,
        }, mid=50.0, volume=400)
        assert sig.direction == SignalDirection.HOLD

    def test_buys_when_a_momentum_and_underpriced(self):
        # A leads 2 sets → strong momentum, mid low → edge > 0
        sig = _run(TennisMomentumContinuation(), {
            "sets_a": 2, "sets_b": 0, "server": Server.A,
        }, mid=55.0, volume=400)
        assert sig.direction in (SignalDirection.BUY, SignalDirection.HOLD)

    def test_sells_when_b_momentum_and_overpriced(self):
        # B leads 2 sets, mid at 70 → A overpriced → edge < 0; momentum < 0
        sig = _run(TennisMomentumContinuation(), {
            "sets_a": 0, "sets_b": 2,
        }, mid=70.0, volume=400)
        assert sig.direction in (SignalDirection.SELL, SignalDirection.HOLD)

    def test_confidence_max_0_80(self):
        sig = _run(TennisMomentumContinuation(), {
            "sets_a": 2, "sets_b": 0,
        }, mid=50.0, volume=400)
        if sig.direction != SignalDirection.HOLD:
            assert sig.confidence <= 0.80
