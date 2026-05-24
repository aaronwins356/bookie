from __future__ import annotations

"""
Validators. Produce structured ValidationIssue lists over canonical models.

Design principle for this phase: make bad data *obvious*. Validators never
mutate or silently fix data — they describe what is wrong, how severe it is,
and (optionally) a suggested fix, so a quality report can decide PASS /
PASS_WITH_WARNINGS / FAIL.
"""

from typing import List, Set

from src.data.schemas import (
    CanonicalGameEvent, CanonicalMarketSnapshot, Severity, ValidationIssue,
)
from src.data.timestamp import parse_timestamp, AmbiguousTimestampError

# A market is considered stale if its snapshot is older than this many
# seconds relative to the latest snapshot in its event.
STALE_MARKET_SECONDS = 120.0
# A suspicious gap between consecutive snapshots (seconds).
SUSPICIOUS_GAP_SECONDS = 300.0
MAX_PLAUSIBLE_SCORE = 200


def _ts(value: str):
    try:
        return parse_timestamp(value)
    except AmbiguousTimestampError:
        return None


def validate_game_events(events: List[CanonicalGameEvent]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    prev_ts = None
    prev_clock = None
    prev_period = None
    seen = set()

    for i, e in enumerate(events):
        if not e.event_id:
            issues.append(ValidationIssue(
                Severity.FATAL, "GAME_MISSING_EVENT_ID",
                "game event has no event_id", index=i,
                suggested_fix="ensure source provides a stable event/game id",
            ))

        if not e.timestamp:
            issues.append(ValidationIssue(
                Severity.ERROR, "GAME_MISSING_TIMESTAMP",
                "game event has no timestamp", index=i,
            ))
            continue

        ts = _ts(e.timestamp)
        if ts is None:
            issues.append(ValidationIssue(
                Severity.ERROR, "GAME_BAD_TIMESTAMP",
                f"unparseable timestamp {e.timestamp!r}", index=i, timestamp=e.timestamp,
            ))
            continue

        if prev_ts is not None and ts < prev_ts:
            issues.append(ValidationIssue(
                Severity.ERROR, "GAME_TIMESTAMP_OUT_OF_ORDER",
                "game timestamps not monotonically increasing",
                index=i, timestamp=e.timestamp,
                suggested_fix="sort rows by timestamp before ingesting",
            ))

        if e.home_score < 0 or e.away_score < 0:
            issues.append(ValidationIssue(
                Severity.ERROR, "GAME_NEGATIVE_SCORE",
                f"negative score {e.home_score}-{e.away_score}", index=i, timestamp=e.timestamp,
            ))
        if e.home_score > MAX_PLAUSIBLE_SCORE or e.away_score > MAX_PLAUSIBLE_SCORE:
            issues.append(ValidationIssue(
                Severity.WARNING, "GAME_IMPLAUSIBLE_SCORE",
                f"implausible score {e.home_score}-{e.away_score}", index=i, timestamp=e.timestamp,
            ))

        if e.clock_seconds_remaining < 0:
            issues.append(ValidationIssue(
                Severity.ERROR, "GAME_NEGATIVE_CLOCK",
                f"negative clock {e.clock_seconds_remaining}", index=i, timestamp=e.timestamp,
            ))

        # Clock should not increase within the same period.
        if (prev_clock is not None and prev_period == e.period
                and e.clock_seconds_remaining > prev_clock):
            issues.append(ValidationIssue(
                Severity.WARNING, "GAME_CLOCK_BACKWARDS",
                f"clock increased within period {e.period} "
                f"({prev_clock} -> {e.clock_seconds_remaining})",
                index=i, timestamp=e.timestamp,
                suggested_fix="verify period boundaries / clock direction",
            ))

        key = (e.event_id, e.timestamp)
        if key in seen:
            issues.append(ValidationIssue(
                Severity.WARNING, "GAME_DUPLICATE_SNAPSHOT",
                f"duplicate game snapshot at {e.timestamp}", index=i, timestamp=e.timestamp,
            ))
        seen.add(key)

        prev_ts, prev_clock, prev_period = ts, e.clock_seconds_remaining, e.period

    return issues


def validate_market_snapshots(snaps: List[CanonicalMarketSnapshot]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    prev_ts = None
    seen = set()
    parsed_ts = []

    for i, m in enumerate(snaps):
        if not m.event_id:
            issues.append(ValidationIssue(
                Severity.ERROR, "MARKET_MISSING_EVENT_ID",
                "market snapshot has no event_id", index=i, timestamp=m.timestamp,
            ))

        if not m.timestamp:
            issues.append(ValidationIssue(
                Severity.ERROR, "MARKET_MISSING_TIMESTAMP",
                "market snapshot has no timestamp", index=i,
            ))
            parsed_ts.append(None)
            continue

        ts = _ts(m.timestamp)
        parsed_ts.append(ts)
        if ts is None:
            issues.append(ValidationIssue(
                Severity.ERROR, "MARKET_BAD_TIMESTAMP",
                f"unparseable timestamp {m.timestamp!r}", index=i, timestamp=m.timestamp,
            ))
            continue

        if prev_ts is not None and ts < prev_ts:
            issues.append(ValidationIssue(
                Severity.ERROR, "MARKET_TIMESTAMP_OUT_OF_ORDER",
                "market timestamps not monotonically increasing",
                index=i, timestamp=m.timestamp,
                suggested_fix="sort rows by timestamp before ingesting",
            ))

        # Price sanity.
        for label, price in (("yes_bid", m.yes_bid), ("yes_ask", m.yes_ask),
                             ("no_bid", m.no_bid), ("no_ask", m.no_ask)):
            if price < 0:
                issues.append(ValidationIssue(
                    Severity.ERROR, "MARKET_NEGATIVE_PRICE",
                    f"{label} negative ({price})", index=i, timestamp=m.timestamp,
                ))
            elif price > 100:
                issues.append(ValidationIssue(
                    Severity.ERROR, "MARKET_PRICE_OUT_OF_RANGE",
                    f"{label} > 100 ({price})", index=i, timestamp=m.timestamp,
                    suggested_fix="prices must be in cents 0-100",
                ))

        if m.yes_bid > m.yes_ask:
            issues.append(ValidationIssue(
                Severity.ERROR, "MARKET_YES_CROSSED",
                f"yes_bid {m.yes_bid} > yes_ask {m.yes_ask}", index=i, timestamp=m.timestamp,
            ))
        if m.no_bid > m.no_ask:
            issues.append(ValidationIssue(
                Severity.ERROR, "MARKET_NO_CROSSED",
                f"no_bid {m.no_bid} > no_ask {m.no_ask}", index=i, timestamp=m.timestamp,
            ))

        # YES/NO consistency: yes_ask + no_bid should be ~100 in a coherent book.
        if abs((m.yes_ask + m.no_bid) - 100.0) > 5.0:
            issues.append(ValidationIssue(
                Severity.WARNING, "MARKET_YESNO_INCONSISTENT",
                f"yes_ask({m.yes_ask}) + no_bid({m.no_bid}) far from 100",
                index=i, timestamp=m.timestamp,
            ))

        if m.volume < 0 or m.open_interest < 0:
            issues.append(ValidationIssue(
                Severity.ERROR, "MARKET_NEGATIVE_LIQUIDITY",
                f"negative volume/oi ({m.volume}/{m.open_interest})", index=i, timestamp=m.timestamp,
            ))
        elif m.volume == 0 and m.open_interest == 0:
            issues.append(ValidationIssue(
                Severity.WARNING, "MARKET_NO_LIQUIDITY",
                "zero volume and open interest", index=i, timestamp=m.timestamp,
            ))

        key = (m.market_id, m.timestamp)
        if key in seen:
            issues.append(ValidationIssue(
                Severity.WARNING, "MARKET_DUPLICATE_SNAPSHOT",
                f"duplicate market snapshot at {m.timestamp}", index=i, timestamp=m.timestamp,
            ))
        seen.add(key)

        prev_ts = ts

    # Suspicious gaps between consecutive valid snapshots.
    valid = [t for t in parsed_ts if t is not None]
    for a, b in zip(valid, valid[1:]):
        gap = (b - a).total_seconds()
        if gap > SUSPICIOUS_GAP_SECONDS:
            issues.append(ValidationIssue(
                Severity.WARNING, "MARKET_SUSPICIOUS_GAP",
                f"gap of {gap:.0f}s between market snapshots",
                timestamp=b.isoformat(),
                suggested_fix="check for dropped data in the feed",
            ))

    return issues


def validate_cross(
    events: List[CanonicalGameEvent],
    snaps: List[CanonicalMarketSnapshot],
) -> List[ValidationIssue]:
    """Cross-checks between the two streams."""
    issues: List[ValidationIssue] = []
    event_ids: Set[str] = {e.event_id for e in events if e.event_id}

    for i, m in enumerate(snaps):
        if m.event_id and m.event_id not in event_ids:
            issues.append(ValidationIssue(
                Severity.ERROR, "MARKET_NO_MATCHING_EVENT",
                f"market event_id {m.event_id!r} has no matching game event",
                index=i, timestamp=m.timestamp,
                suggested_fix="ingest the corresponding game-event file",
            ))

    if not events:
        issues.append(ValidationIssue(
            Severity.FATAL, "NO_GAME_EVENTS", "no game events provided",
        ))
    if not snaps:
        issues.append(ValidationIssue(
            Severity.FATAL, "NO_MARKET_SNAPSHOTS", "no market snapshots provided",
        ))

    return issues


def validate_all(
    events: List[CanonicalGameEvent],
    snaps: List[CanonicalMarketSnapshot],
) -> List[ValidationIssue]:
    return (
        validate_game_events(events)
        + validate_market_snapshots(snaps)
        + validate_cross(events, snaps)
    )
