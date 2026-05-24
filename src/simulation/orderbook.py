from __future__ import annotations

"""
Simulated limit orderbook for a binary (YES/NO) prediction-market contract.

The YES book is the source of truth. The NO book is derived by the identity
    NO_price = 100 - YES_price
so a YES bid at p is equivalent to a NO ask at (100 - p), and vice versa.
This keeps the two sides arbitrage-consistent without double bookkeeping.
"""

from dataclasses import dataclass, field
from typing import List, Tuple
from src.models import OrderSide


@dataclass
class PriceLevel:
    price: float   # cents
    size: int      # contracts resting at this level


@dataclass
class OrderBook:
    market_id: str
    yes_bids: List[PriceLevel] = field(default_factory=list)  # descending price
    yes_asks: List[PriceLevel] = field(default_factory=list)  # ascending price

    # ---- top of book -------------------------------------------------
    @property
    def best_bid(self) -> float:
        return self.yes_bids[0].price if self.yes_bids else 0.0

    @property
    def best_ask(self) -> float:
        return self.yes_asks[0].price if self.yes_asks else 100.0

    @property
    def mid(self) -> float:
        return (self.best_bid + self.best_ask) / 2.0

    @property
    def spread(self) -> float:
        return self.best_ask - self.best_bid

    # ---- depth -------------------------------------------------------
    def depth(self, side: OrderSide, levels: int = 5) -> int:
        """Total resting contracts across the top `levels` on a side."""
        book = self._book_for(side)
        return sum(lvl.size for lvl in book[:levels])

    def total_depth(self, levels: int = 5) -> int:
        return self.depth(OrderSide.YES, levels) + self._ask_depth(levels)

    def _ask_depth(self, levels: int) -> int:
        return sum(lvl.size for lvl in self.yes_asks[:levels])

    def _book_for(self, side: OrderSide) -> List[PriceLevel]:
        # Buying YES consumes asks; buying NO consumes YES bids (equiv).
        return self.yes_asks if side == OrderSide.YES else self.yes_bids

    # ---- mutation ----------------------------------------------------
    def set_levels(self, bids: List[PriceLevel], asks: List[PriceLevel]) -> None:
        self.yes_bids = sorted(bids, key=lambda l: -l.price)
        self.yes_asks = sorted(asks, key=lambda l: l.price)

    def consume(self, side: OrderSide, size: int) -> List[Tuple[float, int]]:
        """
        Walk the book filling `size` contracts. Returns a list of
        (price, qty) fills. Mutates the book (liquidity exhaustion).
        For YES buys we walk asks ascending; for NO buys we walk YES bids
        descending and report the NO-equivalent price (100 - yes_price).
        """
        fills: List[Tuple[float, int]] = []
        remaining = size

        if side == OrderSide.YES:
            book = self.yes_asks
            for lvl in book:
                if remaining <= 0:
                    break
                take = min(lvl.size, remaining)
                fills.append((lvl.price, take))
                lvl.size -= take
                remaining -= take
            self.yes_asks = [l for l in book if l.size > 0]
        else:
            book = self.yes_bids
            for lvl in book:
                if remaining <= 0:
                    break
                take = min(lvl.size, remaining)
                fills.append((round(100.0 - lvl.price, 1), take))
                lvl.size -= take
                remaining -= take
            self.yes_bids = [l for l in book if l.size > 0]

        return fills

    def available(self, side: OrderSide) -> int:
        book = self._book_for(side)
        return sum(l.size for l in book)
