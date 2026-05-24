from __future__ import annotations

"""
Per-strategy attribution: how much PnL, how many trades, win rate, and
average edge each strategy contributed.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class StrategyAttribution:
    strategy_name: str
    trades: int = 0
    realized_pnl: float = 0.0
    wins: int = 0
    losses: int = 0
    edge_sum: float = 0.0

    @property
    def win_rate(self) -> float:
        total = self.wins + self.losses
        return round(self.wins / total, 4) if total else 0.0

    @property
    def avg_edge(self) -> float:
        return round(self.edge_sum / self.trades, 2) if self.trades else 0.0


@dataclass
class StrategyMetrics:
    attributions: Dict[str, StrategyAttribution] = field(default_factory=dict)

    def record(self, strategy: str, realized_pnl: float, edge: float = 0.0) -> None:
        attr = self.attributions.setdefault(strategy, StrategyAttribution(strategy))
        attr.trades += 1
        attr.realized_pnl += realized_pnl
        attr.edge_sum += edge
        if realized_pnl > 0:
            attr.wins += 1
        elif realized_pnl < 0:
            attr.losses += 1

    def ranked(self) -> List[StrategyAttribution]:
        return sorted(self.attributions.values(), key=lambda a: -a.realized_pnl)

    def total_pnl(self) -> float:
        return round(sum(a.realized_pnl for a in self.attributions.values()), 2)
