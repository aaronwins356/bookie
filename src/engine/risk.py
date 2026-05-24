from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple, Dict
from src.models import OrderIntent, OrderStatus


@dataclass
class RiskConfig:
    max_position_per_market: int = 100    # max contracts held in one market
    max_order_size: int = 50
    max_price_cents: float = 90.0        # never buy YES above this
    min_price_cents: float = 10.0        # never buy NO above equivalent
    max_daily_loss: float = 500.0        # dollars
    spread_filter: float = 5.0           # reject if spread > this


@dataclass
class RiskState:
    positions: Dict[str, int] = field(default_factory=dict)   # market_id -> net contracts
    daily_pnl: float = 0.0

    def net_position(self, market_id: str) -> int:
        return self.positions.get(market_id, 0)

    def record_fill(self, market_id: str, size: int, pnl_delta: float = 0.0) -> None:
        self.positions[market_id] = self.net_position(market_id) + size
        self.daily_pnl += pnl_delta


class RiskManager:
    """
    Deterministic gatekeeper. The local brain CANNOT override these rules.
    Returns (approved: bool, reason: str).
    """

    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or RiskConfig()
        self.state = RiskState()

    def evaluate(self, intent: OrderIntent, spread: float = 0.0) -> Tuple[bool, str]:
        c = self.config

        if intent.size > c.max_order_size:
            return False, f"size {intent.size} > max {c.max_order_size}"

        if intent.price > c.max_price_cents:
            return False, f"price {intent.price} > max {c.max_price_cents}"

        if intent.price < c.min_price_cents:
            return False, f"price {intent.price} < min {c.min_price_cents}"

        if spread > c.spread_filter:
            return False, f"spread {spread:.1f} > filter {c.spread_filter}"

        current_pos = self.state.net_position(intent.market_id)
        if abs(current_pos + intent.size) > c.max_position_per_market:
            return False, f"position would exceed {c.max_position_per_market}"

        if self.state.daily_pnl < -c.max_daily_loss:
            return False, f"daily loss limit hit ({self.state.daily_pnl:.2f})"

        return True, "approved"
