from __future__ import annotations

"""
Liquidity engine. Models how much depth is available and how wide the
book is, as a function of game time and the active volatility regime.
"""

import random
from dataclasses import dataclass
from src.simulation.volatility import VolatilityRegime


@dataclass
class LiquidityProfile:
    depth: int            # contracts available near top of book
    depth_multiplier: float   # 1.0 = normal, <1 = thin
    is_collapsed: bool


class LiquidityEngine:
    """
    Produces a LiquidityProfile per tick. Liquidity:
    - shrinks as the game nears its end (endgame collapse)
    - collapses hard during PANIC / CHAOTIC_ENDGAME
    - can randomly vanish ("sudden disappearance") with small probability
    """

    def __init__(
        self,
        base_depth: int = 800,
        collapse_prob: float = 0.05,
        seed: int = 7,
    ) -> None:
        self.base_depth = base_depth
        self.collapse_prob = collapse_prob
        self._rng = random.Random(seed)

    def profile(
        self,
        regime: VolatilityRegime,
        time_remaining: int,
        total_clock: int = 1800,
    ) -> LiquidityProfile:
        mult = 1.0

        # Endgame liquidity decay: depth thins as clock → 0.
        if total_clock > 0:
            frac_left = max(0.0, min(1.0, time_remaining / total_clock))
            mult *= 0.35 + 0.65 * frac_left

        # Regime effects.
        if regime == VolatilityRegime.PANIC:
            mult *= 0.4
        elif regime == VolatilityRegime.CHAOTIC_ENDGAME:
            mult *= 0.25
        elif regime == VolatilityRegime.DEAD:
            mult *= 0.6
        elif regime == VolatilityRegime.TRENDING:
            mult *= 0.85

        # Sudden disappearance.
        collapsed = self._rng.random() < self.collapse_prob
        if collapsed:
            mult *= 0.15

        depth = max(10, int(self.base_depth * mult))
        return LiquidityProfile(
            depth=depth,
            depth_multiplier=round(mult, 3),
            is_collapsed=collapsed or mult < 0.3,
        )
