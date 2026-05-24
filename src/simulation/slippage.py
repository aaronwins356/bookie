from __future__ import annotations

"""
Slippage model. Estimates the realized average fill price for an order,
accounting for order size relative to available depth and the volatility
regime (panic conditions produce far worse slippage).
"""

from dataclasses import dataclass
from src.simulation.volatility import VolatilityRegime


@dataclass
class SlippageResult:
    requested_price: float
    realized_price: float
    slippage_cents: float
    size_penalty: float
    regime_penalty: float


_REGIME_PENALTY = {
    VolatilityRegime.CALM: 0.2,
    VolatilityRegime.TRENDING: 0.6,
    VolatilityRegime.PANIC: 3.0,
    VolatilityRegime.REVERSAL: 1.2,
    VolatilityRegime.DEAD: 0.1,
    VolatilityRegime.CHAOTIC_ENDGAME: 4.0,
}


class SlippageModel:
    def __init__(self, impact_coeff: float = 4.0) -> None:
        # cents of slippage per unit of (size / depth)
        self.impact_coeff = impact_coeff

    def estimate(
        self,
        requested_price: float,
        size: int,
        available_depth: int,
        regime: VolatilityRegime,
        is_buy: bool = True,
    ) -> SlippageResult:
        depth = max(1, available_depth)
        size_ratio = size / depth

        size_penalty = self.impact_coeff * size_ratio
        regime_penalty = _REGIME_PENALTY.get(regime, 0.5)

        # Buys slip up (pay more), sells slip down (receive less). In cents
        # of the YES price; the caller interprets direction.
        total = size_penalty + regime_penalty
        direction = 1.0 if is_buy else -1.0
        realized = requested_price + direction * total

        realized = max(0.0, min(100.0, realized))
        return SlippageResult(
            requested_price=round(requested_price, 2),
            realized_price=round(realized, 2),
            slippage_cents=round(abs(realized - requested_price), 2),
            size_penalty=round(size_penalty, 2),
            regime_penalty=round(regime_penalty, 2),
        )
