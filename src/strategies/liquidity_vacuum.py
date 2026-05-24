from __future__ import annotations

from src.engine.features import FeatureSet
from src.models import Signal, SignalDirection, Regime


class LiquidityVacuum:
    """
    Post thin-book events: low volume + wide spread → mean reversion opportunity.
    Provides liquidity by fading extreme prices in illiquid conditions.
    """

    NAME = "liquidity_vacuum"

    def __init__(
        self,
        min_spread: float = 6.0,
        max_volume: int = 200,
        extreme_threshold: float = 20.0,
    ) -> None:
        self.min_spread = min_spread
        self.max_volume = max_volume
        self.extreme_threshold = extreme_threshold

    def evaluate(self, features: FeatureSet) -> Signal:
        is_illiquid = (
            features.spread >= self.min_spread
            and features.volume <= self.max_volume
        )

        if not is_illiquid:
            return self._hold(features, "market is liquid")

        mid = features.mid_price
        edge = 0.0

        if mid > (100.0 - self.extreme_threshold):
            direction = SignalDirection.SELL
            edge = mid - (100.0 - self.extreme_threshold)
            confidence = 0.6
        elif mid < self.extreme_threshold:
            direction = SignalDirection.BUY
            edge = self.extreme_threshold - mid
            confidence = 0.6
        else:
            return self._hold(features, "price not extreme enough")

        return Signal(
            strategy_name=self.NAME,
            market_id=features.market_id,
            direction=direction,
            confidence=confidence,
            fair_value=mid + (edge if direction == SignalDirection.BUY else -edge),
            current_price=mid,
            edge=edge if direction == SignalDirection.BUY else -edge,
            regime=Regime.ILLIQUID,
            notes=f"spread={features.spread:.1f} volume={features.volume}",
        )

    def _hold(self, features: FeatureSet, reason: str) -> Signal:
        return Signal(
            strategy_name=self.NAME,
            market_id=features.market_id,
            direction=SignalDirection.HOLD,
            confidence=0.0,
            fair_value=features.mid_price,
            current_price=features.mid_price,
            edge=0.0,
            regime=Regime.ILLIQUID,
            notes=reason,
        )
