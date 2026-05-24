from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import uuid


class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class Regime(str, Enum):
    """Market regime classification."""
    TRENDING = "TRENDING"
    MEAN_REVERTING = "MEAN_REVERTING"
    VOLATILE = "VOLATILE"
    ILLIQUID = "ILLIQUID"
    ENDGAME = "ENDGAME"
    UNKNOWN = "UNKNOWN"


@dataclass
class Signal:
    """Output produced by a strategy. Never contains execution logic."""

    strategy_name: str
    market_id: str
    direction: SignalDirection
    confidence: float          # 0.0 – 1.0
    fair_value: float          # estimated fair probability 0–100
    current_price: float       # market mid-price 0–100
    edge: float                # fair_value - current_price (signed)
    regime: Regime = Regime.UNKNOWN
    notes: str = ""
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def is_actionable(self, min_edge: float = 2.0, min_confidence: float = 0.5) -> bool:
        return (
            self.direction != SignalDirection.HOLD
            and abs(self.edge) >= min_edge
            and self.confidence >= min_confidence
        )
