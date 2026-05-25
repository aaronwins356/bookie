from __future__ import annotations

"""
Paired tennis live recorder.

Writes JSONL records containing both a TennisState snapshot and a
Kalshi market snapshot so they can later be converted to a full
ReplayBundle with real game context (no LIVE_UNKNOWN placeholder).

Output path: <base_dir>/YYYY-MM-DD/<match_id>_<ticker>.jsonl

Record format (one JSON object per line):
{
    "received_at": "2026-07-04T14:08:00.123456+00:00",
    "record_type": "paired",
    "match_id": "MOCK-001",
    "ticker": "KXATP-WIM26-SF001",
    "tennis_state": { ... TennisState.to_dict() ... },
    "market_snapshot": { ... market snapshot dict ... }
}

IMPORTANT: No orders are placed. This module only writes files.
"""

import json
import threading
from datetime import datetime, timezone
from io import TextIOWrapper
from pathlib import Path
from typing import Any, Dict, Optional

from src.sports.tennis.state import TennisState


class TennisLiveRecorder:
    """
    Thread-safe append-only recorder for paired tennis + market data.

    Opens one JSONL file per (match_id, ticker, UTC-date) combination.
    Files are rotated at midnight UTC.
    """

    def __init__(self, base_dir: str | Path) -> None:
        self._base = Path(base_dir)
        self._lock = threading.Lock()
        self._handles: Dict[str, TextIOWrapper] = {}
        self._dates: Dict[str, str] = {}

    def record_paired(
        self,
        match_id: str,
        ticker: str,
        tennis_state: TennisState,
        market_snapshot: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Append one paired record. market_snapshot is optional — if None,
        only the tennis state is recorded (useful for state-only testing).
        """
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        received_at = now.isoformat()

        entry: Dict[str, Any] = {
            "received_at": received_at,
            "record_type": "paired",
            "match_id": match_id,
            "ticker": ticker,
            "tennis_state": tennis_state.to_dict(),
        }
        if market_snapshot is not None:
            entry["market_snapshot"] = market_snapshot

        key = f"{match_id}__{_safe(ticker)}"
        with self._lock:
            fh = self._get_handle(key, date_str)
            fh.write(json.dumps(entry) + "\n")
            fh.flush()

    def record_market_only(
        self,
        ticker: str,
        market_snapshot: Dict[str, Any],
    ) -> None:
        """
        Record a market snapshot without game state (fallback path when
        the tennis feed is temporarily unavailable).
        """
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        received_at = now.isoformat()

        entry: Dict[str, Any] = {
            "received_at": received_at,
            "record_type": "market_only",
            "ticker": ticker,
            "market_snapshot": market_snapshot,
        }
        key = f"market_only__{_safe(ticker)}"
        with self._lock:
            fh = self._get_handle(key, date_str)
            fh.write(json.dumps(entry) + "\n")
            fh.flush()

    def _get_handle(self, key: str, date_str: str) -> TextIOWrapper:
        full_key = f"{date_str}/{key}"
        old_date = self._dates.get(key)
        if old_date and old_date != date_str:
            old_full = f"{old_date}/{key}"
            if old_full in self._handles:
                self._handles[old_full].close()
                del self._handles[old_full]

        if full_key not in self._handles:
            day_dir = self._base / date_str
            day_dir.mkdir(parents=True, exist_ok=True)
            path = day_dir / f"{key}.jsonl"
            self._handles[full_key] = open(path, "a", encoding="utf-8")  # noqa: SIM115
            self._dates[key] = date_str

        return self._handles[full_key]

    def close(self) -> None:
        with self._lock:
            for fh in self._handles.values():
                try:
                    fh.close()
                except OSError:
                    pass
            self._handles.clear()

    def __enter__(self) -> "TennisLiveRecorder":
        return self

    def __exit__(self, *_) -> None:
        self.close()


def _safe(s: str) -> str:
    """Make a string safe for use as part of a filename."""
    return s.replace("/", "_").replace("\\", "_").replace(" ", "_")
