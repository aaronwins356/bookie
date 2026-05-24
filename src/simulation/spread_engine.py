from __future__ import annotations

"""
Spread engine. Computes the bid/ask spread (cents) given current
volatility, available liquidity, and proximity to the 0/100 boundaries.
Spreads widen during volatility and when liquidity is thin.
"""

from dataclasses import dataclass
from src.simulation.volatility import VolatilityRegime


@dataclass
class SpreadEngine:
    base_spread: float = 2.0
    min_spread: float = 1.0
    max_spread: float = 30.0

    def compute(
        self,
        regime: VolatilityRegime,
        liquidity_multiplier: float,
        mid_price: float,
        realized_vol: float,
    ) -> float:
        spread = self.base_spread

        # Volatility widens the spread.
        spread += realized_vol * 1.2

        # Thin liquidity widens the spread (inverse of depth multiplier).
        if liquidity_multiplier > 0:
            spread *= 1.0 + (1.0 / liquidity_multiplier - 1.0) * 0.5

        # Regime overrides.
        if regime == VolatilityRegime.PANIC:
            spread *= 2.0
        elif regime == VolatilityRegime.CHAOTIC_ENDGAME:
            spread *= 2.5
        elif regime == VolatilityRegime.DEAD:
            spread *= 0.6

        # Near the boundaries (0/100) books are naturally tighter.
        edge_dist = min(mid_price, 100.0 - mid_price)
        if edge_dist < 10.0:
            spread *= 0.7

        return round(max(self.min_spread, min(self.max_spread, spread)), 1)
