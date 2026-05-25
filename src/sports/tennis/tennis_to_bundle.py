from __future__ import annotations

"""
Convert paired tennis live captures (JSONL) to ReplayBundle format.

Unlike live_to_bundle.py (which creates LIVE_UNKNOWN placeholder events),
this converter uses the TennisState stored in each record to build real
CanonicalGameEvent objects. No placeholder is needed when tennis state exists.

If a record has record_type="market_only" (no tennis_state), a warning
is appended to the quality report and that tick is created with a
LIVE_UNKNOWN placeholder — same as the generic converter.

Output ReplayBundle has:
  - sport="tennis"
  - league from tour (ATP/WTA/UNKNOWN)
  - source_metadata["has_tennis_state"] = True
  - No MISSING_GAME_STATE issue if all ticks have state
"""

import json
from datetime import timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.data.bundle import save_bundle
from src.data.schemas import (
    CanonicalGameEvent,
    CanonicalMarketSnapshot,
    CanonicalReplayTick,
    DataQualityReport,
    ReplayBundle,
    Severity,
    ValidationIssue,
    Verdict,
)
from src.sports.tennis.state import TennisState
from src.sports.tennis.replay_adapter import tennis_state_to_game_state


_PLACEHOLDER_STATUS = "LIVE_UNKNOWN"
_TENNIS_SPORT = "tennis"


def tennis_jsonl_to_bundle(
    jsonl_path: str | Path,
    out_path: Optional[str | Path] = None,
    ticker: Optional[str] = None,
) -> ReplayBundle:
    """
    Convert a paired tennis JSONL capture to a ReplayBundle.

    Reads records written by TennisLiveRecorder. Records with tennis_state
    produce full game events; records without produce LIVE_UNKNOWN placeholders
    and a quality-report warning.
    """
    path = Path(jsonl_path)
    if not path.exists():
        raise FileNotFoundError(f"Capture file not found: {path}")

    if ticker is None:
        ticker = path.stem

    records = _load_jsonl(path)
    if not records:
        raise ValueError(f"No records in {path}")

    ticks: List[CanonicalReplayTick] = []
    issues: List[ValidationIssue] = []
    skipped = 0
    placeholder_count = 0
    state_count = 0

    for record in records:
        received_at = record.get("received_at", "")
        if not received_at:
            skipped += 1
            continue

        market_snap = _parse_market_snapshot(record, ticker, received_at)
        if market_snap is None:
            skipped += 1
            continue

        tennis_dict = record.get("tennis_state")
        if tennis_dict:
            try:
                tennis_state = TennisState.from_dict(tennis_dict)
                game_event = _game_event_from_tennis(tennis_state, received_at)
                metadata = {
                    "has_tennis_state": True,
                    "source": record.get("record_type", "paired"),
                    "match_id": record.get("match_id", ""),
                }
                state_count += 1
            except Exception as exc:
                game_event = _placeholder_game(ticker, received_at)
                metadata = {
                    "has_tennis_state": False,
                    "parse_error": str(exc),
                    "source": record.get("record_type", "paired"),
                }
                placeholder_count += 1
        else:
            game_event = _placeholder_game(ticker, received_at)
            metadata = {
                "has_tennis_state": False,
                "source": record.get("record_type", "market_only"),
            }
            placeholder_count += 1

        ticks.append(CanonicalReplayTick(
            timestamp=received_at,
            game_event=game_event,
            market_snapshot=market_snap,
            metadata=metadata,
        ))

    if not ticks:
        raise ValueError(
            f"No usable records in {path}. "
            "Ensure records contain 'market_snapshot' with yes_bid/yes_ask."
        )

    if placeholder_count > 0:
        issues.append(ValidationIssue(
            severity=Severity.WARNING,
            code="PARTIAL_GAME_STATE",
            message=(
                f"{placeholder_count}/{len(ticks)} ticks missing tennis_state. "
                "Those ticks use LIVE_UNKNOWN placeholder game events."
            ),
            suggested_fix="Ensure tennis feed was running during all recorded ticks.",
        ))

    if skipped > 0:
        issues.append(ValidationIssue(
            severity=Severity.INFO,
            code="SKIPPED_RECORDS",
            message=f"{skipped} records skipped (missing timestamp or market data).",
        ))

    verdict = (
        Verdict.PASS if placeholder_count == 0
        else Verdict.PASS_WITH_WARNINGS
    )
    league = _infer_league(ticks)
    qr = DataQualityReport(
        total_game_rows=state_count,
        total_market_rows=len(ticks),
        total_aligned_ticks=len(ticks),
        dropped_rows=skipped,
        warning_count=sum(1 for i in issues if i.severity == Severity.WARNING),
        info_count=sum(1 for i in issues if i.severity == Severity.INFO),
        time_range_start=ticks[0].timestamp,
        time_range_end=ticks[-1].timestamp,
        verdict=verdict,
        issues=issues,
    )

    bundle = ReplayBundle(
        bundle_id=f"tennis-{ticker}-{len(ticks)}ticks",
        created_at=ticks[-1].timestamp,
        sport=_TENNIS_SPORT,
        league=league,
        event_id=ticker,
        ticks=ticks,
        quality_report=qr,
        source_metadata={
            "source_file": str(path),
            "ticker": ticker,
            "has_tennis_state": state_count > 0,
            "ticks_with_state": state_count,
            "ticks_placeholder": placeholder_count,
            "capture_mode": "TENNIS_PAIRED",
        },
    )

    if out_path:
        save_bundle(bundle, out_path)

    return bundle


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _game_event_from_tennis(state: TennisState, timestamp: str) -> CanonicalGameEvent:
    """Convert TennisState → CanonicalGameEvent (the canonical schema type)."""
    gs = tennis_state_to_game_state(state)
    status = "finished" if state.match_over else "in_progress"
    if state.suspended:
        status = "suspended"
    period = f"set{state.current_set}"
    if state.tiebreak:
        period = f"set{state.current_set}_tiebreak"

    return CanonicalGameEvent(
        event_id=state.match_id,
        sport=_TENNIS_SPORT,
        league=state.tour.value,
        home_team=state.player_a,
        away_team=state.player_b,
        scheduled_start=None,
        status=status,
        period=period,
        clock_seconds_remaining=0,
        home_score=state.sets_a,
        away_score=state.sets_b,
        possession=state.server.value if state.server.value != "UNKNOWN" else None,
        timestamp=timestamp,
    )


