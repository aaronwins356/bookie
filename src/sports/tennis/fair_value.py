from __future__ import annotations

"""
Tennis fair value model — deterministic, heuristic, first version.

Estimates the probability that Player A wins the match from the current
match state. Returns fair_probability (0–1), confidence (0–1), and
a list of human-readable reasons explaining each adjustment.

WARNINGS:
- This model is heuristic, not empirically fitted to historical data.
- Coefficients are based on published win-probability research but not
  calibrated to specific tours, players, or surfaces.
- Do NOT use this as proof of live edge. It is a starting point for research.
- Results must be backtested across many real matches before trusting them.

Design principles:
- All adjustments are additive on a logit scale, then converted to probability.
- Every adjustment has a named reason so the output is auditable.
- Maximum uncertainty is always preserved: output is clamped to [0.02, 0.98].
"""

import math
from dataclasses import dataclass, field
from typing import List

from src.sports.tennis.features import TennisFeatureSet
from src.sports.tennis.state import Surface, TennisState


@dataclass
class TennisFairValueResult:
    fair_probability: float        # 0–1 probability that Player A wins
    fair_value_cents: float        # fair_probability × 100 for market comparison
    confidence: float              # 0–1 model confidence
    reasons: List[str] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    HEURISTIC_WARNING = (
        "HEURISTIC: Tennis fair value is rule-based, not ML-fitted. "
        "Not proven live edge. Backtest across 50+ matches before trusting."
    )

    def edge_cents(self, market_mid: float) -> float:
        """Signed edge vs market mid (positive = A underpriced)."""
        return round(self.fair_value_cents - market_mid, 2)


