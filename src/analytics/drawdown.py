from __future__ import annotations

"""Max-drawdown tracking over an equity curve."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class DrawdownTracker:
    peak: float = float("-inf")
    max_drawdown: float = 0.0          # largest peak-to-trough drop (positive)
    current_drawdown: float = 0.0
    equity_curve: List[float] = field(default_factory=list)

    def update(self, equity: float) -> float:
        self.equity_curve.append(equity)
        if equity > self.peak:
            self.peak = equity
        self.current_drawdown = self.peak - equity
        if self.current_drawdown > self.max_drawdown:
            self.max_drawdown = self.current_drawdown
        return self.current_drawdown

    def max_drawdown_pct(self) -> float:
        if self.peak <= 0:
            return 0.0
        return round(100.0 * self.max_drawdown / self.peak, 2)
