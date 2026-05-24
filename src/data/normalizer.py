from __future__ import annotations

"""
Normalizer. Converts messy raw dict rows (varied field names / casings)
into canonical models. Field-name resolution is alias-driven and
case-insensitive; missing derived fields (NO side, liquidity score) are
computed from what is present.

The normalizer is intentionally lenient about *names* but strict about
*structure*: anything it cannot place is left for the validators to flag,
so bad data is surfaced rather than silently dropped.
"""

from typing import Any, Dict, Iterable, List, Optional

from src.data.schemas import CanonicalGameEvent, CanonicalMarketSnapshot
from src.data.timestamp import parse_timestamp, to_iso


# Alias tables: canonical field -> accepted raw keys (lowercased).
_GAME_ALIASES = {
    "event_id": ["event_id", "eventid", "game_id", "gameid", "id"],
    "sport": ["sport"],
    "league": ["league", "lg"],
    "home_team": ["home_team", "hometeam", "home"],
    "away_team": ["away_team", "awayteam", "away"],
    "home_score": ["home_score", "homescore", "home_pts", "homepoints"],
    "away_score": ["away_score", "awayscore", "away_pts", "awaypoints"],
    "clock_seconds_remaining": ["clock_seconds_remaining", "clock", "time_remaining", "seconds_left", "secondsleft"],
    "period": ["period", "quarter", "half", "qtr"],
    "status": ["status", "state", "game_status"],
    "possession": ["possession", "poss"],
    "scheduled_start": ["scheduled_start", "scheduledstart", "start_time", "starttime"],
    "timestamp": ["timestamp", "ts", "created_at", "createdat", "time", "observed_at"],
}

_MARKET_ALIASES = {
    "market_id": ["market_id", "marketid", "ticker", "id"],
    "event_id": ["event_id", "eventid", "game_id", "gameid"],
    "timestamp": ["timestamp", "ts", "created_at", "createdat", "time", "observed_at"],
    "yes_bid": ["yes_bid", "yesbid", "bid_yes", "bidyes"],
    "yes_ask": ["yes_ask", "yesask", "ask_yes", "askyes"],
    "no_bid": ["no_bid", "nobid", "bid_no", "bidno"],
    "no_ask": ["no_ask", "noask", "ask_no", "askno"],
    "last_price": ["last_price", "lastprice", "last", "price"],
    "volume": ["volume", "vol"],
    "open_interest": ["open_interest", "openinterest", "oi"],
    "liquidity_score": ["liquidity_score", "liquidityscore", "liquidity", "liq"],
    "source": ["source", "src", "feed"],
}


def _lower_keys(row: Dict[str, Any]) -> Dict[str, Any]:
    return {str(k).strip().lower(): v for k, v in row.items()}


def _pick(row: Dict[str, Any], aliases: List[str]) -> Optional[Any]:
    for a in aliases:
        if a in row and row[a] not in (None, ""):
            return row[a]
    return None


def _as_int(v: Any, default: int = 0) -> int:
    if v is None or v == "":
        return default
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _as_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def normalize_game_row(row: Dict[str, Any]) -> CanonicalGameEvent:
    r = _lower_keys(row)

    def g(field: str) -> Optional[Any]:
        return _pick(r, _GAME_ALIASES[field])

    raw_ts = g("timestamp")
    ts_iso = to_iso(parse_timestamp(raw_ts)) if raw_ts is not None else ""

    sched = g("scheduled_start")
    sched_iso = to_iso(parse_timestamp(sched)) if sched not in (None, "") else None

    return CanonicalGameEvent(
        event_id=str(g("event_id") or ""),
        sport=str(g("sport") or "UNKNOWN"),
        league=str(g("league") or "UNKNOWN"),
        home_team=str(g("home_team") or ""),
        away_team=str(g("away_team") or ""),
        scheduled_start=sched_iso,
        status=str(g("status") or "unknown"),
        period=str(g("period") or ""),
        clock_seconds_remaining=_as_int(g("clock_seconds_remaining")),
        home_score=_as_int(g("home_score")),
        away_score=_as_int(g("away_score")),
        possession=(str(g("possession")) if g("possession") is not None else None),
        timestamp=ts_iso,
    )


def normalize_market_row(row: Dict[str, Any]) -> CanonicalMarketSnapshot:
    r = _lower_keys(row)

    def g(field: str) -> Optional[Any]:
        return _pick(r, _MARKET_ALIASES[field])

    raw_ts = g("timestamp")
    ts_iso = to_iso(parse_timestamp(raw_ts)) if raw_ts is not None else ""

    yes_bid = _as_float(g("yes_bid"))
    yes_ask = _as_float(g("yes_ask"))
    no_bid = _as_float(g("no_bid"))
    no_ask = _as_float(g("no_ask"))

    # Derive the NO side from YES if absent (binary-market identity).
    if no_bid is None and yes_ask is not None:
        no_bid = round(100.0 - yes_ask, 4)
    if no_ask is None and yes_bid is not None:
        no_ask = round(100.0 - yes_bid, 4)

    volume = _as_int(g("volume"))
    open_interest = _as_int(g("open_interest"))

    liquidity = _as_float(g("liquidity_score"))
    if liquidity is None:
        # Heuristic: blend of volume and open interest, capped at 100.
        liquidity = round(min(100.0, (volume + open_interest) / 20.0), 2)

    return CanonicalMarketSnapshot(
        market_id=str(g("market_id") or ""),
        event_id=str(g("event_id") or ""),
        timestamp=ts_iso,
        yes_bid=yes_bid if yes_bid is not None else 0.0,
        yes_ask=yes_ask if yes_ask is not None else 0.0,
        no_bid=no_bid if no_bid is not None else 0.0,
        no_ask=no_ask if no_ask is not None else 0.0,
        last_price=_as_float(g("last_price")),
        volume=volume,
        open_interest=open_interest,
        liquidity_score=liquidity,
        source=str(g("source") or "unknown"),
    )


def normalize_games(rows: Iterable[Dict[str, Any]]) -> List[CanonicalGameEvent]:
    return [normalize_game_row(r) for r in rows]


def normalize_markets(rows: Iterable[Dict[str, Any]]) -> List[CanonicalMarketSnapshot]:
    return [normalize_market_row(r) for r in rows]
