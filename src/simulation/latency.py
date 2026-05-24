from __future__ import annotations

"""
Latency model. Simulates the delay between the true market state and what
the engine observes / can act on. Used to produce stale snapshots and
delayed fills. Deterministic given a seed.
"""

import random
from dataclasses import dataclass


@dataclass
class LatencyModel:
    base_ms: float = 80.0
    jitter_ms: float = 40.0
    seed: int = 11

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def quote_latency_ms(self) -> float:
        """Delay before a fresh quote becomes visible."""
        return max(0.0, self.base_ms + self._rng.gauss(0.0, self.jitter_ms))

    def fill_latency_ms(self) -> float:
        """Delay before an order reaches the book and fills."""
        return max(0.0, self.base_ms * 1.5 + self._rng.gauss(0.0, self.jitter_ms))

    def is_snapshot_stale(self, age_ms: float) -> bool:
        """A snapshot is stale if older than the current quote latency."""
        return age_ms > self.quote_latency_ms()

    def staleness_ticks(self, tick_ms: float = 1000.0) -> int:
        """How many ticks of staleness the current latency implies."""
        return int(self.quote_latency_ms() // max(1.0, tick_ms))