def _placeholder_game(ticker: str, timestamp: str) -> CanonicalGameEvent:
    return CanonicalGameEvent(
        event_id=ticker,
        sport=_TENNIS_SPORT,
        league="UNKNOWN",
        home_team="UNKNOWN",
        away_team="UNKNOWN",
        scheduled_start=None,
        status=_PLACEHOLDER_STATUS,
        period="UNKNOWN",
        clock_seconds_remaining=0,
        home_score=0,
        away_score=0,
        possession=None,
        timestamp=timestamp,
    )


def _parse_market_snapshot(
    record: Dict[str, Any],
    ticker: str,
    timestamp: str,
) -> Optional[CanonicalMarketSnapshot]:
    """Extract a CanonicalMarketSnapshot from various record layouts."""
    snap_dict = record.get("market_snapshot")
    if not snap_dict or not isinstance(snap_dict, dict):
        return None

    try:
        yes_bid = float(snap_dict.get("yes_bid", snap_dict.get("yes_ask", 0)))
        yes_ask = float(snap_dict.get("yes_ask", snap_dict.get("yes_bid", 100)))
        no_bid = float(snap_dict.get("no_bid", 100 - yes_ask))
        no_ask = float(snap_dict.get("no_ask", 100 - yes_bid))
        return CanonicalMarketSnapshot(
            market_id=snap_dict.get("market_id", ticker),
            event_id=snap_dict.get("event_id", ticker),
            timestamp=snap_dict.get("timestamp", timestamp),
            yes_bid=yes_bid,
            yes_ask=yes_ask,
            no_bid=no_bid,
            no_ask=no_ask,
            last_price=snap_dict.get("last_price"),
            volume=int(snap_dict.get("volume", 0)),
            open_interest=int(snap_dict.get("open_interest", 0)),
            liquidity_score=float(snap_dict.get("liquidity_score", 0.5)),
            source=snap_dict.get("source", "tennis_paired"),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _infer_league(ticks: List[CanonicalReplayTick]) -> str:
    for tick in ticks:
        league = tick.game_event.league
        if league and league not in ("UNKNOWN", "LIVE_UNKNOWN"):
            return league
    return "UNKNOWN"


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    records = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records
