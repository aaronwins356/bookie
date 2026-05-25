from __future__ import annotations

"""
Tennis live pairing CLI.

Commands:
  list-live           List live tennis matches from the score provider
  pair-markets        Find Kalshi markets that pair with live tennis matches
  record-paired       Record one paired (match, market) for N seconds
  build-bundle        Convert a paired JSONL capture to a ReplayBundle
  backtest-capture    Run backtest pipeline on a paired capture

Examples:
  python -m src.sports.tennis.cli list-live
  python -m src.sports.tennis.cli pair-markets --status open
  python -m src.sports.tennis.cli record-paired --match-id MOCK-001 --ticker KXATP-WIM26 --seconds 60
  python -m src.sports.tennis.cli build-bundle --input data/live/tennis/2026-07-04/MOCK-001__KXATP-WIM26.jsonl --out data/replays/bundle.json
  python -m src.sports.tennis.cli backtest-capture --input data/live/tennis/2026-07-04/MOCK-001__KXATP-WIM26.jsonl --out data/backtests/tennis_check

IMPORTANT: This CLI is DATA_CAPTURE_ONLY. No orders are placed.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DIVIDER = "=" * 64
MODE = "DATA_CAPTURE_ONLY"


# ---------------------------------------------------------------------------
# list-live
# ---------------------------------------------------------------------------

def cmd_list_live(args: argparse.Namespace) -> int:
    provider = _make_provider(args)

    matches = provider.list_live_matches()
    print(f"\n{DIVIDER}")
    print(f"  LIVE TENNIS MATCHES ({len(matches)} found)")
    print(DIVIDER)
    if not matches:
        print("  (none)")
    for m in matches:
        start = m.scheduled_start or "unknown"
        print(
            f"  {m.match_id:<12} {m.tour.value:<10} {m.surface.value:<8} "
            f"{m.status:<12} {m.player_a} vs {m.player_b} — {m.tournament}"
        )
        print(f"              start={start}")
    print()
    return 0


# ---------------------------------------------------------------------------
# pair-markets
# ---------------------------------------------------------------------------

def cmd_pair_markets(args: argparse.Namespace) -> int:
    provider = _make_provider(args)
    matches = provider.list_live_matches()

    if not matches:
        print("No live matches found from provider.", file=sys.stderr)
        return 1

    try:
        markets = _fetch_markets(args)
    except Exception as exc:
        print(f"Could not fetch markets: {exc}", file=sys.stderr)
        print("Tip: set KALSHI_KEY_ID / KALSHI_PRIVATE_KEY_PATH or use --mock-markets", file=sys.stderr)
        return 1

    from src.sports.tennis.match_pairing import pair_matches_to_markets
    threshold = getattr(args, "threshold", 0.55)
    accepted, rejected = pair_matches_to_markets(matches, markets, threshold=threshold)

    print(f"\n{DIVIDER}")
    print(f"  TENNIS ↔ KALSHI MARKET PAIRING")
    print(DIVIDER)
    print(f"  matches       : {len(matches)}")
    print(f"  markets       : {len(markets)}")
    print(f"  threshold     : {threshold}")
    print(f"  accepted      : {len(accepted)}")
    print(f"  rejected      : {len(rejected)}")

    if accepted:
        print("\n  ACCEPTED PAIRS:")
        for p in accepted:
            print(f"    [{p.confidence:.2f}] {p.match.player_a} vs {p.match.player_b} ↔ {p.market.ticker}")
            for r in p.reasons:
                print(f"           {r}")

    if rejected:
        print("\n  REJECTED:")
        for r in rejected:
            print(f"    [{r.best_confidence:.2f}] {r.match.player_a} vs {r.match.player_b} — {r.reason}")

    print()
    return 0 if accepted else 1


# ---------------------------------------------------------------------------
# record-paired
# ---------------------------------------------------------------------------

def cmd_record_paired(args: argparse.Namespace) -> int:
    match_id = args.match_id
    ticker = args.ticker
    seconds = args.seconds
    out_base = Path(args.out) if args.out else Path("data/live/tennis")

    provider = _make_provider(args)

    from src.sports.tennis.live_feed import TennisLiveFeed
    from src.sports.tennis.live_recorder import TennisLiveRecorder

    feed = TennisLiveFeed(provider)

    # Build a synthetic market snapshot (real implementation would
    # pull from Kalshi WS; here we create a placeholder so the CLI
    # works with the mock provider without Kalshi connectivity)
    def _mock_market_snap(ts: str) -> dict:
        return {
            "market_id": ticker,
            "event_id": match_id,
            "timestamp": ts,
            "yes_bid": 48.0,
            "yes_ask": 52.0,
            "no_bid": 48.0,
            "no_ask": 52.0,
            "last_price": 50.0,
            "volume": 0,
            "open_interest": 0,
            "liquidity_score": 0.5,
            "source": "mock",
        }

    import time
    start = time.monotonic()
    count = 0
    poll = max(0.5, seconds / 20.0)  # aim for ~20 ticks max in test mode

    print(f"\n{DIVIDER}")
    print(f"  RECORDING: {match_id} ↔ {ticker}")
    print(f"  duration: {seconds}s  poll: {poll:.1f}s  out: {out_base}")
    print(f"  mode: {MODE} — NO ORDERS WILL BE PLACED")
    print(DIVIDER)

    with TennisLiveRecorder(out_base) as recorder:
        try:
            for state, ts in feed.stream(match_id, poll_interval=poll):
                if time.monotonic() - start >= seconds:
                    break
                snap = _mock_market_snap(ts)
                recorder.record_paired(match_id, ticker, state, snap)
                count += 1
                print(
                    f"  [{count:3d}] {ts} "
                    f"sets={state.sets_a}-{state.sets_b} "
                    f"games={state.games_a}-{state.games_b} "
                    f"pts={state.points_a}-{state.points_b}"
                )
        except KeyError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    print(f"\n  Recorded {count} ticks to {out_base}")
    print()
    return 0


# ---------------------------------------------------------------------------
# build-bundle
# ---------------------------------------------------------------------------

def cmd_build_bundle(args: argparse.Namespace) -> int:
    from src.sports.tennis.tennis_to_bundle import tennis_jsonl_to_bundle

    input_path = Path(args.input)
    out_path = Path(args.out) if args.out else None
    ticker = getattr(args, "ticker", None)

    if not input_path.exists():
        print(f"error: input file not found: {input_path}", file=sys.stderr)
        return 1

    try:
        bundle = tennis_jsonl_to_bundle(input_path, out_path=out_path, ticker=ticker)
    except Exception as exc:
        print(f"error building bundle: {exc}", file=sys.stderr)
        return 1

    print(f"\n{DIVIDER}")
    print("  TENNIS BUNDLE BUILD")
    print(DIVIDER)
    print(f"  bundle_id     : {bundle.bundle_id}")
    print(f"  sport         : {bundle.sport}")
    print(f"  league        : {bundle.league}")
    print(f"  ticks         : {len(bundle.ticks)}")
    print(f"  verdict       : {bundle.quality_report.verdict.value}")
    print(f"  has_tennis    : {bundle.source_metadata.get('has_tennis_state')}")
    if out_path:
        print(f"  saved to      : {out_path}")

    qr = bundle.quality_report
    if qr.issues:
        print("\n  QUALITY ISSUES:")
        for issue in qr.issues:
            print(f"    [{issue.severity.value}] {issue.code}: {issue.message}")
    print()
    return 0


# ---------------------------------------------------------------------------
# backtest-capture
# ---------------------------------------------------------------------------

def cmd_backtest_capture(args: argparse.Namespace) -> int:
    from src.sports.tennis.tennis_to_bundle import tennis_jsonl_to_bundle
    from src.backtest.batch import BatchRunner, export_batch
    from src.backtest.config import BacktestConfig

    input_path = Path(args.input)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"error: input not found: {input_path}", file=sys.stderr)
        return 1

    print(f"\n{DIVIDER}")
    print("  TENNIS CAPTURE BACKTEST")
    print(DIVIDER)
    print(f"  input  : {input_path}")
    print(f"  out    : {out_dir}")
    print(f"  mode   : {MODE}")

    # Step 1: build bundle
    bundle_path = out_dir / "tennis_capture_bundle.json"
    try:
        bundle = tennis_jsonl_to_bundle(input_path, out_path=bundle_path)
    except Exception as exc:
        print(f"error building bundle: {exc}", file=sys.stderr)
        return 1

    has_state = bundle.source_metadata.get("has_tennis_state", False)
    print(f"  ticks  : {len(bundle.ticks)}")
    print(f"  has_tennis_state: {has_state}")

    # Step 2: batch backtest
    configs = [
        BacktestConfig(name=f"tennis_capture_s{s}", seed=s, bundle_path=str(bundle_path))
        for s in [1, 2, 3]
    ]
    runner = BatchRunner(compute_robustness=True)
    batch = runner.run(configs, batch_id="tennis_capture")
    export_batch(batch, str(out_dir))

    agg = batch.aggregate_metrics
    print(f"\n  RESULTS:")
    print(f"  total PnL     : {agg.get('total_pnl_cents', 0):+.2f}c")
    print(f"  fills         : {agg.get('total_fills', 0)}")
    print(f"  verdict       : {bundle.quality_report.verdict.value}")
    print("\n  RESEARCH CAVEATS:")
    print("  - Results are NOT proof of live edge.")
    if not has_state:
        print("  - Game state absent — score-dependent strategies have no signal.")
    print()
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(args: argparse.Namespace):
    from src.sports.tennis.mock_provider import MockProvider
    return MockProvider()


def _fetch_markets(args: argparse.Namespace):
    """
    Fetch Kalshi markets. Uses mock markets when Kalshi env is not configured.
    In live mode, requires KALSHI_KEY_ID and KALSHI_PRIVATE_KEY_PATH.
    """
    use_mock = getattr(args, "mock_markets", False)
    if use_mock:
        return _mock_markets()

    from src.live.env import load_env, validate_env
    env = load_env()
    problems = validate_env(env)
    if problems:
        return _mock_markets()

    from src.live.kalshi_auth import KalshiSigner
    from src.live.kalshi_rest import KalshiRestClient
    from src.live.market_discovery import search_markets

    signer = KalshiSigner(env.key_id, env.private_key_path)
    client = KalshiRestClient(env, signer)
    status = getattr(args, "status", "open")
    return search_markets(client, status=status, sport="tennis")


def _mock_markets():
    """Return mock Kalshi market objects for demo/test without live credentials."""
    from src.live.market_discovery import MarketInfo
    return [
        MarketInfo(
            ticker="KXATP-WIM26-SF001",
            title="Djokovic to win vs Alcaraz - Wimbledon SF",
            status="open",
            event_ticker="KXATP-WIM26-SF",
            series_ticker="KXATP",
            yes_bid=48.0,
            yes_ask=52.0,
            volume=1200,
        ),
        MarketInfo(
            ticker="KXATP-USO26-QF002",
            title="Sinner vs Zverev US Open Men's QF",
            status="open",
            event_ticker="KXATP-USO26-QF",
            series_ticker="KXATP",
            yes_bid=55.0,
            yes_ask=59.0,
            volume=800,
        ),
        MarketInfo(
            ticker="KXWTA-RG26-F001",
            title="Swiatek vs Sabalenka Roland Garros Women's Final",
            status="open",
            event_ticker="KXWTA-RG26-F",
            series_ticker="KXWTA",
            yes_bid=44.0,
            yes_ask=48.0,
            volume=2100,
        ),
    ]


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.sports.tennis.cli",
        description="Tennis live pairing — DATA_CAPTURE_ONLY, no orders",
    )
    sub = parser.add_subparsers(dest="command")

    # list-live
    ll = sub.add_parser("list-live", help="list live tennis matches from provider")
    ll.set_defaults(func=cmd_list_live)

    # pair-markets
    pm = sub.add_parser("pair-markets", help="pair live matches to Kalshi markets")
    pm.add_argument("--status", default="open", help="Kalshi market status filter")
    pm.add_argument("--threshold", type=float, default=0.55, help="min confidence to accept pair")
    pm.add_argument("--mock-markets", action="store_true", help="use built-in mock markets (no Kalshi auth)")
    pm.set_defaults(func=cmd_pair_markets)

    # record-paired
    rp = sub.add_parser("record-paired", help="record one paired match+market")
    rp.add_argument("--match-id", required=True, help="match ID from provider")
    rp.add_argument("--ticker", required=True, help="Kalshi ticker to record alongside")
    rp.add_argument("--seconds", type=int, default=300, help="recording duration in seconds")
    rp.add_argument("--out", default="data/live/tennis", help="base output directory")
    rp.set_defaults(func=cmd_record_paired)

    # build-bundle
    bb = sub.add_parser("build-bundle", help="convert paired JSONL to ReplayBundle")
    bb.add_argument("--input", required=True, help="JSONL capture file")
    bb.add_argument("--out", default=None, help="output bundle path (.json)")
    bb.add_argument("--ticker", default=None, help="override ticker name")
    bb.set_defaults(func=cmd_build_bundle)

    # backtest-capture
    bc = sub.add_parser("backtest-capture", help="backtest a paired capture")
    bc.add_argument("--input", required=True, help="JSONL capture file")
    bc.add_argument("--out", default="data/backtests/tennis_capture_check", help="output dir")
    bc.set_defaults(func=cmd_backtest_capture)

    return parser


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
