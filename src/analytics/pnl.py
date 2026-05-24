from __future__ import annotations

"""
PnL tracking. Maintains per-market positions and realized/unrealized PnL.

Convention: all prices in cents (0-100). A filled contract on side YES at
price p costs p cents and pays 100 at YES resolution. We track average
cost and realize PnL on offsetting fills. Unrealized PnL is marked to the
current mid.
"""

from dataclasses import dataclass, field
from typing import Dict, List
from src.models import OrderSide, ExecutionResult


@dataclass
class Trade:
    market_id: str
    strategy_name: str
    side: OrderSide
    price: float
    size: int
    fee: float = 0.0


@dataclass
class Position:
    market_id: str
    net_contracts: int = 0      # signed: + = long YES, - = long NO (short YES)
    avg_cost: float = 0.0       # average YES-equivalent entry price (cents)
    realized_pnl: float = 0.0   # cents

    def mark(self, mid: float) -> float:
        """Unrealized PnL in cents at the given mid price."""
        return self.net_contracts * (mid - self.avg_cost)


class PnLTracker:
    def __init__(self) -> None:
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.realized_total: float = 0.0
        self.fees_total: float = 0.0
        self.slippage_loss: float = 0.0

    def record(self, trade: Trade, requested_price: float | None = None) -> None:
        self.trades.append(trade)
        self.fees_total += trade.fee

        # YES-equivalent signed size and price.
        signed = trade.size if trade.side == OrderSide.YES else -trade.size
        yes_price = trade.price if trade.side == OrderSide.YES else 100.0 - trade.price

        if requested_price is not None:
            req_yes = requested_price if trade.side == OrderSide.YES else 100.0 - requested_price
            self.slippage_loss += abs(yes_price - req_yes) * trade.size

        pos = self.positions.setdefault(trade.market_id, Position(trade.market_id))
        self._apply(pos, signed, yes_price)

    def _apply(self, pos: Position, signed: int, price: float) -> None:
        prev = pos.net_contracts
        new = prev + signed

        if prev == 0 or (prev > 0) == (signed > 0):
            # opening or increasing in same direction → re-average
            total_cost = pos.avg_cost * abs(prev) + price * abs(signed)
            pos.avg_cost = total_cost / max(1, abs(new)) if new != 0 else 0.0
        else:
            # reducing / closing → realize PnL on the closed quantity
            closed = min(abs(prev), abs(signed))
            direction = 1 if prev > 0 else -1
            realized = direction * closed * (price - pos.avg_cost)
            pos.realized_pnl += realized
            self.realized_total += realized
            if new == 0:
                pos.avg_cost = 0.0
            elif (new > 0) != (prev > 0):
                # flipped direction → remaining opens at this price
                pos.avg_cost = price

        pos.net_contracts = new

    def unrealized(self, marks: Dict[str, float]) -> float:
        return sum(p.mark(marks.get(p.market_id, p.avg_cost)) for p in self.positions.values())

    def total_pnl(self, marks: Dict[str, float]) -> float:
        return self.realized_total + self.unrealized(marks) - self.fees_total

    def equity_curve_point(self, marks: Dict[str, float]) -> float:
        return self.total_pnl(marks)
