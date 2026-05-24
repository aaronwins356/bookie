from __future__ import annotations

"""
Expectancy & EV-capture analytics.

Expectancy per trade = (win_rate * avg_win) - (loss_rate * avg_loss).
EV capture compares realized PnL against the edge the strategies claimed
at signal time.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class ExpectancyCalculator:
    realized_pnls: List[float] = field(default_factory=list)
    claimed_edges: List[float] = field(default_factory=list)

    def record(self, realized_pnl: float, claimed_edge: float = 0.0) -> None:
        self.realized_pnls.append(realized_pnl)
        self.claimed_edges.append(claimed_edge)

    def win_rate(self) -> float:
        if not self.realized_pnls:
            return 0.0
        wins = sum(1 for p in self.realized_pnls if p > 0)
        return round(wins / len(self.realized_pnls), 4)

    def avg_win(self) -> float:
        wins = [p for p in self.realized_pnls if p > 0]
        return round(sum(wins) / len(wins), 2) if wins else 0.0

    def avg_loss(self) -> float:
        losses = [abs(p) for p in self.realized_pnls if p < 0]
        return round(sum(losses) / len(losses), 2) if losses else 0.0

    def expectancy(self) -> float:
        if not self.realized_pnls:
            return 0.0
        wr = self.win_rate()
        return round(wr * self.avg_win() - (1.0 - wr) * self.avg_loss(), 2)

    def ev_capture_ratio(self) -> float:
        """Realized PnL / total claimed edge. >1 means we beat our own model."""
        total_claimed = sum(self.claimed_edges)
        if total_claimed == 0:
            return 0.0
        return round(sum(self.realized_pnls) / total_claimed, 3)
