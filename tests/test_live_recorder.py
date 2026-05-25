from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.live.recorder import LiveRecorder, _safe_ticker


class TestLiveRecorder:
    def test_creates_date_partitioned_file(self, tmp_path):
        with LiveRecorder(tmp_path) as rec:
            rec.record("KXBTC-TEST", {"type": "ticker"})

        # Should have created a YYYY-MM-DD subdirectory
        day_dirs = [d for d in tmp_path.iterdir() if d.is_dir()]
        assert len(day_dirs) == 1
        day = day_dirs[0].name
        # Date format YYYY-MM-DD
        assert len(day) == 10
        assert day[4] == "-" and day[7] == "-"

    def test_writes_jsonl_with_required_fields(self, tmp_path):
        with LiveRecorder(tmp_path) as rec:
            rec.record("TICKER1", {"foo": "bar"}, source="kalshi_ws")

        files = list(tmp_path.rglob("*.jsonl"))
        assert len(files) == 1
        lines = files[0].read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert "received_at" in entry
        assert "source" in entry
        assert "ticker" in entry
        assert "raw_message" in entry
        assert entry["source"] == "kalshi_ws"
        assert entry["ticker"] == "TICKER1"
        assert entry["raw_message"] == {"foo": "bar"}

    def test_appends_multiple_records(self, tmp_path):
        with LiveRecorder(tmp_path) as rec:
            for i in range(5):
                rec.record("TICKER", {"i": i})

        files = list(tmp_path.rglob("*.jsonl"))
        assert len(files) == 1
        lines = [l for l in files[0].read_text().strip().split("\n") if l.strip()]
        assert len(lines) == 5

    def test_different_tickers_different_files(self, tmp_path):
        with LiveRecorder(tmp_path) as rec:
            rec.record("TICKER-A", {"x": 1})
            rec.record("TICKER-B", {"x": 2})

        files = list(tmp_path.rglob("*.jsonl"))
        assert len(files) == 2

    def test_normalized_snapshot_included_when_provided(self, tmp_path):
        snap = {"yes_bid": 55.0, "yes_ask": 65.0}
        with LiveRecorder(tmp_path) as rec:
            rec.record("T", {"raw": "data"}, normalized_snapshot=snap)

        files = list(tmp_path.rglob("*.jsonl"))
        entry = json.loads(files[0].read_text().strip())
        assert "normalized_snapshot" in entry
        assert entry["normalized_snapshot"]["yes_bid"] == 55.0

    def test_normalized_snapshot_absent_by_default(self, tmp_path):
        with LiveRecorder(tmp_path) as rec:
            rec.record("T", {"raw": "data"})

        files = list(tmp_path.rglob("*.jsonl"))
        entry = json.loads(files[0].read_text().strip())
        assert "normalized_snapshot" not in entry

    def test_context_manager_closes_handles(self, tmp_path):
        rec = LiveRecorder(tmp_path)
        rec.record("T", {"x": 1})
        rec.close()
        assert len(rec._handles) == 0

    def test_records_are_valid_json(self, tmp_path):
        with LiveRecorder(tmp_path) as rec:
            rec.record("T", {"nested": {"a": 1, "b": [2, 3]}})
            rec.record("T", "string message")
            rec.record("T", 42)

        files = list(tmp_path.rglob("*.jsonl"))
        for line in files[0].read_text().strip().split("\n"):
            assert line.strip(), "Empty line found"
            parsed = json.loads(line)
            assert isinstance(parsed, dict)


class TestSafeTicker:
    def test_replaces_slashes(self):
        assert "/" not in _safe_ticker("KXBTC/25MAY")

    def test_replaces_backslashes(self):
        assert "\\" not in _safe_ticker("KXBTC\\25MAY")

    def test_replaces_spaces(self):
        assert " " not in _safe_ticker("TICKER WITH SPACES")

    def test_normal_ticker_unchanged(self):
        assert _safe_ticker("KXBTC15M-25MAY-T32000") == "KXBTC15M-25MAY-T32000"
