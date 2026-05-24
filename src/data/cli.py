from __future__ import annotations

"""
Data pipeline CLI (argparse only).

Commands:
    validate        load + normalize + validate game/market files, print report
    build-bundle    build a replay bundle and write it to --out
    inspect-bundle  load a bundle and print its metadata + quality summary

Examples:
    python -m src.data.cli validate \
        --game data/examples/raw_game_sample.csv \
        --market data/examples/raw_market_sample.csv

    python -m src.data.cli build-bundle \
        --game data/examples/raw_game_sample.csv \
        --market data/examples/raw_market_sample.csv \
        --out data/examples/replay_bundle.json

    python -m src.data.cli inspect-bundle --bundle data/examples/replay_bundle.json
"""

import argparse
import sys
from typing import List

from src.data.loaders import load_games, load_markets
from src.data.validators import validate_all
from src.data.aligner import align
from src.data.quality import build_quality_report, format_report
from src.data.bundle import build_bundle, save_bundle, load_bundle
from src.data.schemas import Severity, Verdict, ValidationIssue


DIVIDER = "=" * 60


def _print_issues(issues: List[ValidationIssue], limit: int = 20) -> None:
    if not issues:
        print("  (no issues)")
        return
    shown = sorted(issues, key=lambda i: -i.severity.rank)[:limit]
    for i in shown:
        loc = f"row={i.index}" if i.index is not None else (i.timestamp or "")
        fix = f"  fix: {i.suggested_fix}" if i.suggested_fix else ""
        print(f"  [{i.severity.value:<7}] {i.code:<28} {i.message} ({loc}){fix}")
    if len(issues) > limit:
        print(f"  ... and {len(issues) - limit} more")


def cmd_validate(args: argparse.Namespace) -> int:
    games = load_games(args.game)
    markets = load_markets(args.market)
    issues = validate_all(games, markets)
    alignment = align(games, markets, max_lag_seconds=args.max_lag)
    report = build_quality_report(games, markets, issues, alignment)

    print(f"\n{DIVIDER}\n  VALIDATION REPORT\n{DIVIDER}")
    print(format_report(report))
    print(f"\n  ISSUES ({len(issues)}):")
    _print_issues(issues)
    print()
    return 0 if report.verdict != Verdict.FAIL else 1


def cmd_build_bundle(args: argparse.Namespace) -> int:
    games = load_games(args.game)
    markets = load_markets(args.market)
    bundle = build_bundle(
        games, markets, max_lag_seconds=args.max_lag,
        source_metadata={"game_file": args.game, "market_file": args.market},
    )
    save_bundle(bundle, args.out)

    print(f"\n{DIVIDER}\n  BUILD BUNDLE\n{DIVIDER}")
    print(f"  bundle_id   : {bundle.bundle_id}")
    print(f"  event_id    : {bundle.event_id}  ({bundle.sport}/{bundle.league})")
    print(f"  ticks       : {len(bundle.ticks)}")
    if bundle.quality_report:
        print(f"  verdict     : {bundle.quality_report.verdict.value}")
        print(f"  dropped     : {bundle.quality_report.dropped_rows}")
    print(f"  written to  : {args.out}")
    print()

    if bundle.quality_report and bundle.quality_report.verdict == Verdict.FAIL:
        print("  WARNING: bundle built from data that FAILED validation.\n")
        return 1
    return 0


def cmd_inspect_bundle(args: argparse.Namespace) -> int:
    bundle = load_bundle(args.bundle)
    print(f"\n{DIVIDER}\n  INSPECT BUNDLE\n{DIVIDER}")
    print(f"  bundle_id   : {bundle.bundle_id}")
    print(f"  created_at  : {bundle.created_at}")
    print(f"  event_id    : {bundle.event_id}  ({bundle.sport}/{bundle.league})")
    print(f"  ticks       : {len(bundle.ticks)}")
    print(f"  source      : {bundle.source_metadata}")
    if bundle.ticks:
        first, last = bundle.ticks[0], bundle.ticks[-1]
        print(f"  time range  : {first.timestamp} .. {last.timestamp}")
        ge = first.game_event
        print(f"  first tick  : {ge.home_team} {ge.home_score}-{ge.away_score} "
              f"@ mid {first.market_snapshot.mid:.1f}c")
    if bundle.quality_report:
        print(f"\n  QUALITY REPORT")
        print(format_report(bundle.quality_report))
    print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="src.data.cli", description="Bookie data pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="validate game + market files")
    v.add_argument("--game", required=True)
    v.add_argument("--market", required=True)
    v.add_argument("--max-lag", type=float, default=60.0, dest="max_lag")
    v.set_defaults(func=cmd_validate)

    b = sub.add_parser("build-bundle", help="build a replay bundle")
    b.add_argument("--game", required=True)
    b.add_argument("--market", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--max-lag", type=float, default=60.0, dest="max_lag")
    b.set_defaults(func=cmd_build_bundle)

    i = sub.add_parser("inspect-bundle", help="inspect a replay bundle")
    i.add_argument("--bundle", required=True)
    i.set_defaults(func=cmd_inspect_bundle)

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
