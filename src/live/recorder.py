from __future__ import annotations

"""
Append-only JSONL recorder for live Kalshi market data.

Writes to: <base_dir>/YYYY-MM-DD/<ticker>.jsonl
One JSON object per line; flushed after every write.
Files are rotated by UTC date automatically.
"""

import json
import threading
from datetime import datetime, timezone
from io import TextIOWrapper
from pathlib import Path
from typing import Any, Dict, Optional


class LiveRecorder:
    """
    Thread-safe append-only recorder. Creates date-partitioned JSONL files.
    Each record contains received_at, source, ticker, and raw_message.
    """

    def __init__(self, base_dir: str | Path) -> None:
        self._base = Path(base_dir)
        self._lock = threading.Lock()
        self._handles: Dict[str, TextIOWrapper] = {}  # key = "YYYY-MM-DD/ticker"
        self._dates: Dict[str, str] = {}              # key = ticker -> last date used

    def record(
        self,
        ticker: str,
        raw_message: Any,
        source: str = "kalshi_ws",
        normalized_snapshot: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append one record. Automatically rotates file on UTC date change."""
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        received_at = now.isoformat()

        entry: Dict[str, Any] = {
            "received_at": received_at,
            "source": source,
            "ticker": ticker,
            "raw_message": raw_message,
        }
        if normalized_snapshot is not None:
            entry["normalized_snapshot"] = normalized_snapshot

        with self._lock:
            fh = self._get_handle(ticker, date_str)
            fh.write(json.dumps(entry) + "\n")
            fh.flush()

    def _get_handle(self, ticker: str, date_str: str) -> TextIOWrapper:
        key = f"{date_str}/{ticker}"
        # Rotate if date changed for this ticker
        old_date = self._dates.get(ticker)
        if old_date and old_date != date_str and old_date + "/" + ticker in self._handles:
            self._handles[old_date + "/" + ticker].close()
            del self._handles[old_date + "/" + ticker]

        if key not in self._handles:
            day_dir = self._base / date_str
            day_dir.mkdir(parents=True, exist_ok=True)
            path = day_dir / f"{_safe_ticker(ticker)}.jsonl"
            self._handles[key] = open(path, "a", encoding="utf-8")  # noqa: SIM115
            self._dates[ticker] = date_str

        return self._handles[key]

    def close(self) -> None:
        with self._lock:
            for fh in self._handles.values():
                try:
                    fh.close()
                except OSError:
                    pass
            self._handles.clear()

    def __enter__(self) -> "LiveRecorder":
        return self

    def __exit__(self, *_) -> None:
        self.close()


def _safe_ticker(ticker: str) -> str:
    """Make ticker safe for use as a filename."""
    return ticker.replace("/", "_").replace("\\", "_").replace(" ", "_")
