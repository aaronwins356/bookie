from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.sports.tennis.live_recorder import TennisLiveRecorder, _safe
from src.sports.tennis.mock_provider import MockProvider
from src.sports.tennis.state import TennisState


def _state() -> TennisState:
    return MockProvider().get_match_state("MOCK-001")


class TestSafeFilename:
    def test_replaces_slash(self):
        assert "/" not in _safe("KXATP/WIM26")

    def test_replaces_backslash(self):
        assert "\\" not in _safe("KXATP\\WIM26")

    def test_replaces_space(self):
        assert " " not in _safe("ABC DEF")

    def test_preserves_alphanumeric(self):
        assert _safe("KXATP-WIM26-001") == "KXATP-WIM26-001"


class TestTennisLiveRecorderInit:
    def test_creates_recorder(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec = TennisLiveRecorder(tmp)
            assert rec is not None

    def test_context_manager(self):
        with tempfile.TemporaryDirectory() as tmp:
            with TennisLiveRecorder(tmp) as rec:
                assert isinstance(rec, TennisLiveRecorder)


class TestRecordPaired:
    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with TennisLiveRecorder(tmp) as rec:
                state = _state()
                rec.record_paired("MOCK-001", "KXATP-WIM26", state)

            files = list(Path(tmp).rglob("*.jsonl"))
            assert len(files) == 1

    def test_file_contains_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            with TennisLiveRecorder(tmp) as rec:
                state = _state()
                rec.record_paired("MOCK-001", "KXATP-WIM26", state)

            files = list(Path(tmp).rglob("*.jsonl"))
            with open(files[0]) as f:
                record = json.loads(f.readline())
            assert "received_at" in record

    def test_record_type_is_paired(self):
        with tempfile.TemporaryDirectory() as tmp:
            with TennisLiveRecorder(tmp) as rec:
                rec.record_paired("MOCK-001", "KXATP-WIM26", _state())
            with open(list(Path(tmp).rglob("*.jsonl"))[0]) as f:
                record = json.loads(f.readline())
            assert record["record_type"] == "paired"

    def test_match_id_in_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            with TennisLiveRecorder(tmp) as rec:
                rec.record_paired("MOCK-001", "KXATP-WIM26", _state())
            with open(list(Path(tmp).rglob("*.jsonl"))[0]) as f:
                record = json.loads(f.readline())
            assert record["match_id"] == "MOCK-001"

    def test_ticker_in_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            with TennisLiveRecorder(tmp) as rec:
                rec.record_paired("MOCK-001", "KXATP-WIM26", _state())
            with open(list(Path(tmp).rglob("*.jsonl"))[0]) as f:
                record = json.loads(f.readline())
            assert record["ticker"] == "KXATP-WIM26"

    def test_tennis_state_in_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            with TennisLiveRecorder(tmp) as rec:
                rec.record_paired("MOCK-001", "KXATP-WIM26", _state())
            with open(list(Path(tmp).rglob("*.jsonl"))[0]) as f:
                record = json.loads(f.readline())
            assert "tennis_state" in record
            assert record["tennis_state"]["match_id"] == "MOCK-001"

    def test_market_snapshot_optional(self):
        with tempfile.TemporaryDirectory() as tmp:
            with TennisLiveRecorder(tmp) as rec:
                rec.record_paired("MOCK-001", "KXATP-WIM26", _state(), market_snapshot=None)
            with open(list(Path(tmp).rglob("*.jsonl"))[0]) as f:
                record = json.loads(f.readline())
            assert "market_snapshot" not in record

    def test_market_snapshot_included_when_provided(self):
        snap = {"yes_bid": 48.0, "yes_ask": 52.0, "volume": 100}
        with tempfile.TemporaryDirectory() as tmp:
            with TennisLiveRecorder(tmp) as rec:
                rec.record_paired("MOCK-001", "KXATP-WIM26", _state(), snap)
            with open(list(Path(tmp).rglob("*.jsonl"))[0]) as f:
                record = json.loads(f.readline())
            assert record["market_snapshot"]["yes_bid"] == 48.0

    def test_multiple_records_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            with TennisLiveRecorder(tmp) as rec:
                for _ in range(5):
                    rec.record_paired("MOCK-001", "KXATP-WIM26", _state())
            with open(list(Path(tmp).rglob("*.jsonl"))[0]) as f:
                lines = f.readlines()
            assert len(lines) == 5

    def test_different_pairs_go_to_different_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            with TennisLiveRecorder(tmp) as rec:
                rec.record_paired("MOCK-001", "KXATP-WIM26", _state())
                rec.record_paired("MOCK-002", "KXATP-USO26", _state())
            files = list(Path(tmp).rglob("*.jsonl"))
            assert len(files) == 2

    def test_file_path_contains_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            with TennisLiveRecorder(tmp) as rec:
                rec.record_paired("MOCK-001", "KXATP-WIM26", _state())
            files = list(Path(tmp).rglob("*.jsonl"))
            # Path should contain YYYY-MM-DD segment
            import re
            path_str = str(files[0])
            assert re.search(r"\d{4}-\d{2}-\d{2}", path_str)


class TestRecordMarketOnly:
    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with TennisLiveRecorder(tmp) as rec:
                rec.record_market_only("KXATP-WIM26", {"yes_bid": 48.0, "yes_ask": 52.0})
            files = list(Path(tmp).rglob("*.jsonl"))
            assert len(files) == 1

    def test_record_type_is_market_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            with TennisLiveRecorder(tmp) as rec:
                rec.record_market_only("KXATP-WIM26", {"yes_bid": 48.0})
            with open(list(Path(tmp).rglob("*.jsonl"))[0]) as f:
                record = json.loads(f.readline())
            assert record["record_type"] == "market_only"

    def test_no_tennis_state_in_market_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            with TennisLiveRecorder(tmp) as rec:
                rec.record_market_only("KXATP-WIM26", {"yes_bid": 48.0})
            with open(list(Path(tmp).rglob("*.jsonl"))[0]) as f:
                record = json.loads(f.readline())
            assert "tennis_state" not in record


class TestClose:
    def test_close_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec = TennisLiveRecorder(tmp)
            rec.record_paired("MOCK-001", "KXATP-WIM26", _state())
            rec.close()
            rec.close()  # should not raise
