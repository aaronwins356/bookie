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


class TestPlayerBasedDiscovery:
    def test_extract_atp_tickers_recursive_from_strings(self):
        """Test recursive ATP ticker extraction from market objects."""
        from src.sports.tennis.cli import _extract_atp_tickers_recursive

        markets = [
            {
                "ticker": "KXATP-WIM26",
                "title": "Some market with KXATPMATCH-26MAY25GASMON-GAS embedded",
                "extra": {
                    "description": "Contains KXATPMATCH-26MAY25UNKNOWN-UNK",
                }
            },
        ]

        tickers = _extract_atp_tickers_recursive(markets)
        assert "KXATPMATCH-26MAY25GASMON-GAS" in tickers
        assert "KXATPMATCH-26MAY25UNKNOWN-UNK" in tickers

    def test_extract_atp_tickers_recursive_from_nested(self):
        """Test recursive extraction from deeply nested structures."""
        from src.sports.tennis.cli import _extract_atp_tickers_recursive

        markets = [
            {
                "ticker": "KXMVESPORTS",
                "custom_strike": {
                    "associated_markets": [
                        {"ticker": "KXATPMATCH-26MAY25TEST-TST"},
                        {"ticker": "KXATPMATCH-26MAY25TEST2-TS2"},
                    ]
                }
            }
        ]

        tickers = _extract_atp_tickers_recursive(markets)
        assert len(tickers) == 2
        assert "KXATPMATCH-26MAY25TEST-TST" in tickers
        assert "KXATPMATCH-26MAY25TEST2-TS2" in tickers

    def test_discover_markets_by_players_generates_queries(self):
        """Test that player-based discovery generates correct search queries."""
        from src.sports.tennis.provider_base import TennisMatchInfo, Tour, Surface
        from src.live.market_discovery import MarketInfo
        from unittest.mock import MagicMock, patch

        # Create a mock match for Gaston vs Monfils
        match = TennisMatchInfo(
            match_id="test-gaston-monfils",
            player_a="Hugo Gaston",
            player_b="Gael Monfils",
            tournament="Roland Garros 2026",
            tour=Tour.ATP,
            surface=Surface.CLAY,
            status="live",
        )

        # Mock client
        client = MagicMock()

        # Mock get_market to return the actual Gaston vs Monfils market
        client.get_market.return_value = {
            "ticker": "KXATPMATCH-26MAY25GASMON-GAS",
            "title": "Hugo Gaston vs Gael Monfils French Open",
            "status": "open",
            "event_ticker": "KXATPMATCH-26MAY25GASMON",
            "series_ticker": "KXATP",
            "yes_bid": 4800,
            "yes_ask": 5200,
            "volume": 500,
            "open_interest": 200,
        }

        # Track queries passed to search_markets
        queries_tried = []

        def mock_search_markets(client, query=None, status=None, **kwargs):
            queries_tried.append(query)
            if query in ("Hugo Gaston", "Gaston", "Gael Monfils", "Monfils", "Roland Garros 2026"):
                return [
                    MarketInfo(
                        ticker="KXMVESPORTSMULTIGAMEEXTENDED",
                        title=f"MVP Extended Sports Multi-Game Bundle with KXATPMATCH-26MAY25GASMON-GAS {query}",
                        status="open",
                        event_ticker="KXMVESPORTS",
                        series_ticker="KXMVESPORTS",
                    )
                ]
            return []

        # Patch search_markets at the module level where it's imported
        with patch("src.live.market_discovery.search_markets", side_effect=mock_search_markets):
            from src.sports.tennis.cli import _discover_markets_by_players
            markets = _discover_markets_by_players(client, [match], verbose=False)

            # Verify that queries were generated for player names
            assert "Hugo Gaston" in queries_tried or "Gaston" in queries_tried
            assert "Gael Monfils" in queries_tried or "Monfils" in queries_tried


