from __future__ import annotations

"""
Convert captured JSONL files to ReplayBundle format.

If no game state is present in the captured data, a placeholder
CanonicalGameEvent is created with status=LIVE_UNKNOWN and
metadata missing_game_state=True. The quality report warns
about this so research results are treated with appropriate caution.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.data.bundle import build_bundle, save_bundle
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
from src.live.orderbook_mapper import OrderbookMapper, RawKalshiBook


_PLACEHOLDER_SPORT = "UNKNOWN"
_PLACEHOLDER_LEAGUE = "KALSHI_LIVE"
_MAPPER = OrderbookMapper()


def _make_placeholder_game(ticker: str, timestamp: str) -> CanonicalGameEvent:
    return CanonicalGameEvent(
        event_id=ticker,
        sport=_PLACEHOLDER_SPORT,
        league=_PLACEHOLDER_LEAGUE,
        home_team="UNKNOWN",
        away_team="UNKNOWN",
        scheduled_start=None,
        status="LIVE_UNKNOWN",
        period="UNKNOWN",
        clock_seconds_remaining=0,
        home_score=0,
        away_score=0,
        possession=None,
        timestamp=timestamp,
    )


def _parse_snapshot_from_record(record: Dict[str, Any], ticker: str) -> Optional[CanonicalMarketSnapshot]:
    """Try to extract a CanonicalMarketSnapshot from a recorded JSONL entry."""
    # Use pre-normalized snapshot if present
    if "normalized_snapshot" in record and record["normalized_snapshot"]:
        try:
            return CanonicalMarketSnapshot.from_dict(record["normalized_snapshot"])
        except Exception:  # noqa: BLE001
            pass

    # Try to parse orderbook from raw_message
    raw = record.get("raw_message")
    if not raw:
        return None

    # Handle both dict and string
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None

    if not isinstance(raw, dict):
        return None

    timestamp = record.get("received_at", "")
    msg_type = raw.get("type", "")

    # Orderbook snapshot message
    if msg_type in ("orderbook_snapshot", "orderbook_delta") or "yes" in raw or "no" in raw:
        try:
            book = RawKalshiBook.from_api_response(ticker, timestamp, raw)
            return _MAPPER.map_snapshot(book, event_id=ticker)
        except Exception:  # noqa: BLE001
            pass

    # Ticker message with bid/ask
    msg_data = raw.get("msg", raw)
    if isinstance(msg_data, dict) and ("yes_bid" in msg_data or "yes_ask" in msg_data):
        try:
            return CanonicalMarketSnapshot(
                market_id=ticker,
                event_id=ticker,
                timestamp=timestamp,
                yes_bid=float(msg_data.get("yes_bid", 0)),
                yes_ask=float(msg_data.get("yes_ask", 100)),
                no_bid=float(msg_data.get("no_bid", 0)),
                no_ask=float(msg_data.get("no_ask", 100)),
                last_price=msg_data.get("last_price"),
                volume=int(msg_data.get("volume", 0)),
                open_interest=int(msg_data.get("open_interest", 0)),
                liquidity_score=0.5,
                source="kalshi_live",
            )
        except Exception:  # noqa: BLE001
            pass

    return None


def jsonl_to_bundle(
    jsonl_path: str | Path,
    ticker: Optional[str] = None,
    out_path: Optional[str | Path] = None,
) -> ReplayBundle:
    """
    Convert a single JSONL capture file to a ReplayBundle.

    When no game state is available, a placeholder game event is created
    and the quality report includes a MISSING_GAME_STATE warning.
    """
    path = Path(jsonl_path)
    if not path.exists():
        raise FileNotFoundError(f"Capture file not found: {path}")

    if ticker is None:
        ticker = path.stem

    records = _load_jsonl(path)
    if not records:
        raise ValueError(f"No records found in {path}")

    ticks: List[CanonicalReplayTick] = []
    missing_game_state = True  # assume true until we find game data
    skipped = 0

    for record in records:
        timestamp = record.get("received_at", "")
        if not timestamp:
            skipped += 1
            continue

        snap = _parse_snapshot_from_record(record, ticker)
        if snap is None:
            skipped += 1
            continue

        game_event = _make_placeholder_game(ticker, timestamp)

        tick = CanonicalReplayTick(
            timestamp=timestamp,
            game_event=game_event,
            market_snapshot=snap,
            metadata={
                "missing_game_state": missing_game_state,
                "source": "kalshi_live_capture",
                "raw_source": record.get("source", "kalshi_ws"),
            },
        )
        ticks.append(tick)

    if not ticks:
        raise ValueError(
            f"No usable market snapshots found in {path}. "
            "Check that the file contains orderbook or ticker messages."
        )

    # Build quality report with missing-game-state warning
    issues = []
    if missing_game_state:
        issues.append(ValidationIssue(
            severity=Severity.WARNING,
            code="MISSING_GAME_STATE",
            message=(
                f"No game state data found in capture for {ticker}. "
                "Placeholder game events were created. "
                "Strategy signals that depend on game context (score, period, clock) "
                "will not be meaningful. Backtest results are market-microstructure only."
            ),
            suggested_fix="Pair with a sports data feed or add game state records to the JSONL.",
        ))

    if skipped > 0:
        issues.append(ValidationIssue(
            severity=Severity.INFO,
            code="SKIPPED_RECORDS",
            message=f"{skipped} records skipped (no parseable market snapshot).",
        ))

    qr = DataQualityReport(
        total_game_rows=0 if missing_game_state else len(ticks),
        total_market_rows=len(ticks),
        total_aligned_ticks=len(ticks),
        dropped_rows=skipped,
        warning_count=sum(1 for i in issues if i.severity == Severity.WARNING),
        info_count=sum(1 for i in issues if i.severity == Severity.INFO),
        time_range_start=ticks[0].timestamp,
        time_range_end=ticks[-1].timestamp,
        verdict=Verdict.PASS_WITH_WARNINGS if missing_game_state else Verdict.PASS,
        issues=issues,
    )

    created_at = ticks[-1].timestamp
    sport_label = _PLACEHOLDER_SPORT
    bundle = ReplayBundle(
        bundle_id=f"live-{ticker}-{len(ticks)}ticks",
        created_at=created_at,
        sport=sport_label,
        league=_PLACEHOLDER_LEAGUE,
        event_id=ticker,
        ticks=ticks,
        quality_report=qr,
        source_metadata={
            "source_file": str(path),
            "ticker": ticker,
            "missing_game_state": missing_game_state,
            "capture_mode": "DATA_CAPTURE_ONLY",
        },
    )

    if out_path:
        save_bundle(bundle, out_path)

    return bundle


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
