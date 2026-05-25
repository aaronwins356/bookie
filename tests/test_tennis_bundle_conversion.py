from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.data.schemas import ReplayBundle, Verdict
from src.sports.tennis.live_recorder import TennisLiveRecorder
from src.sports.tennis.mock_provider import MockProvider
from src.sports.tennis.state import TennisState
from src.sports.tennis.tennis_to_bundle import tennis_jsonl_to_bundle


def _market_snap(ticker: str = "KXATP-WIM26", mid: float = 55.0) -> dict:
    return {
        "market_id": ticker,
        "event_id": "MOCK-001",
        "timestamp": "2026-07-04T14:08:00Z",
        "yes_bid": mid - 1.0,
        "yes_ask": mid + 1.0,
        "no_bid": 100 - mid - 1.0,
        "no_ask": 100 - mid + 1.0,
        "last_price": mid,
        "volume": 500,
        "open_interest": 200,
        "liquidity_score": 0.75,
        "source": "mock",
    }


def _write_paired_jsonl(path: Path, n: int = 5, ticker: str = "KXATP-WIM26") -> None:
    provider = MockProvider(stream_ticks=n)
    with TennisLiveRecorder(path.parent) as rec:
        for state in provider.stream_match_states("MOCK-001"):
            rec.record_paired("MOCK-001", ticker, state, _market_snap(ticker))
    # The recorder writes into a date sub-directory; move to the desired path
    files = list(path.parent.rglob("*.jsonl"))
    if files and files[0] != path:
        files[0].rename(path)


def _write_raw_jsonl(path: Path, records: list) -> None:
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


