from __future__ import annotations

"""
Live data capture CLI — DATA_CAPTURE_ONLY. No orders.

Commands:
  doctor              Check environment and dependencies
  list-markets        List/search open Kalshi markets
  record              Record live WS data to JSONL
  build-bundle        Convert JSONL capture to ReplayBundle
  train-from-capture  Convert capture -> bundle -> backtest -> report

Examples:
  python -m src.live.cli doctor
  python -m src.live.cli list-markets --series KXBTC15M --status open
  python -m src.live.cli record --tickers KXBTC15M-25MAY-T32000 --seconds 60 --out data/live
  python -m src.live.cli build-bundle --input data/live/2025-05-25/KXBTC15M-25MAY-T32000.jsonl --out data/live/bundle.json
  python -m src.live.cli train-from-capture --input data/live/2025-05-25/KXBTC15M-25MAY-T32000.jsonl --out data/backtests/live_capture_check
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from src.live import MODE
from src.live.env import LiveEnv, check_live_deps, load_env, validate_env

DIVIDER = "=" * 64


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------
def cmd_doctor(args: argparse.Namespace) -> int:
    env = load_env()
    problems = validate_env(env)
    missing_deps = check_live_deps()

    print(f"\n{DIVIDER}")
    print("  BOOKIE LIVE DATA CAPTURE — SYSTEM DOCTOR")
    print(DIVIDER)
    print(f"  mode            : {MODE}")

    print("\nENVIRONMENT")
    _print_env_status(env)

    print("\nDEPENDENCIES")
    for dep in ("cryptography", "requests", "websockets"):
        status = "MISSING — pip install " + dep if dep in missing_deps else "OK"
        print(f"  {dep:<20} : {status}")

    all_ok = not problems and not missing_deps
    print("\nDIAGNOSIS")
    if all_ok:
        print("  OK — environment is configured for live data capture.")
    else:
        print("  NOT CONFIGURED — fix the issues below before recording:")
        for p in problems:
            print(f"    [!] {p}")
        for d in missing_deps:
            print(f"    [!] missing dependency: {d}")
        print()
        print("  TO SET ENVIRONMENT VARIABLES:")
        print('    export KALSHI_KEY_ID="your-key-id-from-kalshi-dashboard"')
        print('    export KALSHI_PRIVATE_KEY_PATH="/path/to/your/rsa-key.pem"')
        print()
        print("  See docs/KALSHI_LIVE_DATA.md for setup instructions.")

    print(f"\n  IMPORTANT: This system is {MODE}. No orders will be placed.")
    print()
    return 0 if all_ok else 1


def _print_env_status(env: LiveEnv) -> None:
    key_status = env.key_id_display if env.key_id else "NOT SET"
    print(f"  KALSHI_KEY_ID            : {key_status}")
    if env.private_key_path is None:
        path_status = "NOT SET"
    else:
        path_ok = env.private_key_path.exists()
        path_status = f"{env.private_key_path} ({'OK' if path_ok else 'FILE NOT FOUND'})"
    print(f"  KALSHI_PRIVATE_KEY_PATH  : {path_status}")

    from src.live.env import DEFAULT_REST_BASE, DEFAULT_WS_URL
    rest_tag = " (default)" if env.api_base_url == DEFAULT_REST_BASE else ""
    ws_tag = " (default)" if env.ws_url == DEFAULT_WS_URL else ""
    print(f"  KALSHI_API_BASE_URL      : {env.api_base_url}{rest_tag}")
    print(f"  KALSHI_WS_URL            : {env.ws_url}{ws_tag}")


# ---------------------------------------------------------------------------
# list-markets
# ---------------------------------------------------------------------------
def cmd_list_markets(args: argparse.Namespace) -> int:
    env = load_env()
    problems = validate_env(env)
    if problems:
        print("error: environment not configured. Run 'doctor' for details.", file=sys.stderr)
        return 1

    from src.live.kalshi_auth import KalshiSigner
    from src.live.kalshi_rest import KalshiRestClient
    from src.live.market_discovery import format_market_table, search_markets

    signer = KalshiSigner(env.key_id, env.private_key_path)
    client = KalshiRestClient(env, signer)

    sport = getattr(args, "sport", None)
    query = getattr(args, "query", None)
    verbose = getattr(args, "verbose", False)
    category = getattr(args, "category", None)

    try:
        # Fetch raw markets first if verbose mode (to show filter diagnostics)
        all_markets = None
        if verbose and (sport or query or category):
            all_markets = search_markets(
                client,
                series_ticker=args.series,
                event_ticker=args.event,
                ticker=args.ticker,
                status=args.status,
                limit=args.limit,
                sport=None,
                query=None,
                category=None,
            )

        # Fetch filtered markets
        markets = search_markets(
            client,
            series_ticker=args.series,
            event_ticker=args.event,
            ticker=args.ticker,
            status=args.status,
            limit=args.limit,
            sport=sport,
            query=query,
            category=category,
        )
    except Exception as exc:
        print(f"error fetching markets: {exc}", file=sys.stderr)
        return 1

    print(f"\n{DIVIDER}")
    print(f"  MARKETS ({len(markets)} found)")
    if all_markets is not None:
        print(f"  (filtered from {len(all_markets)} total)")
    print(DIVIDER)

    if not markets and sport:
        print(f"  No {sport.upper()} markets found.")
        if verbose and all_markets is not None:
            print(f"  Total markets available: {len(all_markets)}")
            if all_markets:
                series_list = sorted(set(m.series_ticker for m in all_markets))
                print("  Available series tickers: " + ", ".join(series_list[:10]))
                if len(series_list) > 10:
                    print(f"                            ... and {len(series_list) - 10} more")
    elif not markets:
        print("  (no markets found)")
    else:
        print(format_market_table(markets))
    print()
    return 0


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------
def cmd_record(args: argparse.Namespace) -> int:
    env = load_env()
    problems = validate_env(env)
    if problems:
        print("error: environment not configured. Run 'doctor' for details.", file=sys.stderr)
        return 1

    from src.live.kalshi_auth import KalshiSigner
    from src.live.kalshi_ws import KalshiWsClient
    from src.live.orderbook_mapper import OrderbookMapper, RawKalshiBook
    from src.live.recorder import LiveRecorder

    tickers: List[str] = args.tickers
    out_dir = Path(args.out)
    seconds = args.seconds
    mapper = OrderbookMapper()

    print(f"\n{DIVIDER}")
    print(f"  RECORDING — {MODE}")
    print(DIVIDER)
    print(f"  tickers  : {', '.join(tickers)}")
    print(f"  duration : {seconds}s")
    print(f"  output   : {out_dir}")
    print(f"  WARNING  : No orders will be placed.")
    print()

    with LiveRecorder(out_dir) as recorder:
        def on_message(ticker: str, msg: dict) -> None:
            norm = None
            try:
                from datetime import datetime, timezone
                ts = datetime.now(timezone.utc).isoformat()
                book = RawKalshiBook.from_api_response(ticker, ts, msg)
                snap = mapper.map_snapshot(book, event_id=ticker)
                norm = snap.to_dict()
            except Exception:  # noqa: BLE001
                pass
            recorder.record(ticker, msg, source="kalshi_ws", normalized_snapshot=norm)

        signer = KalshiSigner(env.key_id, env.private_key_path)
        client = KalshiWsClient(env, signer, on_message=on_message)
        try:
            count = client.run(tickers=tickers, seconds=seconds)
        except Exception as exc:
            print(f"error during recording: {exc}", file=sys.stderr)
            return 1

    print(f"  recorded {count} message(s) to {out_dir}")
    print()
    return 0


# ---------------------------------------------------------------------------
# build-bundle
# ---------------------------------------------------------------------------
def cmd_build_bundle(args: argparse.Namespace) -> int:
    from src.live.live_to_bundle import jsonl_to_bundle

    input_path = Path(args.input)
    out_path = Path(args.out) if args.out else None

    print(f"\n{DIVIDER}")
    print("  BUILD BUNDLE")
    print(DIVIDER)
    print(f"  input  : {input_path}")
    print(f"  output : {out_path or '(not saved)'}")
    print()

    try:
        bundle = jsonl_to_bundle(input_path, ticker=args.ticker, out_path=out_path)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    qr = bundle.quality_report
    verdict = qr.verdict.value if qr else "UNKNOWN"
    print(f"  ticks   : {len(bundle.ticks)}")
    print(f"  verdict : {verdict}")
    if qr and qr.issues:
        for issue in qr.issues:
            print(f"  [{issue.severity.value}] {issue.code}: {issue.message}")
    if out_path:
        print(f"  written : {out_path}")
    print()
    return 0


# ---------------------------------------------------------------------------
# train-from-capture
# ---------------------------------------------------------------------------
def cmd_train_from_capture(args: argparse.Namespace) -> int:
    from src.live.training_loop import print_training_report, run_training_from_capture

    input_path = Path(args.input)
    out_dir = Path(args.out)

    print(f"\n{DIVIDER}")
    print("  TRAIN FROM CAPTURE")
    print(DIVIDER)
    print(f"  input   : {input_path}")
    print(f"  out_dir : {out_dir}")
    print()

    try:
        batch = run_training_from_capture(
            input_path=input_path,
            out_dir=out_dir,
            ticker=args.ticker,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    missing_game = True  # training loop always marks this for now
    print_training_report(batch, missing_game=missing_game)
    print(f"  artifacts written to {out_dir}")
    print()
    return 0


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="src.live.cli",
        description=f"Bookie live data capture ({MODE})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # doctor
    d = sub.add_parser("doctor", help="check environment and dependencies")
    d.set_defaults(func=cmd_doctor)

    # list-markets
    lm = sub.add_parser("list-markets", help="list/search Kalshi markets")
    lm.add_argument("--series", default=None, help="series ticker filter")
    lm.add_argument("--event", default=None, help="event ticker filter")
    lm.add_argument("--ticker", default=None, help="exact ticker")
    lm.add_argument("--status", default=None, help="market status (e.g. open)")
    lm.add_argument("--limit", type=int, default=100)
    lm.add_argument("--sport", default=None, help="sport filter (e.g. tennis)")
    lm.add_argument("--category", default=None, help="Kalshi category filter (e.g. sports, bundled_product)")
    lm.add_argument("--query", default=None, help="substring search across title/tickers")
    lm.add_argument("--verbose", action="store_true", help="show diagnostics and filtered counts")
    lm.set_defaults(func=cmd_list_markets)

    # record
    rec = sub.add_parser("record", help="record live WS data to JSONL")
    rec.add_argument("--tickers", nargs="+", required=True, help="market tickers to record")
    rec.add_argument("--seconds", type=float, default=60.0, help="recording duration in seconds")
    rec.add_argument("--out", default="data/live", help="output base directory")
    rec.set_defaults(func=cmd_record)

    # build-bundle
    bb = sub.add_parser("build-bundle", help="convert JSONL capture to ReplayBundle")
    bb.add_argument("--input", required=True, help="input JSONL file")
    bb.add_argument("--out", default=None, help="output bundle JSON path")
    bb.add_argument("--ticker", default=None, help="override ticker name")
    bb.set_defaults(func=cmd_build_bundle)

    # train-from-capture
    tc = sub.add_parser("train-from-capture", help="capture -> bundle -> backtest -> report")
    tc.add_argument("--input", required=True, help="input JSONL file")
    tc.add_argument("--out", required=True, help="output directory for artifacts")
    tc.add_argument("--ticker", default=None, help="override ticker name")
    tc.set_defaults(func=cmd_train_from_capture)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
