from __future__ import annotations

"""
Market discovery — search and list Kalshi markets for data capture.

All calls are read-only. No orders are placed.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MarketInfo:
    ticker: str
    title: str
    status: str
    event_ticker: str
    series_ticker: str
    yes_bid: Optional[float] = None
    yes_ask: Optional[float] = None
    volume: int = 0
    open_interest: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)

    def is_open(self) -> bool:
        return self.status.lower() in ("open", "active")


def search_markets(
    client,
    series_ticker: Optional[str] = None,
    event_ticker: Optional[str] = None,
    ticker: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[MarketInfo]:
    """
    Query the REST API and return a list of MarketInfo objects.
    client must be a KalshiRestClient instance.
    """
    resp = client.get_markets(
        series_ticker=series_ticker,
        event_ticker=event_ticker,
        ticker=ticker,
        status=status,
        limit=limit,
    )
    markets_raw = resp.get("markets", [])
    return [_parse_market(m) for m in markets_raw]


def _parse_market(m: Dict[str, Any]) -> MarketInfo:
    yes_bid = m.get("yes_bid")
    yes_ask = m.get("yes_ask")
    return MarketInfo(
        ticker=m.get("ticker", ""),
        title=m.get("title", ""),
        status=m.get("status", ""),
        event_ticker=m.get("event_ticker", ""),
        series_ticker=m.get("series_ticker", ""),
        yes_bid=float(yes_bid) / 100 if yes_bid is not None else None,
        yes_ask=float(yes_ask) / 100 if yes_ask is not None else None,
        volume=m.get("volume", 0),
        open_interest=m.get("open_interest", 0),
        extra={k: v for k, v in m.items() if k not in (
            "ticker", "title", "status", "event_ticker", "series_ticker",
            "yes_bid", "yes_ask", "volume", "open_interest",
        )},
    )


def format_market_table(markets: List[MarketInfo]) -> str:
    if not markets:
        return "  (no markets found)"
    rows = [
        f"  {'TICKER':<35} {'STATUS':<10} {'YES_BID':>8} {'YES_ASK':>8} {'VOL':>8}",
        "  " + "-" * 75,
    ]
    for m in markets:
        bid = f"{m.yes_bid:.2f}" if m.yes_bid is not None else "   -  "
        ask = f"{m.yes_ask:.2f}" if m.yes_ask is not None else "   -  "
        rows.append(
            f"  {m.ticker:<35} {m.status:<10} {bid:>8} {ask:>8} {m.volume:>8}"
        )
    return "\n".join(rows)
