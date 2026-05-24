from __future__ import annotations

from typing import Optional
from src.engine.features import FeatureSet
from src.engine.fair_value import FairValueModel
from src.models import Signal, SignalDirection, Regime
from src.simulation.market_regime import MarketRegime
from src.strategies.base import StrategyProfile, apply_regime


class FavoriteGrinder:
    """
    Back the leading team when they are priced too cheaply relative to
    their empirical win probability given score margin + time remaining.

    Strongest in calm, orderly markets; weakest in chaos where its
    fair-value model breaks down.
    """

    NAME = "favorite_grinder"

    profile = StrategyProfile(
        name=NAME,
        liquidity_sensitivity=0.6,
        volatility_sensitivity=-0.6,
        estimated_risk=0.35,
        estimated_holding_time=8,
        favored_regimes=(MarketRegime.CALM, MarketRegime.TRENDING_UP, MarketRegime.MEAN_REVERSION),
        averse_regimes=(MarketRegime.ENDGAME_CHAOS, MarketRegime.PANIC_SELLING, MarketRegime.LIQUIDITY_COLLAPSE),
    )

    def __init__(self, min_edge: float = 3.0) -> None:
        self.min_edge = min_edge
        self._fv = FairValueModel()

    def regime_compatibility(self, regime: MarketRegime) -> float:
        return self.profile.regime_compatibility(regime)

    def evaluate(self, features: FeatureSet, regime: Optional[MarketRegime] = None) -> Signal:
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

        signal = Signal(
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
        return apply_regime(signal, self.profile, regime)
