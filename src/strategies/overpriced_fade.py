from __future__ import annotations

from typing import Optional
from src.engine.features import FeatureSet
from src.engine.fair_value import FairValueModel
from src.models import Signal, SignalDirection, Regime
from src.simulation.market_regime import MarketRegime
from src.strategies.base import StrategyProfile, apply_regime


class OverpricedFade:
    """
    Fade the overpriced side when the market overreacts to a scoring event.
    Triggered when mid > fair_value + threshold.

    Best when markets overreact — panic buying and favorite euphoria; poor
    in genuine trends where "overpriced" keeps getting more expensive.
    """

    NAME = "overpriced_fade"

    profile = StrategyProfile(
        name=NAME,
        liquidity_sensitivity=0.5,
        volatility_sensitivity=0.3,
        estimated_risk=0.5,
        estimated_holding_time=5,
        favored_regimes=(
            MarketRegime.PANIC_BUYING, MarketRegime.FAVORITE_EUPHORIA,
            MarketRegime.MEAN_REVERSION,
        ),
        averse_regimes=(MarketRegime.TRENDING_UP, MarketRegime.ENDGAME_CHAOS),
    )

    def __init__(self, fade_threshold: float = 8.0) -> None:
        self.fade_threshold = fade_threshold
        self._fv = FairValueModel()

    def regime_compatibility(self, regime: MarketRegime) -> float:
        return self.profile.regime_compatibility(regime)

    def evaluate(self, features: FeatureSet, regime: Optional[MarketRegime] = None) -> Signal:
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

        signal = Signal(
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
        return apply_regime(signal, self.profile, regime)
