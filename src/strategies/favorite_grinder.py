from __future__ import annotations

from src.engine.features import FeatureSet
from src.engine.fair_value import FairValueModel
from src.models import Signal, SignalDirection, Regime


class FavoriteGrinder:
    """
    Back the leading team when they are priced too cheaply relative to
    their empirical win probability given score margin + time remaining.
    """

    NAME = "favorite_grinder"

    def __init__(self, min_edge: float = 3.0) -> None:
        self.min_edge = min_edge
        self._fv = FairValueModel()

    def evaluate(self, features: FeatureSet) -> Signal:
        fair = self._fv.estimate(features)
        mid = features.mid_price
        edge = fair - mid

        if abs(features.score_diff) < 3:
            direction = SignalDirection.HOLD
            confidence = 0.0
        elif edge >= self.min_edge and features.score_diff > 0:
            direction = SignalDirection.BUY
            confidence = min(0.9, 0.5 + edge / 20.0)
        elif -edge >= self.min_edge and features.score_diff < 0:
            direction = SignalDirection.SELL
            confidence = min(0.9, 0.5 + abs(edge) / 20.0)
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
            regime=Regime.TRENDING,
            notes=f"score_diff={features.score_diff} time_pressure={features.time_pressure:.2f}",
        )
