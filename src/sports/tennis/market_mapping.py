from __future__ import annotations

"""
Kalshi tennis market discovery helpers.

Maps Kalshi series tickers to tennis tournaments/tours and provides
sport-level filtering so the CLI can do:

    list-markets --sport tennis --status open
    list-markets --query "Wimbledon" --status open

Kalshi uses series tickers like:
  KXATP, KXWTA, KXATP-WIM, KXWTA-USO ...

The exact tickers are not authoritative — they change when Kalshi adds
new events. Use the string patterns below as hints, not gospel.

IMPORTANT: This module never submits orders. It only maps market labels.
"""

from dataclasses import dataclass
from typing import List, Optional

from src.sports.tennis.state import Tour


# ------------------------------------------------------------------ #
# Known Kalshi series patterns for tennis
# ------------------------------------------------------------------ #

TENNIS_SERIES_PREFIXES: List[str] = [
    "KXATP",      # ATP match-winner markets
    "KXWTA",      # WTA match-winner markets
    "KXTEN",      # generic tennis ticker prefix Kalshi sometimes uses
]

TENNIS_KEYWORDS: List[str] = [
    "tennis",
    "atp",
    "wta",
    "wimbledon",
    "us open",
    "french open",
    "roland garros",
    "australian open",
    "depalmeiro",    # common Kalshi mangled title fragment
]

GRAND_SLAM_SLUGS = {
    "AO": "Australian Open",
    "RG": "Roland Garros",
    "WIM": "Wimbledon",
    "USO": "US Open",
}


# ------------------------------------------------------------------ #
# Tour inference from ticker
# ------------------------------------------------------------------ #

def infer_tour(series_ticker: str) -> Tour:
    """Best-effort Tour from a Kalshi series ticker string."""
    t = series_ticker.upper()
    if "WTA" in t:
        return Tour.WTA
    if "ATP" in t:
        return Tour.ATP
    return Tour.UNKNOWN


# ------------------------------------------------------------------ #
# Sport / query filtering
# ------------------------------------------------------------------ #

def is_tennis_market(title: str, series_ticker: str) -> bool:
    """
    Heuristic: return True if this Kalshi market is likely a tennis market.

    Checks both the series ticker prefix and keywords in the title.
    """
    series_upper = series_ticker.upper()
    for prefix in TENNIS_SERIES_PREFIXES:
        if series_upper.startswith(prefix):
            return True

    title_lower = title.lower()
    for kw in TENNIS_KEYWORDS:
        if kw in title_lower:
            return True

    return False


def market_matches_query(title: str, series_ticker: str, event_ticker: str, query: str) -> bool:
    """
    Case-insensitive substring match across title, series ticker, and event ticker.
    Used for --query filtering in list-markets CLI.
    """
    q = query.lower()
    return (
        q in title.lower()
        or q in series_ticker.lower()
        or q in event_ticker.lower()
    )


# ------------------------------------------------------------------ #
# Structured market info
# ------------------------------------------------------------------ #

@dataclass
class TennisMarketInfo:
    """
    A Kalshi market identified as a tennis market.

    Wraps the generic MarketInfo from market_discovery.py with
    tennis-specific inferred fields.
    """
    ticker: str
    series_ticker: str
    event_ticker: str
    title: str
    status: str
    yes_bid: Optional[float]
    yes_ask: Optional[float]
    volume: int
    tour: Tour

    @property
    def mid(self) -> Optional[float]:
        if self.yes_bid is not None and self.yes_ask is not None:
            return (self.yes_bid + self.yes_ask) / 2.0
        return None

    def __str__(self) -> str:
        mid_str = f"{self.mid:.1f}¢" if self.mid is not None else "—"
        return (
            f"[{self.tour.value:12s}] {self.ticker:<36} "
            f"{self.status:<8} mid={mid_str:>7} vol={self.volume:>6}  {self.title}"
        )


def to_tennis_market_info(raw: "MarketInfo") -> TennisMarketInfo:  # type: ignore[name-defined]
    """Convert a generic MarketInfo to TennisMarketInfo."""
    return TennisMarketInfo(
        ticker=raw.ticker,
        series_ticker=raw.series_ticker,
        event_ticker=raw.event_ticker,
        title=raw.title,
        status=raw.status,
        yes_bid=raw.yes_bid,
        yes_ask=raw.yes_ask,
        volume=raw.volume,
        tour=infer_tour(raw.series_ticker),
    )


def filter_tennis(markets: list, query: Optional[str] = None) -> List[TennisMarketInfo]:
    """
    From a list of generic MarketInfo objects, keep only tennis markets
    (and optionally filter by query string).
    """
    results: List[TennisMarketInfo] = []
    for m in markets:
        if not is_tennis_market(m.title, m.series_ticker):
            continue
        if query and not market_matches_query(m.title, m.series_ticker, m.event_ticker, query):
            continue
        results.append(to_tennis_market_info(m))
    return results
