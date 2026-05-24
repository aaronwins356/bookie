from __future__ import annotations

from src.engine.features import FeatureSet
from src.models import Signal, SignalDirection, Regime


class MomentumStrategy:
    """
    If the market price is moving strongly in one direction (via repeated
    calls), follow it. Requires state between ticks.
    """

    NAME = "momentum"

    def __init__(self, momentum_threshold: float = 5.0) -> None:
        self.momentum_threshold = momentum_threshold
        self._prev_mid: dict[str, float] = {}

    def evaluate(self, features: FeatureSet) -> Signal:
        prev = self._prev_mid.get(features.market_id)
        mid = features.mid_price
        self._prev_mid[features.market_id] = mid

        if prev is None:
            return self._hold(features, mid, "no previous tick")

        delta = mid - prev

        if delta >= self.momentum_threshold:
            direction = SignalDirection.BUY
            confidence = min(0.75, 0.4 + delta / 20.0)
            edge = delta * 0.5
        elif delta <= -self.momentum_threshold:
            direction = SignalDirection.SELL
            confidence = min(0.75, 0.4 + abs(delta) / 20.0)
            edge = delta * 0.5
        else:
            return self._hold(features, mid, f"delta={delta:.1f} below threshold")

        return Signal(
            strategy_name=self.NAME,
            market_id=features.market_id,
            direction=direction,
            confidence=confidence,
            fair_value=mid + edge,
            current_price=mid,
            edge=edge,
            regime=Regime.TRENDING,
            notes=f"delta={delta:.1f}",
        )

    def _hold(self, features: FeatureSet, mid: float, reason: str) -> Signal:
        return Signal(
            strategy_name=self.NAME,
            market_id=features.market_id,
            direction=SignalDirection.HOLD,
            confidence=0.0,
            fair_value=mid,
            current_price=mid,
            edge=0.0,
            regime=Regime.UNKNOWN,
            notes=reason,
        )
