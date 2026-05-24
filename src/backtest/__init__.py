"""
Phase 4: rigorous backtesting + evaluation harness.

Runs replay bundles and built-in scenarios, aggregates per-strategy and
per-regime performance, scores robustness, raises conservative fake-edge
warnings, and produces honest leaderboards + research reports.

Philosophy: the goal is not to make strategies look good - it is to find
out which are real candidates, which are artifacts, and which are too
fragile. Bad results are useful. Fake edge must be exposed early.
"""

from src.backtest.config import BacktestConfig
from src.backtest.result import (
    BacktestResult, BatchBacktestResult, StrategyLeaderboardRow,
    PnLSummary, DrawdownSummary, StrategyMetric, RegimeMetric, RiskEvent,
)
from src.backtest.runner import BacktestRunner, run_config
from src.backtest.batch import BatchRunner, export_batch
from src.backtest.leaderboard import build_leaderboard
from src.backtest import significance, robustness, splits, report

__all__ = [
    "BacktestConfig",
    "BacktestResult", "BatchBacktestResult", "StrategyLeaderboardRow",
    "PnLSummary", "DrawdownSummary", "StrategyMetric", "RegimeMetric", "RiskEvent",
    "BacktestRunner", "run_config",
    "BatchRunner", "export_batch",
    "build_leaderboard",
    "significance", "robustness", "splits", "report",
]