class TestHydrationAndPairing:
    def test_hydrate_atp_market_from_ticker(self):
        """Test that ATP market hydration parses market dict to MarketInfo."""
        from src.sports.tennis.cli import _hydrate_atp_markets
        from src.live.market_discovery import MarketInfo
        from unittest.mock import MagicMock

        client = MagicMock()
        client.get_market.return_value = {
            "ticker": "KXATPMATCH-26MAY25GASMON-GAS",
            "title": "Gaston vs Monfils French Open",
            "status": "open",
            "event_ticker": "KXATPMATCH-26MAY25GASMON",
            "series_ticker": "KXATP",
            "yes_bid": 4800,  # in cents
            "yes_ask": 5200,
            "volume": 500,
            "open_interest": 200,
        }

        hydrated = _hydrate_atp_markets(client, ["KXATPMATCH-26MAY25GASMON-GAS"])

        assert len(hydrated) == 1
        assert hydrated[0].ticker == "KXATPMATCH-26MAY25GASMON-GAS"
        assert hydrated[0].title == "Gaston vs Monfils French Open"
        assert hydrated[0].yes_bid == 48.0  # converted from cents
        assert hydrated[0].yes_ask == 52.0

    def test_hydrate_deduplicates_tickers(self):
        """Test that duplicate ATP tickers are dedupped."""
        from src.sports.tennis.cli import _hydrate_atp_markets
        from unittest.mock import MagicMock

        client = MagicMock()
        client.get_market.return_value = {
            "ticker": "KXATPMATCH-26MAY25GASMON-GAS",
            "title": "Gaston vs Monfils French Open",
            "status": "open",
            "event_ticker": "KXATPMATCH-26MAY25GASMON",
            "series_ticker": "KXATP",
            "yes_bid": 4800,
            "yes_ask": 5200,
        }

        # Pass same ticker twice
        hydrated = _hydrate_atp_markets(client, [
            "KXATPMATCH-26MAY25GASMON-GAS",
            "KXATPMATCH-26MAY25GASMON-GAS",
        ])

        # Should only hydrate once (deduplicated)
        assert len(hydrated) == 1
        assert client.get_market.call_count == 2

    def test_hydrate_handles_failed_tickers(self):
        """Test that hydration continues on API failures."""
        from src.sports.tennis.cli import _hydrate_atp_markets
        from unittest.mock import MagicMock

        client = MagicMock()
        # First ticker fails, second succeeds
        client.get_market.side_effect = [
            RuntimeError("API error"),
            {
                "ticker": "KXATPMATCH-26MAY25UNKNOWN-UNK",
                "title": "Unknown Match",
                "status": "open",
                "event_ticker": "KXATPMATCH-26MAY25UNKNOWN",
                "series_ticker": "KXATP",
                "yes_bid": 4800,
                "yes_ask": 5200,
            },
        ]

        hydrated = _hydrate_atp_markets(client, [
            "KXATPMATCH-BAD-TICKER",
            "KXATPMATCH-26MAY25UNKNOWN-UNK",
        ])

        # Should have 1 hydrated market (the successful one)
        assert len(hydrated) == 1
        assert hydrated[0].ticker == "KXATPMATCH-26MAY25UNKNOWN-UNK"

    def test_pair_markets_gets_hydrated_markets(self, capsys):
        """Test that pair-markets reports hydrated market count."""
        # This is an integration test that uses mock markets
        rc = _run("pair-markets", "--mock-markets")
        out = capsys.readouterr().out + capsys.readouterr().err

        # With mock markets, we should see market count reported
        assert "markets" in out.lower()

    def test_extract_and_hydrate_atp_markets_workflow(self):
        """Test the full extraction and hydration workflow for ATP markets."""
        from src.sports.tennis.cli import _extract_atp_tickers_recursive, _hydrate_atp_markets
        from unittest.mock import MagicMock

        # Simulate raw API search results with embedded ATP tickers in various fields
        search_results = [
            {
                "ticker": "KXMVESPORTSMULTIGAMEEXTENDED",
                "title": "Sports Bundle with KXATPMATCH-03JUL26FEDNAD-FED",
                "status": "open",
                "event_ticker": "KXMVESPORTS",
                "series_ticker": "KXMVESPORTS",
                "custom_strike": {
                    "associated_markets": [
                        {"market_ticker": "KXATPMATCH-03JUL26DJOTIM-DJO"}
                    ]
                }
            }
        ]

        # Extract ATP tickers
        tickers = _extract_atp_tickers_recursive(search_results)
        assert len(tickers) == 2
        assert "KXATPMATCH-03JUL26FEDNAD-FED" in tickers
        assert "KXATPMATCH-03JUL26DJOTIM-DJO" in tickers

        # Mock hydration
        client = MagicMock()

        def get_market_side_effect(ticker):
            markets = {
                "KXATPMATCH-03JUL26FEDNAD-FED": {
                    "ticker": "KXATPMATCH-03JUL26FEDNAD-FED",
                    "title": "Roger Federer vs Rafael Nadal Wimbledon",
                    "status": "open",
                    "event_ticker": "KXATPMATCH-03JUL26FEDNAD",
                    "series_ticker": "KXATP",
                    "yes_bid": 5000,
                    "yes_ask": 5500,
                },
                "KXATPMATCH-03JUL26DJOTIM-DJO": {
                    "ticker": "KXATPMATCH-03JUL26DJOTIM-DJO",
                    "title": "Novak Djokovic vs Jannik Sinner Wimbledon",
                    "status": "open",
                    "event_ticker": "KXATPMATCH-03JUL26DJOTIM",
                    "series_ticker": "KXATP",
                    "yes_bid": 4800,
                    "yes_ask": 5200,
                }
            }
            return markets.get(ticker, {})

        client.get_market.side_effect = get_market_side_effect

        # Hydrate the tickers
        hydrated = _hydrate_atp_markets(client, tickers)
        assert len(hydrated) == 2
        assert any(m.ticker == "KXATPMATCH-03JUL26FEDNAD-FED" for m in hydrated)
        assert any(m.ticker == "KXATPMATCH-03JUL26DJOTIM-DJO" for m in hydrated)


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