class TestTennisJsonlToBundleBasic:
    def test_returns_replay_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.jsonl"
            _write_paired_jsonl(p, n=5)
            bundle = tennis_jsonl_to_bundle(p)
            assert isinstance(bundle, ReplayBundle)

    def test_sport_is_tennis(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.jsonl"
            _write_paired_jsonl(p, n=3)
            bundle = tennis_jsonl_to_bundle(p)
            assert bundle.sport == "tennis"

    def test_tick_count_matches_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.jsonl"
            _write_paired_jsonl(p, n=4)
            bundle = tennis_jsonl_to_bundle(p)
            assert len(bundle.ticks) == 4

    def test_has_tennis_state_flag_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.jsonl"
            _write_paired_jsonl(p, n=3)
            bundle = tennis_jsonl_to_bundle(p)
            assert bundle.source_metadata["has_tennis_state"] is True

    def test_no_missing_game_state_issue(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.jsonl"
            _write_paired_jsonl(p, n=3)
            bundle = tennis_jsonl_to_bundle(p)
            codes = [i.code for i in bundle.quality_report.issues]
            assert "MISSING_GAME_STATE" not in codes

    def test_verdict_pass_when_all_have_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.jsonl"
            _write_paired_jsonl(p, n=3)
            bundle = tennis_jsonl_to_bundle(p)
            assert bundle.quality_report.verdict == Verdict.PASS

    def test_ticker_in_source_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.jsonl"
            _write_paired_jsonl(p, n=2, ticker="KXATP-WIM26")
            bundle = tennis_jsonl_to_bundle(p, ticker="KXATP-WIM26")
            assert bundle.source_metadata["ticker"] == "KXATP-WIM26"

    def test_game_events_have_real_players(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.jsonl"
            _write_paired_jsonl(p, n=3)
            bundle = tennis_jsonl_to_bundle(p)
            for tick in bundle.ticks:
                assert tick.game_event.home_team not in ("UNKNOWN", "")

    def test_game_events_sets_a_in_home_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.jsonl"
            _write_paired_jsonl(p, n=3)
            bundle = tennis_jsonl_to_bundle(p)
            # MOCK-001 starts at sets 0-0
            first_tick = bundle.ticks[0]
            assert first_tick.game_event.home_score == 0

    def test_capture_mode_in_source_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.jsonl"
            _write_paired_jsonl(p, n=2)
            bundle = tennis_jsonl_to_bundle(p)
            assert bundle.source_metadata["capture_mode"] == "TENNIS_PAIRED"

    def test_saves_to_file_when_out_path_given(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.jsonl"
            out = Path(tmp) / "bundle.json"
            _write_paired_jsonl(p, n=2)
            tennis_jsonl_to_bundle(p, out_path=out)
            assert out.exists()

    def test_league_is_atp_for_mock_001(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.jsonl"
            _write_paired_jsonl(p, n=2)
            bundle = tennis_jsonl_to_bundle(p)
            assert bundle.league == "ATP"

    def test_tiebreak_tick_has_correct_period(self):
        """MOCK-003 is a tiebreak — period should include 'tiebreak'."""
        with tempfile.TemporaryDirectory() as tmp:
            provider = MockProvider(stream_ticks=2)
            p = Path(tmp) / "capture.jsonl"
            with open(p, "w") as f:
                for state in provider.stream_match_states("MOCK-003"):
                    snap = _market_snap()
                    record = {
                        "received_at": "2026-06-07T15:45:00Z",
                        "record_type": "paired",
                        "match_id": "MOCK-003",
                        "ticker": "KXWTA-RG26-F001",
                        "tennis_state": state.to_dict(),
                        "market_snapshot": snap,
                    }
                    f.write(json.dumps(record) + "\n")
            bundle = tennis_jsonl_to_bundle(p)
            for tick in bundle.ticks:
                assert "tiebreak" in tick.game_event.period


class TestTennisJsonlToBundlePartialState:
    def test_market_only_records_produce_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.jsonl"
            records = [
                {
                    "received_at": "2026-07-04T14:00:00Z",
                    "record_type": "market_only",
                    "ticker": "KXATP-WIM26",
                    "market_snapshot": _market_snap(),
                }
            ]
            _write_raw_jsonl(p, records)
            bundle = tennis_jsonl_to_bundle(p)
            assert bundle.ticks[0].game_event.status == "LIVE_UNKNOWN"

    def test_mixed_records_warns_partial_state(self):
        provider = MockProvider(stream_ticks=1)
        states = list(provider.stream_match_states("MOCK-001"))
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.jsonl"
            records = [
                {
                    "received_at": "2026-07-04T14:00:00Z",
                    "record_type": "paired",
                    "match_id": "MOCK-001",
                    "ticker": "KXATP-WIM26",
                    "tennis_state": states[0].to_dict(),
                    "market_snapshot": _market_snap(),
                },
                {
                    "received_at": "2026-07-04T14:01:00Z",
                    "record_type": "market_only",
                    "ticker": "KXATP-WIM26",
                    "market_snapshot": _market_snap(),
                },
            ]
            _write_raw_jsonl(p, records)
            bundle = tennis_jsonl_to_bundle(p)
            codes = [i.code for i in bundle.quality_report.issues]
            assert "PARTIAL_GAME_STATE" in codes

    def test_mixed_verdict_is_pass_with_warnings(self):
        provider = MockProvider(stream_ticks=1)
        states = list(provider.stream_match_states("MOCK-001"))
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.jsonl"
            records = [
                {
                    "received_at": "2026-07-04T14:00:00Z",
                    "record_type": "paired",
                    "match_id": "MOCK-001",
                    "ticker": "KXATP-WIM26",
                    "tennis_state": states[0].to_dict(),
                    "market_snapshot": _market_snap(),
                },
                {
                    "received_at": "2026-07-04T14:01:00Z",
                    "record_type": "market_only",
                    "ticker": "KXATP-WIM26",
                    "market_snapshot": _market_snap(),
                },
            ]
            _write_raw_jsonl(p, records)
            bundle = tennis_jsonl_to_bundle(p)
            assert bundle.quality_report.verdict == Verdict.PASS_WITH_WARNINGS


class TestTennisJsonlToBundleErrors:
    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            tennis_jsonl_to_bundle("/nonexistent/path.jsonl")

    def test_empty_file_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "empty.jsonl"
            p.write_text("")
            with pytest.raises(ValueError):
                tennis_jsonl_to_bundle(p)

    def test_no_usable_snapshots_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.jsonl"
            # Records with no market_snapshot at all
            records = [{"received_at": "2026-07-04T14:00:00Z", "record_type": "paired"}]
            _write_raw_jsonl(p, records)
            with pytest.raises(ValueError):
                tennis_jsonl_to_bundle(p)

    def test_invalid_json_lines_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "corrupt.jsonl"
            provider = MockProvider(stream_ticks=1)
            states = list(provider.stream_match_states("MOCK-001"))
            with open(p, "w") as f:
                f.write("NOT JSON AT ALL\n")
                f.write(json.dumps({
                    "received_at": "2026-07-04T14:00:00Z",
                    "record_type": "paired",
                    "match_id": "MOCK-001",
                    "ticker": "KXATP-WIM26",
                    "tennis_state": states[0].to_dict(),
                    "market_snapshot": _market_snap(),
                }) + "\n")
            bundle = tennis_jsonl_to_bundle(p)
            assert len(bundle.ticks) == 1
