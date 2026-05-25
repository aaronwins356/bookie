from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.sports.tennis.cli import main
from src.sports.tennis.live_recorder import TennisLiveRecorder
from src.sports.tennis.mock_provider import MockProvider


def _run(*args) -> int:
    return main(list(args))


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


def _make_paired_jsonl(path: Path, n: int = 3) -> None:
    provider = MockProvider(stream_ticks=n)
    records = []
    for state in provider.stream_match_states("MOCK-001"):
        records.append({
            "received_at": "2026-07-04T14:08:00Z",
            "record_type": "paired",
            "match_id": "MOCK-001",
            "ticker": "KXATP-WIM26",
            "tennis_state": state.to_dict(),
            "market_snapshot": _market_snap(),
        })
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


class TestNoCommand:
    def test_no_args_returns_1(self):
        assert _run() == 1


class TestListLive:
    def test_exits_0(self, capsys):
        rc = _run("list-live")
        assert rc == 0

    def test_shows_matches(self, capsys):
        _run("list-live")
        out = capsys.readouterr().out
        assert "MOCK-001" in out or "Djokovic" in out

    def test_shows_three_matches(self, capsys):
        _run("list-live")
        out = capsys.readouterr().out
        # Default MockProvider has 3 matches
        count = out.count("MOCK-")
        assert count >= 3


class TestPairMarkets:
    def test_exits_0_with_mock_markets(self):
        rc = _run("pair-markets", "--mock-markets")
        assert rc == 0

    def test_shows_accepted_pairs(self, capsys):
        _run("pair-markets", "--mock-markets")
        out = capsys.readouterr().out
        assert "ACCEPTED" in out or "REJECTED" in out

    def test_threshold_flag_accepted(self):
        rc = _run("pair-markets", "--mock-markets", "--threshold", "0.0")
        assert rc == 0

    def test_threshold_1_rejects_all(self):
        # threshold=1.0 means no pair is perfect → returns 1 (no accepted)
        rc = _run("pair-markets", "--mock-markets", "--threshold", "1.0")
        assert rc == 1

    def test_shows_confidence_scores(self, capsys):
        _run("pair-markets", "--mock-markets", "--threshold", "0.0")
        out = capsys.readouterr().out
        # Should contain some float confidence value
        import re
        assert re.search(r"\d\.\d{2}", out)


class TestRecordPaired:
    def test_unknown_match_id_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = _run(
                "record-paired",
                "--match-id", "NONEXISTENT",
                "--ticker", "KXATP-WIM26",
                "--seconds", "1",
                "--out", tmp,
            )
            assert rc == 1

    def test_valid_match_exits_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = _run(
                "record-paired",
                "--match-id", "MOCK-001",
                "--ticker", "KXATP-WIM26",
                "--seconds", "1",
                "--out", tmp,
            )
            assert rc == 0

    def test_creates_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            _run(
                "record-paired",
                "--match-id", "MOCK-001",
                "--ticker", "KXATP-WIM26",
                "--seconds", "1",
                "--out", tmp,
            )
            files = list(Path(tmp).rglob("*.jsonl"))
            assert len(files) >= 1


class TestBuildBundle:
    def test_missing_input_exits_1(self):
        rc = _run("build-bundle", "--input", "/nonexistent/path.jsonl")
        assert rc == 1

    def test_valid_input_exits_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.jsonl"
            _make_paired_jsonl(p, n=3)
            rc = _run("build-bundle", "--input", str(p))
            assert rc == 0

    def test_shows_bundle_info(self, capsys):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.jsonl"
            _make_paired_jsonl(p, n=3)
            _run("build-bundle", "--input", str(p))
            out = capsys.readouterr().out
            assert "tennis" in out.lower()
            assert "ticks" in out.lower()

    def test_saves_file_when_out_given(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.jsonl"
            out = Path(tmp) / "bundle.json"
            _make_paired_jsonl(p, n=3)
            _run("build-bundle", "--input", str(p), "--out", str(out))
            assert out.exists()

    def test_shows_verdict(self, capsys):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.jsonl"
            _make_paired_jsonl(p, n=3)
            _run("build-bundle", "--input", str(p))
            out = capsys.readouterr().out
            assert "PASS" in out or "WARNING" in out


class TestBacktestCapture:
    def test_missing_input_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = _run(
                "backtest-capture",
                "--input", "/nonexistent/path.jsonl",
                "--out", tmp,
            )
            assert rc == 1

    def test_valid_input_exits_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.jsonl"
            out_dir = Path(tmp) / "results"
            _make_paired_jsonl(p, n=5)
            rc = _run(
                "backtest-capture",
                "--input", str(p),
                "--out", str(out_dir),
            )
            assert rc == 0

    def test_creates_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.jsonl"
            out_dir = Path(tmp) / "results"
            _make_paired_jsonl(p, n=3)
            _run("backtest-capture", "--input", str(p), "--out", str(out_dir))
            assert out_dir.exists()

    def test_shows_pnl_and_fills(self, capsys):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "capture.jsonl"
            _make_paired_jsonl(p, n=5)
            _run("backtest-capture", "--input", str(p), "--out", tmp)
            out = capsys.readouterr().out
            assert "PnL" in out or "pnl" in out.lower()
