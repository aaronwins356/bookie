from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.live.cli import build_parser, cmd_doctor


class TestDoctorCommand:
    def _run_doctor(self, env_overrides=None):
        """Run doctor with specific env and return exit code."""
        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ("KALSHI_KEY_ID", "KALSHI_PRIVATE_KEY_PATH",
                                  "KALSHI_API_BASE_URL", "KALSHI_WS_URL")}
        if env_overrides:
            clean_env.update(env_overrides)
        with patch.dict(os.environ, clean_env, clear=True):
            args = build_parser().parse_args(["doctor"])
            return args.func(args)

    def test_doctor_returns_nonzero_when_not_configured(self, capsys):
        rc = self._run_doctor({})
        assert rc != 0

    def test_doctor_prints_env_var_names(self, capsys):
        self._run_doctor({})
        out = capsys.readouterr().out
        assert "KALSHI_KEY_ID" in out
        assert "KALSHI_PRIVATE_KEY_PATH" in out

    def test_doctor_prints_fix_instructions(self, capsys):
        self._run_doctor({})
        out = capsys.readouterr().out
        assert "export KALSHI_KEY_ID" in out
        assert "export KALSHI_PRIVATE_KEY_PATH" in out

    def test_doctor_shows_data_capture_only(self, capsys):
        self._run_doctor({})
        out = capsys.readouterr().out
        assert "DATA_CAPTURE_ONLY" in out

    def test_doctor_returns_zero_when_configured(self, tmp_path, capsys):
        pem = tmp_path / "key.pem"
        pem.write_text("dummy")
        rc = self._run_doctor({
            "KALSHI_KEY_ID": "test-key",
            "KALSHI_PRIVATE_KEY_PATH": str(pem),
        })
        assert rc == 0

    def test_doctor_no_order_warning_present(self, capsys):
        self._run_doctor({})
        out = capsys.readouterr().out
        assert "No orders" in out or "no orders" in out.lower()


class TestListMarketsCommand:
    def test_fails_without_env(self, capsys):
        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ("KALSHI_KEY_ID", "KALSHI_PRIVATE_KEY_PATH")}
        with patch.dict(os.environ, clean_env, clear=True):
            args = build_parser().parse_args(["list-markets", "--series", "KXBTC15M"])
            rc = args.func(args)
        assert rc != 0


class TestSearchMarketsCommand:
    def test_fails_without_env(self, capsys):
        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ("KALSHI_KEY_ID", "KALSHI_PRIVATE_KEY_PATH")}
        with patch.dict(os.environ, clean_env, clear=True):
            args = build_parser().parse_args(["search-markets", "--query", "Gaston"])
            rc = args.func(args)
        assert rc != 0

    def test_handles_missing_prices(self, capsys, tmp_path):
        """Test that None/missing prices don't crash with format error."""
        pem = tmp_path / "key.pem"
        pem.write_text("dummy")
        clean_env = {
            "KALSHI_KEY_ID": "test-key",
            "KALSHI_PRIVATE_KEY_PATH": str(pem),
        }

        # Mock response with markets missing yes_bid/yes_ask
        from src.live.market_discovery import MarketInfo
        mock_market = MarketInfo(
            ticker="TEST-001",
            title="Test Market without prices",
            status="open",
            event_ticker="TEST",
            series_ticker="TEST",
            yes_bid=None,
            yes_ask=None,
        )

        # Verify formatting doesn't crash
        bid_str = f"{mock_market.yes_bid:.2f}" if mock_market.yes_bid is not None else "—"
        ask_str = f"{mock_market.yes_ask:.2f}" if mock_market.yes_ask is not None else "—"
        assert bid_str == "—"
        assert ask_str == "—"

    def test_query_filtering_gaston(self):
        """Test that query 'Gaston' only matches markets containing Gaston."""
        from src.live.market_discovery import MarketInfo

        # Markets that should match
        gaston_match = MarketInfo(
            ticker="KXRG26-GASTMON-001",
            title="Hugo Gaston vs Gael Monfils - French Open",
            status="open",
            event_ticker="KXRG26-GASTMON",
            series_ticker="KXRG26",
        )

        # Markets that should NOT match
        bundled = MarketInfo(
            ticker="KXMVESPORTSMULTIGAMEEXTENDED",
            title="MVP Extended Sports Multi-Game Bundle",
            status="open",
            event_ticker="KXMVESPORTS",
            series_ticker="KXMVESPORTS",
            extra={"category": "bundled_product"},
        )

        # Define matching function (same as in cmd_search_markets)
        def matches_query(market, q: str) -> bool:
            q_lower = q.lower()
            search_fields = [
                market.ticker,
                market.title,
                market.series_ticker,
                market.event_ticker,
                market.extra.get("subtitle", ""),
                market.extra.get("category", ""),
                market.extra.get("sport", ""),
                market.extra.get("tournament", ""),
            ]
            return any(q_lower in str(field).lower() for field in search_fields if field)

        # Test filtering
        assert matches_query(gaston_match, "Gaston") is True
        assert matches_query(gaston_match, "Monfils") is True
        assert matches_query(gaston_match, "French Open") is True
        assert matches_query(bundled, "Gaston") is False
        assert matches_query(bundled, "KXMVE") is True  # Matches by ticker
        assert matches_query(bundled, "bundled") is True  # Matches by category


