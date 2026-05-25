from __future__ import annotations

"""
Tennis market regime classification.

Tennis regimes are distinct from the generic market microstructure regimes
(MarketRegime) in src/simulation/market_regime.py. They describe what is
happening in the match that drives market behavior — not orderbook topology.

The regime is used by tennis strategies to gate activity:
  - Some strategies only activate in specific regimes.
  - The TennisTiebreakChaosAvoider explicitly holds in TIEBREAK_CHAOS.
  - POST_BREAK_OVERREACTION is the primary alpha regime for reversion strategies.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List

from src.sports.tennis.features import TennisFeatureSet
from src.sports.tennis.state import TennisState


class TennisRegime(str, Enum):
    CALM_HOLD_PATTERN = "CALM_HOLD_PATTERN"
    SERVER_PRESSURE = "SERVER_PRESSURE"
    BREAK_POINT_PRESSURE = "BREAK_POINT_PRESSURE"
    POST_BREAK_OVERREACTION = "POST_BREAK_OVERREACTION"
    TIEBREAK_CHAOS = "TIEBREAK_CHAOS"
    SET_POINT_PRESSURE = "SET_POINT_PRESSURE"
    MATCH_POINT_PRESSURE = "MATCH_POINT_PRESSURE"
    RETIREMENT_RISK = "RETIREMENT_RISK"
    SUSPENDED_OR_DELAYED = "SUSPENDED_OR_DELAYED"
    LOW_LIQUIDITY = "LOW_LIQUIDITY"


@dataclass
class RegimeResult:
    regime: TennisRegime
    confidence: float       # 0–1 confidence in this classification
    reasons: List[str]


class TennisRegimeClassifier:
    """
    Rule-based decision tree. Checked in priority order:
    highest-impact / most-structurally-dominant conditions first.
    """

    # Thresholds
    LOW_LIQ_SPREAD = 8.0
    LOW_LIQ_SCORE = 0.25
    OVERREACTION_THRESHOLD = 0.12   # |implied - rough_fair| above this = overreaction
    SERVER_PRESSURE_RETURN_THRESH = 0.35

    def classify(
        self, features: TennisFeatureSet, state: TennisState
    ) -> RegimeResult:
        reasons: List[str] = []

        # 1. Match over / retirement
        if state.retired:
            return RegimeResult(
                TennisRegime.RETIREMENT_RISK, 1.0, ["player retired"]
            )

        # 2. Suspension
        if state.suspended:
            return RegimeResult(
                TennisRegime.SUSPENDED_OR_DELAYED, 1.0, ["match suspended"]
            )

        # 3. Low liquidity (structurally blocks good fills)
        if (
            features.market_spread >= self.LOW_LIQ_SPREAD
            or features.liquidity_score < self.LOW_LIQ_SCORE
        ):
            reasons = [
                f"spread={features.market_spread:.1f}c",
                f"liquidity={features.liquidity_score:.2f}",
            ]
            return RegimeResult(TennisRegime.LOW_LIQUIDITY, 0.85, reasons)

        # 4. Match point
        if features.match_point:
            return RegimeResult(
                TennisRegime.MATCH_POINT_PRESSURE,
                0.95,
                ["match_point=True"],
            )

        # 5. Tiebreak chaos
        if features.tiebreak:
            tb_pressure = features.point_pressure
            return RegimeResult(
                TennisRegime.TIEBREAK_CHAOS,
                min(0.95, 0.65 + tb_pressure * 0.3),
                [f"tiebreak pts {state.points_a}-{state.points_b}"],
            )

        # 6. Set point
        if features.set_point:
            return RegimeResult(
                TennisRegime.SET_POINT_PRESSURE,
                0.85,
                ["set_point=True"],
            )

        # 7. Break point pressure
        if features.break_point:
            return RegimeResult(
                TennisRegime.BREAK_POINT_PRESSURE,
                0.80 + features.break_points_count * 0.05,
                [f"break_point, count={features.break_points_count}"],
            )

        # 8. Post-break overreaction
        if features.market_overreaction_score >= self.OVERREACTION_THRESHOLD:
            return RegimeResult(
                TennisRegime.POST_BREAK_OVERREACTION,
                min(0.80, 0.50 + features.market_overreaction_score * 2.0),
                [
                    f"overreaction_score={features.market_overreaction_score:.2f}",
                    f"implied={features.implied_probability:.2f}",
                ],
            )

        # 9. Server under sustained pressure (not break point but wobbling)
        if features.return_pressure >= self.SERVER_PRESSURE_RETURN_THRESH:
            return RegimeResult(
                TennisRegime.SERVER_PRESSURE,
                0.65,
                [f"return_pressure={features.return_pressure:.2f}"],
            )

        # 10. Default: calm hold pattern
        return RegimeResult(
            TennisRegime.CALM_HOLD_PATTERN,
            0.70,
            ["no elevated pressure detected"],
        )
