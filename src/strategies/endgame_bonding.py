from __future__ import annotations

from src.engine.features import FeatureSet
from src.engine.fair_value import FairValueModel
from src.models import Signal, SignalDirection, Regime


class EndgameBonding:
    """
    Late-game, large-lead strategy: market is slow to price in
    near-certain outcomes when time pressure > 0.85 and lead > 10.
    """

    NAME = "endgame_bonding"

    def __init__(self, time_threshold: float = 0.85, lead_threshold: int = 10) -> None:
        self.time_threshold = time_threshold
        self.lead_threshold = lead_threshold
        self._fv = FairValueModel()

    def evaluate(self, features: FeatureSet) -> Signal:
        fair = self._fv.estimate(features)
        mid = features.mid_price
        edge = fair - mid

        in_endgame = features.time_pressure >= self.time_threshold
        big_lead = abs(features.score_diff) >= self.lead_threshold

        if in_endgame and big_lead and abs(edge) >= 4.0:
            direction = SignalDirection.BUY if edge > 0 else SignalDirection.SELL
            confidence = min(0.95, 0.6 + features.time_pressure * 0.35)
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
            regime=Regime.ENDGAME,
            notes=f"endgame={in_endgame} big_lead={big_lead}",
        )