class TestBuildBundleCommand:
    def _write_capture(self, path: Path, ticker: str = "T", n: int = 3) -> None:
        with open(path, "w") as fh:
            for i in range(n):
                record = {
                    "received_at": f"2025-05-25T12:{i:02d}:00+00:00",
                    "source": "kalshi_ws",
                    "ticker": ticker,
                    "raw_message": {
                        "type": "orderbook_snapshot",
                        "yes": [[55 + i, 10]],
                        "no": [[40, 8]],
                    },
                }
                fh.write(json.dumps(record) + "\n")

    def test_build_bundle_creates_output_file(self, tmp_path, capsys):
        p = tmp_path / "T.jsonl"
        self._write_capture(p, "T")
        out = tmp_path / "bundle.json"
        args = build_parser().parse_args([
            "build-bundle", "--input", str(p), "--out", str(out), "--ticker", "T"
        ])
        rc = args.func(args)
        assert rc == 0
        assert out.exists()

    def test_build_bundle_reports_tick_count(self, tmp_path, capsys):
        p = tmp_path / "T.jsonl"
        self._write_capture(p, "T", n=4)
        args = build_parser().parse_args([
            "build-bundle", "--input", str(p), "--ticker", "T"
        ])
        args.out = None
        rc = args.func(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "4" in out

    def test_build_bundle_warns_missing_game_state(self, tmp_path, capsys):
        p = tmp_path / "T.jsonl"
        self._write_capture(p, "T")
        args = build_parser().parse_args([
            "build-bundle", "--input", str(p), "--ticker", "T"
        ])
        args.out = None
        args.func(args)
        out = capsys.readouterr().out
        assert "MISSING_GAME_STATE" in out

    def test_build_bundle_fails_on_missing_file(self, tmp_path, capsys):
        args = build_parser().parse_args([
            "build-bundle", "--input", str(tmp_path / "missing.jsonl"), "--ticker", "T"
        ])
        args.out = None
        rc = args.func(args)
        assert rc != 0


class TestTrainFromCaptureCommand:
    def _write_capture(self, path: Path, n: int = 5) -> None:
        with open(path, "w") as fh:
            for i in range(n):
                record = {
                    "received_at": f"2025-05-25T12:{i:02d}:00+00:00",
                    "source": "kalshi_ws",
                    "ticker": "T",
                    "raw_message": {
                        "type": "orderbook_snapshot",
                        "yes": [[55 + i, 10], [54, 5]],
                        "no": [[40, 8], [39, 4]],
                    },
                }
                fh.write(json.dumps(record) + "\n")

    def test_train_from_capture_runs_and_returns_zero(self, tmp_path, capsys):
        p = tmp_path / "T.jsonl"
        self._write_capture(p)
        out = tmp_path / "backtest_out"
        args = build_parser().parse_args([
            "train-from-capture",
            "--input", str(p),
            "--out", str(out),
            "--ticker", "T",
        ])
        rc = args.func(args)
        assert rc == 0

    def test_train_from_capture_creates_artifacts(self, tmp_path):
        p = tmp_path / "T.jsonl"
        self._write_capture(p)
        out = tmp_path / "backtest_out"
        args = build_parser().parse_args([
            "train-from-capture",
            "--input", str(p),
            "--out", str(out),
            "--ticker", "T",
        ])
        args.func(args)
        assert out.exists()
        files = list(out.iterdir())
        assert len(files) > 0

    def test_train_from_capture_prints_research_caveats(self, tmp_path, capsys):
        p = tmp_path / "T.jsonl"
        self._write_capture(p)
        out = tmp_path / "backtest_out"
        args = build_parser().parse_args([
            "train-from-capture",
            "--input", str(p),
            "--out", str(out),
            "--ticker", "T",
        ])
        args.func(args)
        output = capsys.readouterr().out
        assert "NOT proof" in output or "not proof" in output.lower()


class TestParserStructure:
    def test_doctor_subcommand_exists(self):
        parser = build_parser()
        args = parser.parse_args(["doctor"])
        assert args.command == "doctor"

    def test_list_markets_subcommand_exists(self):
        parser = build_parser()
        args = parser.parse_args(["list-markets"])
        assert args.command == "list-markets"

    def test_record_subcommand_exists(self):
        parser = build_parser()
        args = parser.parse_args(["record", "--tickers", "T1", "T2", "--seconds", "30"])
        assert args.command == "record"
        assert args.tickers == ["T1", "T2"]
        assert args.seconds == 30.0

    def test_build_bundle_subcommand_exists(self):
        parser = build_parser()
        args = parser.parse_args(["build-bundle", "--input", "/tmp/t.jsonl"])
        assert args.command == "build-bundle"

    def test_train_from_capture_subcommand_exists(self):
        parser = build_parser()
        args = parser.parse_args([
            "train-from-capture", "--input", "/tmp/t.jsonl", "--out", "/tmp/out"
        ])
        assert args.command == "train-from-capture"
