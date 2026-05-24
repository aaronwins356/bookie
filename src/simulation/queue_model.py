from __future__ import annotations

"""
Queue model. Estimates a resting order's position in the FIFO queue at a
price level and the probability it gets filled before the level clears.
"""

import random
from dataclasses import dataclass


@dataclass
class QueuePosition:
    ahead: int          # contracts ahead of us in queue
    level_size: int     # total resting at the level
    fill_probability: float


class QueueModel:
    def __init__(self, seed: int = 23) -> None:
        self._rng = random.Random(seed)

    def position(self, level_size: int, our_size: int) -> QueuePosition:
        """We join the back of the queue at a level of `level_size`."""
        ahead = level_size
        # Probability the queue in front of us clears scales with how much
        # flow typically trades through a level vs. how deep we are.
        if ahead <= 0:
            prob = 1.0
        else:
            prob = max(0.0, min(1.0, 1.0 / (1.0 + ahead / max(1, our_size * 4))))
        return QueuePosition(ahead=ahead, level_size=level_size + our_size, fill_probability=round(prob, 3))

    def did_fill(self, qp: QueuePosition) -> bool:
        """Stochastic fill given queue position (deterministic with seed)."""
        return self._rng.random() < qp.fill_probability
