from __future__ import annotations

import math
from src.engine.features import FeatureSet
from src.models import GamePhase


class FairValueModel:
    """
    Deterministic fair-value estimator.

    Uses a simple logistic model driven by score differential and time pressure.
    No ML weights — entirely rule-based so it is reproducible and auditable.
    """

    def estimate(self, features: FeatureSet) -> float:
        """Return estimated fair probability for YES (home-team win) 0–100."""
        base = self._score_diff_to_prob(features.score_diff)
        adjusted = self._apply_time_pressure(base, features.time_pressure)
        return round(max(1.0, min(99.0, adjusted * 100.0)), 2)

    def _score_diff_to_prob(self, diff: int) -> float:
        """Sigmoid: each point ~12% logit shift."""
        return 1.0 / (1.0 + math.exp(-0.12 * diff))

    def _apply_time_pressure(self, prob: float, time_pressure: float) -> float:
        """Pull probability toward extremes as time runs out. Tie stays at 0.5."""
        if prob > 0.5:
            return prob + (1.0 - prob) * time_pressure * 0.4
        elif prob < 0.5:
            return prob - prob * time_pressure * 0.4
        else:
            return prob
