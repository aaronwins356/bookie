from __future__ import annotations

from src.engine.features import FeatureSet
from src.engine.fair_value import FairValueModel
from src.models import Signal, SignalDirection, Regime


class OverpricedFade:
    """
    Fade the overpriced side when the market overreacts to a scoring event.
    Triggered when mid > fair_value + threshold.
    """

    NAME = "overpriced_fade"

    def __init__(self, fade_threshold: float = 8.0) -> None:
        self.fade_threshold = fade_threshold
        self._fv = FairValueModel()

    def evaluate(self, features: FeatureSet) -> Signal:
        fair = self._fv.estimate(features)
        mid = features.mid_price
        edge = fair - mid  # negative means market overpriced YES

        if edge <= -self.fade_threshold:
            direction = SignalDirection.SELL
            confidence = min(0.85, 0.5 + abs(edge) / 20.0)
        elif edge >= self.fade_threshold:
            # market too cheap on YES — not a fade scenario
            direction = SignalDirection.HOLD
            confidence = 0.0
        else:
            direction = SignalDirection.HOLD
            confidence = 0.0

        return Signal(
            strategy_name=self.NAME,
            market_id=features.market_id,
            direction=direction,
            confidence=confidence,
            fair_value=fair,
            current_price=mid,
            edge=edge,
            regime=Regime.MEAN_REVERTING,
            notes=f"fade_threshold={self.fade_threshold} edge={edge:.1f}",
        )
