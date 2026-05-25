from __future__ import annotations

"""
Tennis-specific trading strategies.

All strategies:
- Take TennisFeatureSet + TennisRegime as input.
- Output Signal objects (same type as generic strategies).
- Expose regime_compatibility(MarketRegime) for router integration.
- Never touch execution or risk.

Design philosophy:
- The edge in tennis markets comes from market overreaction to score events
  and mispricing of server/returner dynamics.
- Strategies that require game state (break point, set lead, tiebreak) only
  fire when that state is known. If state is LIVE_UNKNOWN, they hold.
- TennisTiebreakChaosAvoider is intentionally conservative — it returns HOLD
  in most tiebreak situations because fills are hard and outcomes are random.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from src.models import Regime, Signal, SignalDirection
from src.simulation.market_regime import MarketRegime
from src.sports.tennis.fair_value import TennisFairValueModel, TennisFairValueResult
from src.sports.tennis.features import TennisFeatureSet
from src.sports.tennis.regimes import TennisRegime
from src.sports.tennis.state import Server, TennisState


# ------------------------------------------------------------------ #
# Shared helpers
# ------------------------------------------------------------------ #

def _make_signal(
    strategy_name: str,
    features: TennisFeatureSet,
    fair: TennisFairValueResult,
    direction: SignalDirection,
    confidence: float,
    regime_label: Regime,
    notes: str,
) -> Signal:
    edge = fair.edge_cents(features.market_mid)
    return Signal(
        strategy_name=strategy_name,
        market_id=features.market_id,
        direction=direction,
        confidence=round(confidence, 4),
        fair_value=fair.fair_value_cents,
        current_price=features.market_mid,
        edge=round(edge, 2),
        regime=regime_label,
        notes=notes,
    )


def _hold(strategy_name: str, features: TennisFeatureSet, reason: str) -> Signal:
    return Signal(
        strategy_name=strategy_name,
        market_id=features.market_id,
        direction=SignalDirection.HOLD,
        confidence=0.0,
        fair_value=features.market_mid,
        current_price=features.market_mid,
        edge=0.0,
        regime=Regime.UNKNOWN,
        notes=reason,
    )


# ------------------------------------------------------------------ #
# Strategy 1 — TennisFavoriteHold
# ------------------------------------------------------------------ #

class TennisFavoriteHold:
    """
    Back the set-leader when the market underestimates their win probability.

    Rationale: Markets often underestimate the difficulty of coming back
    from a set down, especially on fast surfaces or in best-of-5 formats.

    When to fire: Set lead > 0, edge ≥ min_edge, not in chaotic situations.
    When to hold: Tiebreak, match point, retirement risk, low liquidity.
    """

    NAME = "tennis_favorite_hold"
    MIN_EDGE = 3.0
    MIN_CONFIDENCE = 0.50

    def __init__(self) -> None:
        self._fv = TennisFairValueModel()

    def regime_compatibility(self, regime: MarketRegime) -> float:
        good = {MarketRegime.CALM, MarketRegime.MEAN_REVERSION, MarketRegime.DEAD_MARKET}
        bad = {MarketRegime.LIQUIDITY_COLLAPSE, MarketRegime.ENDGAME_CHAOS, MarketRegime.PANIC_BUYING}
        if regime in good:
            return 1.0
        if regime in bad:
            return 0.1
        return 0.5

    def evaluate(
        self,
        features: TennisFeatureSet,
        state: TennisState,
        tennis_regime: TennisRegime,
    ) -> Signal:
        # Avoid chaotic / dangerous regimes
        if tennis_regime in (
            TennisRegime.TIEBREAK_CHAOS,
            TennisRegime.MATCH_POINT_PRESSURE,
            TennisRegime.RETIREMENT_RISK,
            TennisRegime.LOW_LIQUIDITY,
            TennisRegime.SUSPENDED_OR_DELAYED,
        ):
            return _hold(self.NAME, features, f"hold: regime={tennis_regime.value}")

        fair = self._fv.estimate(features, state)
        edge = fair.edge_cents(features.market_mid)

        if abs(edge) < self.MIN_EDGE:
            return _hold(self.NAME, features, f"edge={edge:.1f}c below min={self.MIN_EDGE}")

        if fair.confidence < self.MIN_CONFIDENCE:
            return _hold(self.NAME, features, f"confidence={fair.confidence:.2f} too low")

        # A leads in sets → A underpriced → BUY
        if edge > 0 and features.set_lead > 0:
            direction = SignalDirection.BUY
            conf = min(0.85, fair.confidence + features.set_lead * 0.05)
        elif edge < 0 and features.set_lead < 0:
            direction = SignalDirection.SELL
            conf = min(0.85, fair.confidence + abs(features.set_lead) * 0.05)
        else:
            return _hold(self.NAME, features, "set_lead disagrees with edge direction")

        return _make_signal(
            self.NAME, features, fair, direction, conf,
            Regime.TRENDING,
            f"set_lead={features.set_lead} edge={edge:.1f}c regime={tennis_regime.value}",
        )


# ------------------------------------------------------------------ #
# Strategy 2 — TennisBreakPointOverreaction
# ------------------------------------------------------------------ #

class TennisBreakPointOverreaction:
    """
    At break point, markets often overreact — implied probability shifts
    more than the ~35-40% chance of a break warrants.

    When the market has already moved to imply break > fair value, fade
    the move (the server holds more often than markets price in panics).

    When to fire: break_point=True, overreaction_score ≥ threshold.
    """

    NAME = "tennis_break_point_overreaction"
    OVERREACTION_THRESHOLD = 0.08
    MIN_EDGE = 2.5

    def __init__(self) -> None:
        self._fv = TennisFairValueModel()

    def regime_compatibility(self, regime: MarketRegime) -> float:
        good = {MarketRegime.MEAN_REVERSION, MarketRegime.PANIC_SELLING, MarketRegime.PANIC_BUYING}
        bad = {MarketRegime.LIQUIDITY_COLLAPSE, MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN}
        if regime in good:
            return 1.0
        if regime in bad:
            return 0.2
        return 0.5

    def evaluate(
        self,
        features: TennisFeatureSet,
        state: TennisState,
        tennis_regime: TennisRegime,
    ) -> Signal:
        if not features.break_point:
            return _hold(self.NAME, features, "no break point")

        if tennis_regime in (TennisRegime.LOW_LIQUIDITY, TennisRegime.SUSPENDED_OR_DELAYED):
            return _hold(self.NAME, features, f"blocked: {tennis_regime.value}")

        if features.market_overreaction_score < self.OVERREACTION_THRESHOLD:
            return _hold(
                self.NAME, features,
                f"overreaction_score={features.market_overreaction_score:.2f} below threshold"
            )

        fair = self._fv.estimate(features, state)
        edge = fair.edge_cents(features.market_mid)

        if abs(edge) < self.MIN_EDGE:
            return _hold(self.NAME, features, f"edge={edge:.1f}c too small")

        # If server is A and market has crashed A's price too far, buy back
        if state.server == Server.A and edge > 0:
            direction = SignalDirection.BUY
        elif state.server == Server.B and edge < 0:
            direction = SignalDirection.SELL
        else:
            direction = SignalDirection.BUY if edge > 0 else SignalDirection.SELL

        conf = min(0.75, 0.45 + features.market_overreaction_score * 2.0)

        return _make_signal(
            self.NAME, features, fair, direction, conf,
            Regime.MEAN_REVERTING,
            f"break_pt overreaction={features.market_overreaction_score:.2f} "
            f"bp_count={features.break_points_count} edge={edge:.1f}c",
        )


# ------------------------------------------------------------------ #
# Strategy 3 — TennisPostBreakReversion
# ------------------------------------------------------------------ #

class TennisPostBreakReversion:
    """
    After a break of serve, the market typically over-extends the breaker's
    probability beyond what the new game state warrants.

    This strategy fades the post-break spike by identifying market
    overreaction (overreaction_score high) in the POST_BREAK_OVERREACTION regime.

    When to fire: POST_BREAK_OVERREACTION regime, meaningful edge.
    """

    NAME = "tennis_post_break_reversion"
    MIN_EDGE = 2.0
    MIN_OVERREACTION = 0.08

    def __init__(self) -> None:
        self._fv = TennisFairValueModel()

    def regime_compatibility(self, regime: MarketRegime) -> float:
        good = {MarketRegime.MEAN_REVERSION, MarketRegime.FAVORITE_EUPHORIA}
        bad = {MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN, MarketRegime.PANIC_BUYING}
        if regime in good:
            return 1.0
        if regime in bad:
            return 0.15
        return 0.55

    def evaluate(
        self,
        features: TennisFeatureSet,
        state: TennisState,
        tennis_regime: TennisRegime,
    ) -> Signal:
        if tennis_regime != TennisRegime.POST_BREAK_OVERREACTION:
            return _hold(self.NAME, features, f"regime={tennis_regime.value}, need POST_BREAK")

        if features.market_overreaction_score < self.MIN_OVERREACTION:
            return _hold(
                self.NAME, features,
                f"overreaction={features.market_overreaction_score:.2f} too low"
            )

        if tennis_regime in (TennisRegime.LOW_LIQUIDITY, TennisRegime.SUSPENDED_OR_DELAYED):
            return _hold(self.NAME, features, f"blocked: {tennis_regime.value}")

        fair = self._fv.estimate(features, state)
        edge = fair.edge_cents(features.market_mid)

        if abs(edge) < self.MIN_EDGE:
            return _hold(self.NAME, features, f"edge={edge:.1f}c too small")

        direction = SignalDirection.BUY if edge > 0 else SignalDirection.SELL
        conf = min(0.72, 0.40 + features.market_overreaction_score * 1.8)

        return _make_signal(
            self.NAME, features, fair, direction, conf,
            Regime.MEAN_REVERTING,
            f"post_break reversion overreaction={features.market_overreaction_score:.2f} "
            f"edge={edge:.1f}c game_lead={features.game_lead:+d}",
        )


# ------------------------------------------------------------------ #
# Strategy 4 — TennisTiebreakChaosAvoider
# ------------------------------------------------------------------ #

class TennisTiebreakChaosAvoider:
    """
    Tiebreaks are high-pressure, low-predictability situations. Markets
    thin out, spreads widen, and random mini-runs determine outcomes.

    This strategy almost always returns HOLD during tiebreaks. It only
    enters if there is a very strong market overreaction (the market has
    moved far from fair value) AND liquidity is acceptable.

    The primary contribution is NOT trading — avoiding the worst fills
    during chaotic tiebreaks. Absence of bad trades is positive EV.
    """

    NAME = "tennis_tiebreak_chaos_avoider"
    VERY_HIGH_OVERREACTION = 0.20  # only trade if extremely mispriced
    MIN_LIQUIDITY = 0.50

    def __init__(self) -> None:
        self._fv = TennisFairValueModel()

    def regime_compatibility(self, regime: MarketRegime) -> float:
        # Conservative everywhere; never favors high-activity regimes
        good = {MarketRegime.CALM, MarketRegime.DEAD_MARKET}
        bad = {
            MarketRegime.ENDGAME_CHAOS, MarketRegime.PANIC_BUYING, MarketRegime.PANIC_SELLING,
            MarketRegime.LIQUIDITY_COLLAPSE,
        }
        if regime in good:
            return 1.0
        if regime in bad:
            return 0.05
        return 0.3

    def evaluate(
        self,
        features: TennisFeatureSet,
        state: TennisState,
        tennis_regime: TennisRegime,
    ) -> Signal:
        # If not in a tiebreak, this strategy is idle
        if not features.tiebreak:
            return _hold(self.NAME, features, "not in tiebreak; strategy idle")

        # Low liquidity during tiebreak = always hold
        if features.liquidity_score < self.MIN_LIQUIDITY:
            return _hold(
                self.NAME, features,
                f"tiebreak + low_liq={features.liquidity_score:.2f}; hold"
            )

        # Match point during tiebreak = hold (too late to trade safely)
        if features.match_point:
            return _hold(self.NAME, features, "tiebreak match_point; hold")

        # Only enter if extreme overreaction
        if features.market_overreaction_score < self.VERY_HIGH_OVERREACTION:
            return _hold(
                self.NAME, features,
                f"tiebreak chaos; overreaction={features.market_overreaction_score:.2f} "
                f"< {self.VERY_HIGH_OVERREACTION}; hold"
            )

        # Extreme mismatch case — cautious entry
        fair = self._fv.estimate(features, state)
        edge = fair.edge_cents(features.market_mid)

        if abs(edge) < 4.0:
            return _hold(self.NAME, features, f"tiebreak edge={edge:.1f}c too small")

        direction = SignalDirection.BUY if edge > 0 else SignalDirection.SELL
        # Very low confidence even when entering
        conf = min(0.45, 0.25 + features.market_overreaction_score)

        return _make_signal(
            self.NAME, features, fair, direction, conf,
            Regime.VOLATILE,
            f"tiebreak exception: extreme overreaction={features.market_overreaction_score:.2f} "
            f"pts {state.points_a}-{state.points_b} edge={edge:.1f}c",
        )


# ------------------------------------------------------------------ #
# Strategy 5 — TennisMomentumContinuation
# ------------------------------------------------------------------ #

class TennisMomentumContinuation:
    """
    When one player has strong momentum (consecutive games won, set lead)
    the market sometimes lags the repricing — especially on fast surfaces
    and after dominant service games.

    Follows the momentum by buying the leading player when momentum_proxy
    is strong and market mid hasn't fully adjusted.

    When to hold: low momentum, tiebreak, match point (already priced in).
    """

    NAME = "tennis_momentum_continuation"
    MIN_MOMENTUM = 0.35
    MIN_EDGE = 2.5

    def __init__(self) -> None:
        self._fv = TennisFairValueModel()

    def regime_compatibility(self, regime: MarketRegime) -> float:
        good = {
            MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN,
            MarketRegime.CALM, MarketRegime.FAVORITE_EUPHORIA,
        }
        bad = {MarketRegime.MEAN_REVERSION, MarketRegime.DEAD_MARKET, MarketRegime.LIQUIDITY_COLLAPSE}
        if regime in good:
            return 1.0
        if regime in bad:
            return 0.15
        return 0.5

    def evaluate(
        self,
        features: TennisFeatureSet,
        state: TennisState,
        tennis_regime: TennisRegime,
    ) -> Signal:
        # Avoid chaotic regimes
        if tennis_regime in (
            TennisRegime.TIEBREAK_CHAOS,
            TennisRegime.MATCH_POINT_PRESSURE,
            TennisRegime.LOW_LIQUIDITY,
            TennisRegime.SUSPENDED_OR_DELAYED,
            TennisRegime.RETIREMENT_RISK,
        ):
            return _hold(self.NAME, features, f"blocked: {tennis_regime.value}")

        if abs(features.momentum_proxy) < self.MIN_MOMENTUM:
            return _hold(
                self.NAME, features,
                f"momentum_proxy={features.momentum_proxy:.2f} below min={self.MIN_MOMENTUM}"
            )

        fair = self._fv.estimate(features, state)
        edge = fair.edge_cents(features.market_mid)

        if abs(edge) < self.MIN_EDGE:
            return _hold(self.NAME, features, f"edge={edge:.1f}c too small")

        # Momentum direction must align with edge direction
        if features.momentum_proxy > 0 and edge > 0:
            direction = SignalDirection.BUY
        elif features.momentum_proxy < 0 and edge < 0:
            direction = SignalDirection.SELL
        else:
            return _hold(
                self.NAME, features,
                f"momentum={features.momentum_proxy:.2f} disagrees with edge={edge:.1f}c"
            )

        conf = min(0.80, 0.40 + abs(features.momentum_proxy) * 0.5 + fair.confidence * 0.2)

        return _make_signal(
            self.NAME, features, fair, direction, conf,
            Regime.TRENDING,
            f"momentum={features.momentum_proxy:.2f} edge={edge:.1f}c "
            f"set_lead={features.set_lead:+d} game_lead={features.game_lead:+d}",
        )


# ------------------------------------------------------------------ #
# All tennis strategies list
# ------------------------------------------------------------------ #

ALL_TENNIS_STRATEGIES = [
    TennisFavoriteHold,
    TennisBreakPointOverreaction,
    TennisPostBreakReversion,
    TennisTiebreakChaosAvoider,
    TennisMomentumContinuation,
]


def make_tennis_strategies() -> list:
    return [cls() for cls in ALL_TENNIS_STRATEGIES]
