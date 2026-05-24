from __future__ import annotations

"""
Volatility engine. Drives per-tick price increments for the simulated mid.
Deterministic given a seed.
"""

import random
from dataclasses import dataclass
from enum import Enum


class VolatilityRegime(str, Enum):
    CALM = "CALM"
    TRENDING = "TRENDING"
    PANIC = "PANIC"
    REVERSAL = "REVERSAL"
    DEAD = "DEAD"
    CHAOTIC_ENDGAME = "CHAOTIC_ENDGAME"


@dataclass
class _VolParams:
    sigma: float       # std-dev of per-tick increment (cents)
    drift: float       # mean per-tick increment (cents)


_PROFILES = {
    VolatilityRegime.CALM: _VolParams(sigma=0.6, drift=0.0),
    VolatilityRegime.TRENDING: _VolParams(sigma=1.2, drift=1.0),
    VolatilityRegime.PANIC: _VolParams(sigma=4.5, drift=-2.5),
    VolatilityRegime.REVERSAL: _VolParams(sigma=3.0, drift=0.0),
    VolatilityRegime.DEAD: _VolParams(sigma=0.15, drift=0.0),
    VolatilityRegime.CHAOTIC_ENDGAME: _VolParams(sigma=6.0, drift=0.0),
}


class VolatilityEngine:
    def __init__(self, seed: int = 1337) -> None:
        self._rng = random.Random(seed)
        self._reversal_sign = 1.0

    def increment(self, regime: VolatilityRegime) -> float:
        """Return a signed price increment (cents) for one tick."""
        p = _PROFILES[regime]
        shock = self._rng.gauss(0.0, p.sigma)

        if regime == VolatilityRegime.REVERSAL:
            # alternate the drift sign to whipsaw price
            self._reversal_sign *= -1.0
            return round(self._reversal_sign * abs(self._rng.gauss(2.0, p.sigma)) + shock * 0.2, 2)

        return round(p.drift + shock, 2)

    def realized_vol(self, regime: VolatilityRegime) -> float:
        """Expected realized volatility (cents) for a regime — used by classifiers."""
        return _PROFILES[regime].sigma
