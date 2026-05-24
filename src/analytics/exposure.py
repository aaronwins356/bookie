from __future__ import annotations

"""
Exposure tracking. Aggregates open notional exposure by market, by
strategy, and by direction — the inputs for an exposure heatmap.
"""

from dataclasses import dataclass, field
from typing import Dict
from src.models import OrderSide


@dataclass
class ExposureTracker:
    by_market: Dict[str, float] = field(default_factory=dict)
    by_strategy: Dict[str, float] = field(default_factory=dict)
    by_direction: Dict[str, float] = field(default_factory=dict)

    def add(self, market_id: str, strategy: str, side: OrderSide, price: float, size: int) -> None:
        notional = price * size / 100.0   # dollars (100c = $1 payout)
        self.by_market[market_id] = self.by_market.get(market_id, 0.0) + notional
        self.by_strategy[strategy] = self.by_strategy.get(strategy, 0.0) + notional
        self.by_direction[side.value] = self.by_direction.get(side.value, 0.0) + notional

    def total(self) -> float:
        return round(sum(self.by_market.values()), 2)

    def heatmap(self) -> Dict[str, Dict[str, float]]:
        return {
            "by_market": {k: round(v, 2) for k, v in self.by_market.items()},
            "by_strategy": {k: round(v, 2) for k, v in self.by_strategy.items()},
            "by_direction": {k: round(v, 2) for k, v in self.by_direction.items()},
        }

    def concentration(self) -> float:
        """Herfindahl index over market exposure (0=diversified,1=concentrated)."""
        total = sum(self.by_market.values())
        if total <= 0:
            return 0.0
        return round(sum((v / total) ** 2 for v in self.by_market.values()), 3)
