from __future__ import annotations

from typing import Optional
from src.models import Signal, SignalDirection, OrderIntent, OrderSide


class Router:
    """
    Converts a Signal into an OrderIntent.

    Rules:
    - BUY signal  → YES side at (fair_value - half_spread)
    - SELL signal → NO  side at (100 - fair_value - half_spread)
    - HOLD signal → None
    - Size is proportional to confidence (Kelly-lite, capped at max_size)
    """

    def __init__(self, base_size: int = 10, max_size: int = 50) -> None:
        self.base_size = base_size
        self.max_size = max_size

    def route(self, signal: Signal) -> Optional[OrderIntent]:
        if signal.direction == SignalDirection.HOLD:
            return None
        if not signal.is_actionable():
            return None

        side = OrderSide.YES if signal.direction == SignalDirection.BUY else OrderSide.NO
        limit_price = self._limit_price(signal, side)
        size = self._kelly_size(signal)

        return OrderIntent(
            market_id=signal.market_id,
            side=side,
            price=limit_price,
            size=size,
            strategy_name=signal.strategy_name,
            signal_id=signal.signal_id,
            notes=f"edge={signal.edge:.1f} conf={signal.confidence:.2f}",
        )

    def _limit_price(self, signal: Signal, side: OrderSide) -> float:
        half_spread = 0.5
        if side == OrderSide.YES:
            return round(signal.fair_value - half_spread, 1)
        else:
            return round(100.0 - signal.fair_value - half_spread, 1)

    def _kelly_size(self, signal: Signal) -> int:
        fraction = min(signal.confidence, 0.8)
        size = int(self.base_size * fraction * (abs(signal.edge) / 5.0))
        return max(1, min(size, self.max_size))
