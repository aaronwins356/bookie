from __future__ import annotations

"""
Correlation analysis between strategy return streams. Used by the router
to avoid stacking correlated exposure.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import math


@dataclass
class CorrelationAnalyzer:
    returns: Dict[str, List[float]] = field(default_factory=dict)

    def record(self, strategy: str, ret: float) -> None:
        self.returns.setdefault(strategy, []).append(ret)

    def pearson(self, a: str, b: str) -> float:
        xs = self.returns.get(a, [])
        ys = self.returns.get(b, [])
        n = min(len(xs), len(ys))
        if n < 2:
            return 0.0
        xs, ys = xs[:n], ys[:n]
        mx = sum(xs) / n
        my = sum(ys) / n
        cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        vx = sum((x - mx) ** 2 for x in xs)
        vy = sum((y - my) ** 2 for y in ys)
        denom = math.sqrt(vx * vy)
        if denom == 0:
            return 0.0
        return round(cov / denom, 3)

    def matrix(self) -> Dict[Tuple[str, str], float]:
        names = list(self.returns.keys())
        out: Dict[Tuple[str, str], float] = {}
        for i, a in enumerate(names):
            for b in names[i:]:
                out[(a, b)] = self.pearson(a, b)
        return out

    def most_correlated(self, threshold: float = 0.7) -> List[Tuple[str, str, float]]:
        pairs = []
        for (a, b), c in self.matrix().items():
            if a != b and abs(c) >= threshold:
                pairs.append((a, b, c))
        return sorted(pairs, key=lambda t: -abs(t[2]))
