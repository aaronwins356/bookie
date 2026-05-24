from __future__ import annotations

"""
Aligner. Joins market snapshots to the nearest-in-time game event and
emits CanonicalReplayTick objects in deterministic timestamp order.

Each market snapshot anchors a tick; the closest game event within
`max_lag_seconds` is attached. Lag and staleness are recorded in tick
metadata so downstream consumers (and the quality report) can see exactly
how well the two streams lined up — bad alignment never silently produces
a clean-looking tick.
"""

from dataclasses import dataclass
from typing import List, Optional

from src.data.schemas import (
    CanonicalGameEvent, CanonicalMarketSnapshot, CanonicalReplayTick,
)
from src.data.timestamp import parse_timestamp, AmbiguousTimestampError

DEFAULT_MAX_LAG_SECONDS = 60.0
STALE_GAME_SECONDS = 90.0
STALE_MARKET_SECONDS = 120.0


@dataclass
class AlignmentResult:
    ticks: List[CanonicalReplayTick]
    dropped: int
    stale_game: int
    stale_market: int


def _epoch(ts: str) -> Optional[float]:
    try:
        return parse_timestamp(ts).timestamp()
    except (AmbiguousTimestampError, ValueError):
        return None


def align(
    events: List[CanonicalGameEvent],
    snaps: List[CanonicalMarketSnapshot],
    max_lag_seconds: float = DEFAULT_MAX_LAG_SECONDS,
) -> AlignmentResult:
    # Pre-compute event epochs once; keep only parseable events.
    indexed_events = []
    for e in events:
        t = _epoch(e.timestamp)
        if t is not None:
            indexed_events.append((t, e))
    indexed_events.sort(key=lambda x: x[0])

    # Sort snapshots by time for deterministic output.
    indexed_snaps = []
    for m in snaps:
        t = _epoch(m.timestamp)
        if t is not None:
            indexed_snaps.append((t, m))
    indexed_snaps.sort(key=lambda x: x[0])

    ticks: List[CanonicalReplayTick] = []
    dropped = 0
    stale_game = 0
    stale_market = 0
    prev_snap_t: Optional[float] = None

    for t, m in indexed_snaps:
        nearest = _nearest_event(indexed_events, t)
        if nearest is None:
            dropped += 1
            continue

        ev_t, ev = nearest
        lag = abs(t - ev_t)
        if lag > max_lag_seconds:
            dropped += 1
            continue

        # Game is stale if the attached game snapshot is far (in time) from
        # this market tick. Market is stale if the feed went quiet — a long
        # gap since the previous market snapshot.
        game_is_stale = lag > STALE_GAME_SECONDS
        market_is_stale = (
            prev_snap_t is not None and (t - prev_snap_t) > STALE_MARKET_SECONDS
        )
        if game_is_stale:
            stale_game += 1
        if market_is_stale:
            stale_market += 1
        prev_snap_t = t

        ticks.append(CanonicalReplayTick(
            timestamp=m.timestamp,
            game_event=ev,
            market_snapshot=m,
            orderbook_snapshot=None,
            metadata={
                "lag_seconds": round(lag, 3),
                "stale_game": game_is_stale,
                "stale_market": market_is_stale,
            },
        ))

    return AlignmentResult(
        ticks=ticks, dropped=dropped,
        stale_game=stale_game, stale_market=stale_market,
    )


def _nearest_event(indexed_events, t: float):
    """Linear nearest-by-time search (data sizes here are small)."""
    best = None
    best_gap = None
    for ev_t, ev in indexed_events:
        gap = abs(ev_t - t)
        if best_gap is None or gap < best_gap:
            best_gap = gap
            best = (ev_t, ev)
    return best
