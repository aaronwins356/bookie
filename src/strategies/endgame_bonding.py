from __future__ import annotations

from typing import Optional
from src.engine.features import FeatureSet
from src.engine.fair_value import FairValueModel
from src.models import Signal, SignalDirection, Regime
from src.simulation.market_regime import MarketRegime
from src.strategies.base import StrategyProfile, apply_regime


class EndgameBonding:
    """
    Late-game, large-lead strategy: market is slow to price in
    near-certain outcomes when time pressure > 0.85 and lead > 10.

    Thrives precisely when others panic — endgame chaos, panic selling,
    and liquidity collapse create the mispricings it captures.
    """

    NAME = "endgame_bonding"

    profile = StrategyProfile(
        name=NAME,
        liquidity_sensitivity=0.2,
        volatility_sensitivity=0.8,
        estimated_risk=0.55,
        estimated_holding_time=3,
        favored_regimes=(MarketRegime.ENDGAME_CHAOS, MarketRegime.PANIC_SELLING, MarketRegime.LIQUIDITY_COLLAPSE),
        averse_regimes=(MarketRegime.DEAD_MARKET, MarketRegime.CALM),
    )

    def __init__(self, time_threshold: float = 0.85, lead_threshold: int = 10) -> None:
        self.time_threshold = time_threshold
        self.lead_threshold = lead_threshold
        self._fv = FairValueModel()

    def regime_compatibility(self, regime: MarketRegime) -> float:
        return self.profile.regime_compatibility(regime)

    def evaluate(self, features: FeatureSet, regime: Optional[MarketRegime] = None) -> Signal:
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

        signal = Signal(
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
        return apply_regime(signal, self.profile, regime)
