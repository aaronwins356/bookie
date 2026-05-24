from __future__ import annotations

from typing import Optional
from src.engine.features import FeatureSet
from src.models import Signal, SignalDirection, Regime
from src.simulation.market_regime import MarketRegime
from src.strategies.base import StrategyProfile, apply_regime


class MomentumStrategy:
    """
    If the market price is moving strongly in one direction (via repeated
    calls), follow it. Requires state between ticks.

    Loves directional trends and panic moves; useless in dead or
    mean-reverting markets where moves reverse.
    """

    NAME = "momentum"

    profile = StrategyProfile(
        name=NAME,
        liquidity_sensitivity=0.4,
        volatility_sensitivity=0.7,
        estimated_risk=0.6,
        estimated_holding_time=4,
        favored_regimes=(
            MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN,
            MarketRegime.PANIC_BUYING, MarketRegime.PANIC_SELLING,
        ),
        averse_regimes=(MarketRegime.DEAD_MARKET, MarketRegime.MEAN_REVERSION),
    )

    def __init__(self, momentum_threshold: float = 5.0) -> None:
        self.momentum_threshold = momentum_threshold
        self._prev_mid: dict[str, float] = {}

    def regime_compatibility(self, regime: MarketRegime) -> float:
        return self.profile.regime_compatibility(regime)

    def evaluate(self, features: FeatureSet, regime: Optional[MarketRegime] = None) -> Signal:
        prev = self._prev_mid.get(features.market_id)
        mid = features.mid_price
        self._prev_mid[features.market_id] = mid

        if prev is None:
            return apply_regime(self._hold(features, mid, "no previous tick"), self.profile, regime)

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
            return apply_regime(self._hold(features, mid, f"delta={delta:.1f} below threshold"), self.profile, regime)

        signal = Signal(
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
        return apply_regime(signal, self.profile, regime)

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
