from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import uuid


class OrderSide(str, Enum):
    YES = "YES"
    NO = "NO"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    VETOED = "VETOED"


@dataclass
class OrderIntent:
    """Router output: intent to place an order. Not yet executed."""

    market_id: str
    side: OrderSide
    price: float          # limit price cents (0–100)
    size: int             # number of contracts
    strategy_name: str
    signal_id: str
    intent_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    notes: str = ""


@dataclass
class ExecutionResult:
    """Adapter output after attempting to fill an OrderIntent."""

    intent_id: str
    market_id: str
    status: OrderStatus
    filled_price: Optional[float] = None
    filled_size: Optional[int] = None
    fee: float = 0.0
    message: str = ""
