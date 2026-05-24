from __future__ import annotations

from typing import Optional
from src.engine.features import FeatureSet
from src.models import Signal, SignalDirection, Regime
from src.simulation.market_regime import MarketRegime
from src.strategies.base import StrategyProfile, apply_regime


class LiquidityVacuum:
    """
    Post thin-book events: low volume + wide spread → mean reversion opportunity.
    Provides liquidity by fading extreme prices in illiquid conditions.

    Exists for exactly the regimes others avoid — liquidity collapse and
    dead markets — and is dangerous in fast directional moves.
    """

    NAME = "liquidity_vacuum"

    profile = StrategyProfile(
        name=NAME,
        liquidity_sensitivity=-0.8,
        volatility_sensitivity=-0.2,
        estimated_risk=0.7,
        estimated_holding_time=6,
        favored_regimes=(MarketRegime.LIQUIDITY_COLLAPSE, MarketRegime.DEAD_MARKET),
        averse_regimes=(
            MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN,
            MarketRegime.PANIC_SELLING,
        ),
    )

    def __init__(
        self,
        min_spread: float = 6.0,
        max_volume: int = 200,
        extreme_threshold: float = 20.0,
    ) -> None:
        self.min_spread = min_spread
        self.max_volume = max_volume
        self.extreme_threshold = extreme_threshold

    def regime_compatibility(self, regime: MarketRegime) -> float:
        return self.profile.regime_compatibility(regime)

    def evaluate(self, features: FeatureSet, regime: Optional[MarketRegime] = None) -> Signal:
        is_illiquid = (
            features.spread >= self.min_spread
            and features.volume <= self.max_volume
        )

        if not is_illiquid:
            return apply_regime(self._hold(features, "market is liquid"), self.profile, regime)

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
            return apply_regime(self._hold(features, "price not extreme enough"), self.profile, regime)

        signal = Signal(
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
        return apply_regime(signal, self.profile, regime)

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