class TennisFairValueModel:
    """
    Deterministic logit-adjustment model.

    Start from 0.5 (equal players assumed), apply logit adjustments for
    each observable factor, then convert back to probability.

    Each adjustment is in logit units; typical adjustments:
      +0.5 logit ≈ +12% probability near 50%
      +1.0 logit ≈ +23% probability near 50%
      +2.0 logit ≈ +38% probability near 50%
    """

    # Base logit adjustments per factor (tuned to typical ATP/WTA observed rates)
    _SET_LEAD_ADJ = {
        # (sets_a, sets_b, best_of) → logit adj for A
    }

    # Logit adjustments per game lead in current set
    _GAME_LEAD_PER_GAME = 0.10      # each game of lead adds ~0.10 logit
    _GAME_LEAD_MAX_ADJ = 0.50       # cap on game-lead adjustment

    # Server advantage
    _SERVER_A_ADJ = {
        Surface.GRASS: 0.15,
        Surface.HARD: 0.10,
        Surface.INDOOR: 0.12,
        Surface.CLAY: 0.06,
        Surface.UNKNOWN: 0.10,
    }

    def estimate(
        self,
        features: TennisFeatureSet,
        state: TennisState,
    ) -> TennisFairValueResult:
        reasons: List[str] = []
        logit = 0.0  # start at 0.5

        # ---- 1. Set score ----------------------------------------- #
        logit_adj, reason = self._set_score_adjustment(state)
        logit += logit_adj
        reasons.append(reason)

        # ---- 2. Game score in current set -------------------------- #
        game_adj = max(
            -self._GAME_LEAD_MAX_ADJ,
            min(self._GAME_LEAD_MAX_ADJ, features.game_lead * self._GAME_LEAD_PER_GAME),
        )
        logit += game_adj
        reasons.append(
            f"game_lead={features.game_lead:+d} → logit {game_adj:+.2f}"
        )

        # ---- 3. Server identity ------------------------------------ #
        srv_adj = self._server_adjustment(state)
        logit += srv_adj
        if srv_adj != 0.0:
            reasons.append(
                f"server={'A' if srv_adj > 0 else 'B'} on {state.surface.value} → "
                f"logit {srv_adj:+.2f}"
            )

        # ---- 4. Tiebreak ------------------------------------------ #
        if features.tiebreak:
            tb_adj = self._tiebreak_adjustment(state)
            logit += tb_adj
            reasons.append(
                f"tiebreak pts {state.points_a}-{state.points_b} → logit {tb_adj:+.2f}"
            )

        # ---- 5. Point pressure situations -------------------------- #
        pressure_adj, pressure_reason = self._pressure_adjustment(features, state)
        logit += pressure_adj
        reasons.append(pressure_reason)

        # ---- 6. Retirement / suspension risk ----------------------- #
        if state.retired:
            # Match is over; determine winner from sets
            if state.sets_a > state.sets_b:
                logit = 5.0  # A wins
                reasons.append("retired: A leading → A wins match")
            else:
                logit = -5.0
                reasons.append("retired: B leading → B wins match")

        if state.suspended:
            # Pull toward 0.5 — very uncertain
            logit *= 0.5
            reasons.append("suspended: reducing conviction by 50%")

        # ---- Convert logit to probability -------------------------- #
        prob = _logit_to_prob(logit)
        prob = max(0.02, min(0.98, prob))

        confidence = self._confidence(features, state)
        reasons.append(TennisFairValueResult.HEURISTIC_WARNING)

        return TennisFairValueResult(
            fair_probability=round(prob, 4),
            fair_value_cents=round(prob * 100.0, 2),
            confidence=round(confidence, 3),
            reasons=reasons,
        )

    def _set_score_adjustment(self, state: TennisState) -> tuple[float, str]:
        """Logit adjustment based on sets won."""
        stw = state.sets_to_win
        sa, sb = state.sets_a, state.sets_b

        # Weights vary by how close each player is to winning
        a_needs = stw - sa
        b_needs = stw - sb

        if a_needs == 0:
            return 5.0, f"sets {sa}-{sb}: A has already won"
        if b_needs == 0:
            return -5.0, f"sets {sa}-{sb}: B has already won"

        # Logit adjustment: each set up = roughly +0.7 logit
        set_diff = sa - sb
        adj = set_diff * 0.70

        # Extra boost when one set from match (set point scenario)
        if a_needs == 1 and b_needs > 1:
            adj += 0.30
        elif b_needs == 1 and a_needs > 1:
            adj -= 0.30

        return round(adj, 3), f"sets {sa}-{sb} (best_of {state.best_of}) → logit {adj:+.2f}"

    def _server_adjustment(self, state: TennisState) -> float:
        """Logit adjustment for server identity on this surface."""
        base = self._SERVER_A_ADJ.get(state.surface, 0.10)
        from src.sports.tennis.state import Server
        if state.server == Server.A:
            return base
        elif state.server == Server.B:
            return -base
        return 0.0

    def _tiebreak_adjustment(self, state: TennisState) -> float:
        """
        Logit adjustment for tiebreak position.
        Each tiebreak point of lead ≈ +0.15 logit (uncertain; tiebreaks are volatile).
        """
        pt_diff = state.points_a - state.points_b
        return max(-1.0, min(1.0, pt_diff * 0.15))

    def _pressure_adjustment(
        self, features: TennisFeatureSet, state: TennisState
    ) -> tuple[float, str]:
        """
        Logit adjustments for break point, set point, match point.
        These are small because the next point is highly uncertain.
        """
        from src.sports.tennis.state import Server
        adj = 0.0
        parts = []

        if features.match_point:
            # Who is serving for the match? Server has slight advantage.
            if state.server == Server.A:
                adj += 0.10
                parts.append("match_pt A serving +0.10")
            elif state.server == Server.B:
                adj -= 0.10
                parts.append("match_pt B serving -0.10")

        elif features.set_point and not features.match_point:
            if state.server == Server.A:
                adj += 0.05
                parts.append("set_pt A serving +0.05")
            elif state.server == Server.B:
                adj -= 0.05
                parts.append("set_pt B serving -0.05")

        elif features.break_point:
            # Server at break point — slight negative for server (= A or B)
            if state.server == Server.A:
                adj -= 0.08  # A serving, under break pressure
                parts.append("break_pt vs A-serve -0.08")
            elif state.server == Server.B:
                adj += 0.08
                parts.append("break_pt vs B-serve +0.08")

        reason = "; ".join(parts) if parts else "no_pressure_adj"
        return round(adj, 3), f"pressure: {reason}"

    def _confidence(self, features: TennisFeatureSet, state: TennisState) -> float:
        """
        Model confidence. Lower when:
        - Tiebreak (random-walk territory)
        - Suspended/retired
        - Few sets played (early match)
        - Low market liquidity (market doesn't believe any price)
        """
        base = 0.60
        if state.tiebreak:
            base -= 0.15
        if state.suspended:
            base -= 0.25
        total_sets = state.sets_a + state.sets_b
        if total_sets == 0:
            base -= 0.10  # very early in match
        base += features.liquidity_score * 0.10
        return max(0.10, min(0.90, base))


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _logit_to_prob(logit: float) -> float:
    """Logistic sigmoid: prob = 1 / (1 + exp(-logit))."""
    try:
        return 1.0 / (1.0 + math.exp(-logit))
    except OverflowError:
        return 0.0 if logit < 0 else 1.0
