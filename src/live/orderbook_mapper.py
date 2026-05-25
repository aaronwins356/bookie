from __future__ import annotations

"""
Orderbook mapper: converts Kalshi's bid-only book into internal snapshots.

Kalshi orderbooks provide YES bids and NO bids only (no explicit asks).
The ask side is derived:
  yes_ask = 100 - best_no_bid   (best NO bid implies the implicit YES ask)
  no_ask  = 100 - best_yes_bid  (best YES bid implies the implicit NO ask)

All prices are in cents (0–100).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.data.schemas import CanonicalMarketSnapshot, CanonicalOrderbookSnapshot


@dataclass
class RawKalshiBook:
    """Parsed representation of a Kalshi /orderbook response."""

    ticker: str
    timestamp: str
    yes_bids: List[Tuple[float, int]] = field(default_factory=list)   # (price_cents, size)
    no_bids: List[Tuple[float, int]] = field(default_factory=list)    # (price_cents, size)

    @classmethod
    def from_api_response(cls, ticker: str, timestamp: str, data: Dict[str, Any]) -> "RawKalshiBook":
        """
        Parse a Kalshi /markets/{ticker}/orderbook API response.
        Expected shape: {"orderbook": {"yes": [[price, size], ...], "no": [[price, size], ...]}}
        Prices in the API are in cents (1–99).
        """
        ob = data.get("orderbook", data)
        raw_yes = ob.get("yes", [])
        raw_no = ob.get("no", [])

        def parse_levels(levels) -> List[Tuple[float, int]]:
            out = []
            for entry in levels:
                if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                    out.append((float(entry[0]), int(entry[1])))
            return sorted(out, key=lambda x: -x[0])  # best (highest) bid first

        return cls(
            ticker=ticker,
            timestamp=timestamp,
            yes_bids=parse_levels(raw_yes),
            no_bids=parse_levels(raw_no),
        )


def _best_bid(levels: List[Tuple[float, int]]) -> Optional[float]:
    return levels[0][0] if levels else None


def _total_depth(levels: List[Tuple[float, int]], top_n: int = 5) -> int:
    return sum(size for _, size in levels[:top_n])


class OrderbookMapper:
    """
    Converts a RawKalshiBook into canonical market/orderbook snapshots.

    The derived-ask logic:
      yes_ask = 100 - best_no_bid   (someone willing to pay X for NO means
                                     they'd need 100-X for YES to be neutral)
      no_ask  = 100 - best_yes_bid
    """

    def map_snapshot(
        self,
        book: RawKalshiBook,
        event_id: str = "",
        volume: int = 0,
        open_interest: int = 0,
    ) -> CanonicalMarketSnapshot:
        best_yes_bid = _best_bid(book.yes_bids)
        best_no_bid = _best_bid(book.no_bids)

        # Derived asks
        yes_ask = (100.0 - best_no_bid) if best_no_bid is not None else 100.0
        no_ask = (100.0 - best_yes_bid) if best_yes_bid is not None else 100.0
        yes_bid = best_yes_bid if best_yes_bid is not None else 0.0
        no_bid = best_no_bid if best_no_bid is not None else 0.0

        spread = yes_ask - yes_bid
        depth_yes = _total_depth(book.yes_bids)
        depth_no = _total_depth(book.no_bids)
        liquidity_score = min(1.0, (depth_yes + depth_no) / 200.0)

        return CanonicalMarketSnapshot(
            market_id=book.ticker,
            event_id=event_id or book.ticker,
            timestamp=book.timestamp,
            yes_bid=yes_bid,
            yes_ask=yes_ask,
            no_bid=no_bid,
            no_ask=no_ask,
            last_price=None,
            volume=volume,
            open_interest=open_interest,
            liquidity_score=liquidity_score,
            source="kalshi_live",
        )

    def map_orderbook(self, book: RawKalshiBook) -> CanonicalOrderbookSnapshot:
        best_yes_bid = _best_bid(book.yes_bids)
        best_no_bid = _best_bid(book.no_bids)

        # Derive ask levels from the opposite side's bid levels
        yes_asks: List[Tuple[float, int]] = [
            (100.0 - p, s) for p, s in reversed(book.no_bids)
        ]
        no_asks: List[Tuple[float, int]] = [
            (100.0 - p, s) for p, s in reversed(book.yes_bids)
        ]

        depth_score = min(
            1.0,
            (_total_depth(book.yes_bids) + _total_depth(book.no_bids)) / 100.0,
        )

        return CanonicalOrderbookSnapshot(
            market_id=book.ticker,
            timestamp=book.timestamp,
            yes_bids=book.yes_bids,
            yes_asks=yes_asks,
            no_bids=book.no_bids,
            no_asks=no_asks,
            depth_score=depth_score,
        )
