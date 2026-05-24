from __future__ import annotations

"""
Formal market-regime classification.

This is the *microstructure* regime (distinct from the lightweight
`src.models.Regime` used by individual strategies). It is classified
deterministically from observable market metrics so it can be audited
and reproduced.
"""

from dataclasses import dataclass
from enum import Enum


class MarketRegime(str, Enum):
    CALM = "CALM"
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    PANIC_BUYING = "PANIC_BUYING"
    PANIC_SELLING = "PANIC_SELLING"
    FAVORITE_EUPHORIA = "FAVORITE_EUPHORIA"
    ENDGAME_CHAOS = "ENDGAME_CHAOS"
    LIQUIDITY_COLLAPSE = "LIQUIDITY_COLLAPSE"
    DEAD_MARKET = "DEAD_MARKET"
    MEAN_REVERSION = "MEAN_REVERSION"


@dataclass
class RegimeInputs:
    """Observable metrics fed to the classifier."""

    spread: float                 # cents
    odds_velocity: float          # signed cents/sec change in mid
    liquidity_depth: int          # contracts available within top levels
    volatility: float             # recent stddev of mid (cents)
    time_remaining: int           # seconds left in game
    score_diff: int               # home - away
    order_flow_imbalance: float   # -1 (selling) .. +1 (buying)
    mid_price: float = 50.0       # current mid (cents)


class RegimeClassifier:
    """
    Deterministic decision tree. Ordering matters: the most extreme /
    structurally-dominant conditions are checked first.
    """

    def __init__(
        self,
        wide_spread: float = 6.0,
        thin_depth: int = 150,
        high_vol: float = 4.0,
        dead_vol: float = 0.4,
        fast_odds: float = 0.05,     # cents/sec
        endgame_seconds: int = 120,
        panic_imbalance: float = 0.6,
    ) -> None:
        self.wide_spread = wide_spread
        self.thin_depth = thin_depth
        self.high_vol = high_vol
        self.dead_vol = dead_vol
        self.fast_odds = fast_odds
        self.endgame_seconds = endgame_seconds
        self.panic_imbalance = panic_imbalance

    def classify(self, x: RegimeInputs) -> MarketRegime:
        # 1. Structural liquidity failure dominates everything.
        if x.liquidity_depth < self.thin_depth and x.spread >= self.wide_spread:
            return MarketRegime.LIQUIDITY_COLLAPSE

        # 2. Endgame chaos: little time, real volatility, contested.
        if (
            x.time_remaining <= self.endgame_seconds
            and x.volatility >= self.high_vol
            and abs(x.score_diff) <= 8
        ):
            return MarketRegime.ENDGAME_CHAOS

        # 3. Dead market: essentially no movement and no volatility.
        if x.volatility <= self.dead_vol and abs(x.odds_velocity) < self.fast_odds / 4:
            return MarketRegime.DEAD_MARKET

        # 4. Panic: fast move + lopsided flow.
        if abs(x.odds_velocity) >= self.fast_odds and abs(x.order_flow_imbalance) >= self.panic_imbalance:
            if x.order_flow_imbalance > 0:
                return MarketRegime.PANIC_BUYING
            return MarketRegime.PANIC_SELLING

        # 5. Favorite euphoria: heavy favorite pushed even higher late.
        if x.mid_price >= 80.0 and x.score_diff > 10 and x.odds_velocity > 0:
            return MarketRegime.FAVORITE_EUPHORIA

        # 6. Sustained directional drift.
        if x.odds_velocity >= self.fast_odds:
            return MarketRegime.TRENDING_UP
        if x.odds_velocity <= -self.fast_odds:
            return MarketRegime.TRENDING_DOWN

        # 7. Choppy but range-bound with measurable volatility.
        if x.volatility >= self.high_vol:
            return MarketRegime.MEAN_REVERSION

        # 8. Default.
        return MarketRegime.CALM
