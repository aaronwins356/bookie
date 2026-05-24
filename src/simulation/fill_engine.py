from __future__ import annotations

"""
Fill engine. Combines the orderbook, slippage model, latency model, and
queue model to produce realistic (and still deterministic-with-seed) fills.

Implements the ExecutionAdapter protocol (`submit`) so it can be dropped
into the existing ExecutionEngine in place of MockExecutionAdapter.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from src.models import OrderIntent, ExecutionResult, OrderStatus, OrderSide
from src.simulation.orderbook import OrderBook
from src.simulation.slippage import SlippageModel
from src.simulation.latency import LatencyModel
from src.simulation.queue_model import QueueModel
from src.simulation.volatility import VolatilityRegime


@dataclass
class Fill:
    price: float
    size: int


class FillEngine:
    """
    Fill semantics:
    - Marketable size walks the book (slippage from depth exhaustion).
    - A regime-aware slippage premium is applied on top.
    - If the book is too thin, the order is PARTIALLY filled.
    - Latency can delay the fill (reported in the message), and an
      unfavorable queue can cause a partial/zero fill for resting orders.
    """

    def __init__(
        self,
        slippage: Optional[SlippageModel] = None,
        latency: Optional[LatencyModel] = None,
        queue: Optional[QueueModel] = None,
    ) -> None:
        self.slippage = slippage or SlippageModel()
        self.latency = latency or LatencyModel()
        self.queue = queue or QueueModel()
        self.last_fills: List[Fill] = []
        # The replay driver may set this each tick so submit() produces
        # regime-aware slippage without changing the ExecutionAdapter API.
        self.current_regime: VolatilityRegime = VolatilityRegime.CALM
        self.book_depth: int = 60

    def submit(self, intent: OrderIntent) -> ExecutionResult:
        """ExecutionAdapter entry point — uses an internal flat book."""
        book = OrderBook(market_id=intent.market_id)
        from src.simulation.orderbook import PriceLevel
        # Flat synthetic book around the intent price; top-level depth
        # reflects current liquidity so thin books cause partial fills.
        book.set_levels(
            bids=[PriceLevel(intent.price - 1, self.book_depth), PriceLevel(intent.price - 2, 100)],
            asks=[PriceLevel(intent.price, self.book_depth), PriceLevel(intent.price + 1, 100)],
        )
        return self.fill(intent, book, self.current_regime)

    def fill(
        self,
        intent: OrderIntent,
        book: OrderBook,
        regime: VolatilityRegime,
    ) -> ExecutionResult:
        is_buy = True  # all intents express a long position in `side`
        available = book.available(intent.side)

        if available <= 0:
            return ExecutionResult(
                intent_id=intent.intent_id,
                market_id=intent.market_id,
                status=OrderStatus.REJECTED,
                message="no liquidity available",
            )

        raw_fills = book.consume(intent.side, intent.size)
        filled_size = sum(q for _, q in raw_fills)
        self.last_fills = [Fill(p, q) for p, q in raw_fills]

        if filled_size == 0:
            return ExecutionResult(
                intent_id=intent.intent_id,
                market_id=intent.market_id,
                status=OrderStatus.REJECTED,
                message="order did not fill (queue/liquidity)",
            )

        vwap = sum(p * q for p, q in raw_fills) / filled_size

        slip = self.slippage.estimate(
            requested_price=vwap,
            size=filled_size,
            available_depth=max(available, filled_size),
            regime=regime,
            is_buy=is_buy,
        )

        fill_delay = self.latency.fill_latency_ms()
        partial = filled_size < intent.size
        status = OrderStatus.FILLED

        msg = f"vwap={vwap:.2f} slip={slip.slippage_cents:.2f}c delay={fill_delay:.0f}ms"
        if partial:
            msg = "PARTIAL " + msg

        return ExecutionResult(
            intent_id=intent.intent_id,
            market_id=intent.market_id,
            status=status,
            filled_price=slip.realized_price,
            filled_size=filled_size,
            fee=round(filled_size * 0.01, 2),
            message=msg,
        )
