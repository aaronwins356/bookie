"""
Analytics layer. Pure, deterministic computations over trade/fill/PnL
records. Depends only on `src.models` and plain data. No simulation or
engine imports, so it can be reused for live trading later.
"""

from .pnl import PnLTracker, Position, Trade
from .drawdown import DrawdownTracker
from .exposure import ExposureTracker
from .expectancy import ExpectancyCalculator
from .correlation import CorrelationAnalyzer
from .strategy_metrics import StrategyMetrics, StrategyAttribution
from .performance import PerformanceReport, PerformanceAnalyzer

__all__ = [
    "PnLTracker", "Position", "Trade",
    "DrawdownTracker",
    "ExposureTracker",
    "ExpectancyCalculator",
    "CorrelationAnalyzer",
    "StrategyMetrics", "StrategyAttribution",
    "PerformanceReport", "PerformanceAnalyzer",
]
