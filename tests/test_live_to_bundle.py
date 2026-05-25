from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.live.live_to_bundle import jsonl_to_bundle, _make_placeholder_game


class TestMakePlaceholderGame:
    def test_status_is_live_unknown(self):
        game = _make_placeholder_game("TICKER", "2025-01-01T00:00:00+00:00")
        assert game.status == "LIVE_UNKNOWN"

    def test_sport_is_unknown(self):
        game = _make_placeholder_game("TICKER", "2025-01-01T00:00:00+00:00")
        assert game.sport == "UNKNOWN"

    def test_event_id_is_ticker(self):
        game = _make_placeholder_game("MY-TICKER", "ts")
        assert game.event_id == "MY-TICKER"

    def test_scores_are_zero(self):
        game = _make_placeholder_game("T", "ts")
        assert game.home_score == 0
        assert game.away_score == 0


def _write_orderbook_jsonl(path: Path, ticker: str, n: int = 3) -> None:
    """Write n orderbook JSONL records with valid yes/no bids."""
    with open(path, "w") as fh:
        for i in range(n):
            record = {
                "received_at": f"2025-05-25T12:{i:02d}:00+00:00",
                "source": "kalshi_ws",
                "ticker": ticker,
                "raw_message": {
                    "type": "orderbook_snapshot",
                    "yes": [[55 + i, 10], [54, 5]],
                    "no": [[40, 8], [39, 4]],
                },
            }
            fh.write(json.dumps(record) + "\n")


def _write_ticker_jsonl(path: Path, ticker: str, n: int = 3) -> None:
    """Write n ticker-style JSONL records with yes_bid/yes_ask fields."""
    with open(path, "w") as fh:
        for i in range(n):
            record = {
                "received_at": f"2025-05-25T12:{i:02d}:00+00:00",
                "source": "kalshi_ws",
                "ticker": ticker,
                "raw_message": {
                    "msg": {
                        "yes_bid": 55.0 + i,
                        "yes_ask": 65.0 + i,
                        "no_bid": 35.0,
                        "no_ask": 45.0,
                        "volume": 100 + i,
                        "open_interest": 50,
                    }
                },
            }
            fh.write(json.dumps(record) + "\n")


class TestJsonlToBundle:
    def test_raises_on_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            jsonl_to_bundle(tmp_path / "nonexistent.jsonl", ticker="T")

    def test_raises_on_empty_file(self, tmp_path):
        p = tmp_path / "empty.jsonl"
        p.write_text("")
        with pytest.raises(ValueError, match="No records"):
            jsonl_to_bundle(p, ticker="T")

    def test_raises_when_no_parseable_snapshots(self, tmp_path):
        p = tmp_path / "garbage.jsonl"
        p.write_text('{"received_at": "ts", "raw_message": "garbage"}\n')
        with pytest.raises(ValueError, match="No usable"):
            jsonl_to_bundle(p, ticker="T")

    def test_bundle_has_correct_ticker_event_id(self, tmp_path):
        p = tmp_path / "MYTEST.jsonl"
        _write_orderbook_jsonl(p, "MYTEST", n=3)
        bundle = jsonl_to_bundle(p, ticker="MYTEST")
        assert bundle.event_id == "MYTEST"

    def test_bundle_tick_count_matches_records(self, tmp_path):
        p = tmp_path / "T.jsonl"
        _write_orderbook_jsonl(p, "T", n=5)
        bundle = jsonl_to_bundle(p, ticker="T")
        assert len(bundle.ticks) == 5

    def test_quality_report_warns_missing_game_state(self, tmp_path):
        p = tmp_path / "T.jsonl"
        _write_orderbook_jsonl(p, "T", n=2)
        bundle = jsonl_to_bundle(p, ticker="T")
        qr = bundle.quality_report
        assert qr is not None
        codes = [issue.code for issue in qr.issues]
        assert "MISSING_GAME_STATE" in codes

    def test_ticks_have_missing_game_state_metadata(self, tmp_path):
        p = tmp_path / "T.jsonl"
        _write_orderbook_jsonl(p, "T", n=2)
        bundle = jsonl_to_bundle(p, ticker="T")
        for tick in bundle.ticks:
            assert tick.metadata.get("missing_game_state") is True

    def test_placeholder_game_has_live_unknown_status(self, tmp_path):
        p = tmp_path / "T.jsonl"
        _write_orderbook_jsonl(p, "T", n=2)
        bundle = jsonl_to_bundle(p, ticker="T")
        for tick in bundle.ticks:
            assert tick.game_event.status == "LIVE_UNKNOWN"

    def test_verdict_is_pass_with_warnings(self, tmp_path):
        p = tmp_path / "T.jsonl"
        _write_orderbook_jsonl(p, "T", n=2)
        bundle = jsonl_to_bundle(p, ticker="T")
        from src.data.schemas import Verdict
        assert bundle.quality_report.verdict == Verdict.PASS_WITH_WARNINGS

    def test_saves_bundle_to_file(self, tmp_path):
        p = tmp_path / "T.jsonl"
        _write_orderbook_jsonl(p, "T", n=2)
        out = tmp_path / "bundle.json"
        jsonl_to_bundle(p, ticker="T", out_path=out)
        assert out.exists()
        data = json.loads(out.read_text())
        assert "ticks" in data
        assert "bundle_id" in data

    def test_ticker_inferred_from_filename(self, tmp_path):
        p = tmp_path / "MYTICKER.jsonl"
        _write_orderbook_jsonl(p, "MYTICKER", n=2)
        bundle = jsonl_to_bundle(p)  # no explicit ticker
        assert bundle.event_id == "MYTICKER"

    def test_ticker_style_records_parsed(self, tmp_path):
        p = tmp_path / "T.jsonl"
        _write_ticker_jsonl(p, "T", n=3)
        bundle = jsonl_to_bundle(p, ticker="T")
        assert len(bundle.ticks) == 3

    def test_source_metadata_has_capture_mode(self, tmp_path):
        p = tmp_path / "T.jsonl"
        _write_orderbook_jsonl(p, "T", n=2)
        bundle = jsonl_to_bundle(p, ticker="T")
        assert bundle.source_metadata.get("capture_mode") == "DATA_CAPTURE_ONLY"

    def test_market_snapshots_have_correct_ask_derivation(self, tmp_path):
        """yes_ask should be 100 - best_no_bid in the output snapshots."""
        p = tmp_path / "T.jsonl"
        _write_orderbook_jsonl(p, "T", n=1)
        bundle = jsonl_to_bundle(p, ticker="T")
        snap = bundle.ticks[0].market_snapshot
        # Our test data has no_bids = [[40, 8], [39, 4]], best = 40
        assert snap.yes_ask == pytest.approx(100.0 - 40.0)
