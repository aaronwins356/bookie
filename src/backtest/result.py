from __future__ import annotations

"""
Backtest result models. Pure data + JSON ser/de - no computation here beyond
trivial helpers. Computation lives in the runner / leaderboard / significance
modules so these stay easy to serialize and inspect.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from src.backtest.config import BacktestConfig


@dataclass
class PnLSummary:
    total_pnl_cents: float = 0.0
    realized_pnl_cents: float = 0.0
    unrealized_pnl_cents: float = 0.0
    fees_cents: float = 0.0
    slippage_loss_cents: float = 0.0
    sharpe_like: float = 0.0
    return_on_bankroll_pct: float = 0.0


@dataclass
class DrawdownSummary:
    max_drawdown_cents: float = 0.0
    max_drawdown_pct: float = 0.0


@dataclass
class StrategyMetric:
    strategy_name: str
    trades: int = 0
    fills: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl_cents: float = 0.0
    edge_sum: float = 0.0
    slippage_loss_cents: float = 0.0
    regime_pnl: Dict[str, float] = field(default_factory=dict)

    @property
    def win_rate(self) -> float:
        n = self.wins + self.losses
        return round(self.wins / n, 4) if n else 0.0

    @property
    def avg_pnl_cents(self) -> float:
        return round(self.total_pnl_cents / self.fills, 3) if self.fills else 0.0

    @property
    def avg_edge(self) -> float:
        return round(self.edge_sum / self.trades, 3) if self.trades else 0.0

    @property
    def ev_capture(self) -> float:
        return round(self.total_pnl_cents / self.edge_sum, 3) if self.edge_sum else 0.0


@dataclass
class RegimeMetric:
    regime: str
    ticks: int = 0
    fills: int = 0
    pnl_cents: float = 0.0


@dataclass
class RiskEvent:
    tick: int
    code: str          # e.g. "VETO"
    reason: str
    strategy: str = ""


@dataclass
class BacktestResult:
    config: BacktestConfig
    started_at: str
    completed_at: str
    ticks_processed: int = 0
    trades: int = 0
    fills: int = 0
    rejected_orders: int = 0
    pnl_summary: PnLSummary = field(default_factory=PnLSummary)
    drawdown_summary: DrawdownSummary = field(default_factory=DrawdownSummary)
    strategy_metrics: List[StrategyMetric] = field(default_factory=list)
    regime_metrics: List[RegimeMetric] = field(default_factory=list)
    risk_events: List[RiskEvent] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    artifacts: Dict[str, str] = field(default_factory=dict)
    # Raw per-fill PnL series, used by significance tooling. Kept compact.
    fill_pnls: List[float] = field(default_factory=list)
    data_verdict: str = "UNKNOWN"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": self.config.to_dict(),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "ticks_processed": self.ticks_processed,
            "trades": self.trades,
            "fills": self.fills,
            "rejected_orders": self.rejected_orders,
            "pnl_summary": asdict(self.pnl_summary),
            "drawdown_summary": asdict(self.drawdown_summary),
            "strategy_metrics": [
                {**asdict(m), "win_rate": m.win_rate, "avg_pnl_cents": m.avg_pnl_cents,
                 "avg_edge": m.avg_edge, "ev_capture": m.ev_capture}
                for m in self.strategy_metrics
            ],
            "regime_metrics": [asdict(r) for r in self.regime_metrics],
            "risk_events": [asdict(e) for e in self.risk_events],
            "warnings": self.warnings,
            "artifacts": self.artifacts,
            "fill_pnls": [round(x, 4) for x in self.fill_pnls],
            "data_verdict": self.data_verdict,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BacktestResult":
        sm = []
        for m in d.get("strategy_metrics", []):
            sm.append(StrategyMetric(
                strategy_name=m["strategy_name"], trades=m.get("trades", 0),
                fills=m.get("fills", 0), wins=m.get("wins", 0), losses=m.get("losses", 0),
                total_pnl_cents=m.get("total_pnl_cents", 0.0), edge_sum=m.get("edge_sum", 0.0),
                slippage_loss_cents=m.get("slippage_loss_cents", 0.0),
                regime_pnl=m.get("regime_pnl", {}),
            ))
        return cls(
            config=BacktestConfig.from_dict(d["config"]),
            started_at=d["started_at"], completed_at=d["completed_at"],
            ticks_processed=d.get("ticks_processed", 0), trades=d.get("trades", 0),
            fills=d.get("fills", 0), rejected_orders=d.get("rejected_orders", 0),
            pnl_summary=PnLSummary(**d.get("pnl_summary", {})),
            drawdown_summary=DrawdownSummary(**d.get("drawdown_summary", {})),
            strategy_metrics=sm,
            regime_metrics=[RegimeMetric(**r) for r in d.get("regime_metrics", [])],
            risk_events=[RiskEvent(**e) for e in d.get("risk_events", [])],
            warnings=d.get("warnings", []), artifacts=d.get("artifacts", {}),
            fill_pnls=d.get("fill_pnls", []), data_verdict=d.get("data_verdict", "UNKNOWN"),
        )


@dataclass
class StrategyLeaderboardRow:
    strategy_name: str
    trades: int = 0
    fills: int = 0
    win_rate: float = 0.0
    total_pnl_cents: float = 0.0
    avg_pnl_cents: float = 0.0
    max_drawdown_cents: float = 0.0
    sharpe_like: float = 0.0
    expectancy: float = 0.0
    ev_capture: float = 0.0
    slippage_loss: float = 0.0
    regime_strengths: List[str] = field(default_factory=list)
    regime_weaknesses: List[str] = field(default_factory=list)
    robustness_score: float = 0.0
    warning_flags: List[str] = field(default_factory=list)
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StrategyLeaderboardRow":
        known = {k: d[k] for k in cls.__dataclass_fields__ if k in d}
        return cls(**known)  # type: ignore[arg-type]


@dataclass
class BatchBacktestResult:
    batch_id: str
    configs: List[BacktestConfig] = field(default_factory=list)
    results: List[BacktestResult] = field(default_factory=list)
    aggregate_metrics: Dict[str, Any] = field(default_factory=dict)
    leaderboard: List[StrategyLeaderboardRow] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "configs": [c.to_dict() for c in self.configs],
            "results": [r.to_dict() for r in self.results],
            "aggregate_metrics": self.aggregate_metrics,
            "leaderboard": [row.to_dict() for row in self.leaderboard],
            "warnings": self.warnings,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BatchBacktestResult":
        return cls(
            batch_id=d["batch_id"],
            configs=[BacktestConfig.from_dict(c) for c in d.get("configs", [])],
            results=[BacktestResult.from_dict(r) for r in d.get("results", [])],
            aggregate_metrics=d.get("aggregate_metrics", {}),
            leaderboard=[StrategyLeaderboardRow.from_dict(x) for x in d.get("leaderboard", [])],
            warnings=d.get("warnings", []),
        )
