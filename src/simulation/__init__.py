"""
Market microstructure simulation layer.

Depends only on `src.models`. Provides a realistic, deterministic-with-seed
simulation of prediction-market behavior: orderbooks, liquidity, slippage,
latency, volatility, spreads, fills, queue dynamics, and random events.
"""

from .market_regime import MarketRegime, RegimeInputs, RegimeClassifier
from .orderbook import PriceLevel, OrderBook
from .liquidity import LiquidityEngine, LiquidityProfile
from .slippage import SlippageModel, SlippageResult
from .latency import LatencyModel
from .volatility import VolatilityEngine, VolatilityRegime
from .spread_engine import SpreadEngine
from .fill_engine import FillEngine, Fill
from .queue_model import QueueModel
from .event_engine import EventEngine, MarketEvent, EventType

__all__ = [
    "MarketRegime", "RegimeInputs", "RegimeClassifier",
    "PriceLevel", "OrderBook",
    "LiquidityEngine", "LiquidityProfile",
    "SlippageModel", "SlippageResult",
    "LatencyModel",
    "VolatilityEngine", "VolatilityRegime",
    "SpreadEngine",
    "FillEngine", "Fill",
    "QueueModel",
    "EventEngine", "MarketEvent", "EventType",
]
