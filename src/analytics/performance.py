from __future__ import annotations

"""
Top-level performance report. Aggregates PnL, drawdown, expectancy, and a
Sharpe-like ratio over a return series. Pure functions over recorded data.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List

from src.analytics.drawdown import DrawdownTracker
from src.analytics.expectancy import ExpectancyCalculator
from src.analytics.strategy_metrics import StrategyMetrics


@dataclass
class PerformanceReport:
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    fees: float
    slippage_loss: float
    win_rate: float
    expectancy: float
    sharpe_like: float
    max_drawdown: float
    max_drawdown_pct: float
    n_trades: int
    regime_pnl: Dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, object]:
        return self.__dict__


class PerformanceAnalyzer:
    """Collects per-tick returns and produces a PerformanceReport."""

    def __init__(self) -> None:
        self.returns: List[float] = []
        self.drawdown = DrawdownTracker()
        self.expectancy = ExpectancyCalculator()
        self.strategy_metrics = StrategyMetrics()
        self.regime_pnl: Dict[str, float] = {}

    def record_equity(self, equity: float) -> None:
        if self.returns:
            self.returns.append(equity - self._last_equity)
        else:
            self.returns.append(0.0)
        self._last_equity = equity
        self.drawdown.update(equity)

    _last_equity: float = 0.0

    def record_regime_pnl(self, regime: str, pnl_delta: float) -> None:
        self.regime_pnl[regime] = self.regime_pnl.get(regime, 0.0) + pnl_delta

    def sharpe_like(self) -> float:
        rets = [r for r in self.returns if r != 0.0]
        if len(rets) < 2:
            return 0.0
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        sd = math.sqrt(var)
        if sd == 0:
            return 0.0
        return round(mean / sd * math.sqrt(len(rets)), 3)

    def build_report(
        self,
        realized: float,
        unrealized: float,
        fees: float,
        slippage_loss: float,
        n_trades: int,
    ) -> PerformanceReport:
        return PerformanceReport(
            total_pnl=round(realized + unrealized - fees, 2),
            realized_pnl=round(realized, 2),
            unrealized_pnl=round(unrealized, 2),
            fees=round(fees, 2),
            slippage_loss=round(slippage_loss, 2),
            win_rate=self.expectancy.win_rate(),
            expectancy=self.expectancy.expectancy(),
            sharpe_like=self.sharpe_like(),
            max_drawdown=round(self.drawdown.max_drawdown, 2),
            max_drawdown_pct=self.drawdown.max_drawdown_pct(),
            n_trades=n_trades,
            regime_pnl={k: round(v, 2) for k, v in self.regime_pnl.items()},
        )
