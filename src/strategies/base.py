from __future__ import annotations

"""
Strategy profile metadata and shared helpers.

Every strategy exposes a `profile` describing its sensitivities and which
market regimes it thrives or struggles in, plus a `regime_compatibility`
score used by the portfolio router to rank and scale opportunities.

Strategies remain pure signal generators — this module adds metadata and
a regime-aware confidence adjustment but never touches execution or risk.
"""

from dataclasses import dataclass, field
from typing import Tuple
from src.models import Signal
from src.simulation.market_regime import MarketRegime


@dataclass(frozen=True)
class StrategyProfile:
    name: str
    liquidity_sensitivity: float          # 0 = liquidity-agnostic, 1 = needs deep books
    volatility_sensitivity: float         # -1 = vol hurts, +1 = vol helps
    estimated_risk: float                 # 0 = low risk, 1 = high risk
    estimated_holding_time: int           # ticks expected to hold a position
    favored_regimes: Tuple[MarketRegime, ...] = ()
    averse_regimes: Tuple[MarketRegime, ...] = ()

    def regime_compatibility(self, regime: MarketRegime) -> float:
        """Return a 0..1 compatibility score for the given regime."""
        if regime in self.favored_regimes:
            return 1.0
        if regime in self.averse_regimes:
            return 0.1
        return 0.5


def expected_value(signal: Signal) -> float:
    """EV proxy in cents: realizable edge weighted by confidence."""
    return round(abs(signal.edge) * signal.confidence, 3)


def apply_regime(signal: Signal, profile: StrategyProfile, regime: MarketRegime | None) -> Signal:
    """
    Mildly modulate a signal's confidence by regime compatibility. A no-op
    when `regime` is None (preserves base behavior).

    The multiplier maps compat∈[0,1] → [0.55, 1.0] so a neutral regime only
    lightly trims confidence. Regime has a *stronger* effect on ranking and
    sizing (handled by PortfolioRouter via ev×compat and by RiskManager via
    regime risk scaling); confidence is only nudged here so good signals stay
    actionable outside their ideal regime.
    """
    if regime is None:
        return signal
    compat = profile.regime_compatibility(regime)
    multiplier = 0.55 + 0.45 * compat
    signal.confidence = round(signal.confidence * multiplier, 4)
    signal.notes = f"{signal.notes} | regime={regime.value} compat={compat:.2f}"
    return signal
