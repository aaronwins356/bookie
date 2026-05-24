from __future__ import annotations

"""
Backtest CLI (argparse only).

Commands:
    run          run one config (scenario or bundle) -> result.json + report
    batch        run many configs -> batch artifacts + leaderboard + report
    leaderboard  print the leaderboard from a batch output dir
    inspect      print a single result.json

Examples:
    python -m src.backtest.cli run --scenario calm --seed 1 --out data/backtests/calm_seed1
    python -m src.backtest.cli run --bundle data/examples/replay_bundle.json --out data/backtests/example_bundle
    python -m src.backtest.cli batch --scenarios calm panic liquidity_crisis endgame_chaos --seeds 1 2 3 --out data/backtests/scenario_batch
    python -m src.backtest.cli batch --bundle-dir data/examples --out data/backtests/bundle_batch
    python -m src.backtest.cli leaderboard --results data/backtests/scenario_batch
    python -m src.backtest.cli inspect --result data/backtests/calm_seed1/result.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from src.backtest.config import BacktestConfig
from src.backtest.result import BacktestResult, BatchBacktestResult
from src.backtest.runner import BacktestRunner
from src.backtest.batch import BatchRunner, export_batch
from src.backtest.leaderboard import build_leaderboard
from src.backtest.report import write_report, build_report_text
from src.backtest import significance

DIVIDER = "=" * 64


# ---------------------------------------------------------------------------
# persistence helpers
# ---------------------------------------------------------------------------
def _save_result(result: BacktestResult, out_dir: str) -> str:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "result.json"
    with path.open("w", encoding="utf-8") as fh:
        json.dump(result.to_dict(), fh, indent=2, sort_keys=True)
    return str(path)


def _load_result(path: str) -> BacktestResult:
    with Path(path).open("r", encoding="utf-8") as fh:
        return BacktestResult.from_dict(json.load(fh))


def _discover_bundles(dirpath: str) -> List[str]:
    """Return paths in a dir that actually parse as replay bundles."""
    from src.data.bundle import load_bundle
    found: List[str] = []
    for p in sorted(Path(dirpath).glob("*.json")) + sorted(Path(dirpath).glob("*.jsonl")):
        try:
            b = load_bundle(p)
            if b.ticks:
                found.append(str(p))
        except Exception:  # noqa: BLE001
            continue
    return found


def _print_result_summary(result: BacktestResult) -> None:
    p = result.pnl_summary
    print(f"  source        : {result.config.source_label()}")
    print(f"  ticks/fills   : {result.ticks_processed} / {result.fills}  "
          f"(rejected {result.rejected_orders})")
    print(f"  total PnL     : {p.total_pnl_cents:+.2f}c  (real {p.realized_pnl_cents:+.2f} / "
          f"unreal {p.unrealized_pnl_cents:+.2f})")
    print(f"  sharpe-like   : {p.sharpe_like}   max drawdown: {result.drawdown_summary.max_drawdown_cents:.2f}c")
    print(f"  fees/slippage : {p.fees_cents:.2f}c / {p.slippage_loss_cents:.2f}c")
    top = sorted(result.strategy_metrics, key=lambda m: -m.total_pnl_cents)
    print("  strategy PnL  :")
    for m in top:
        print(f"     {m.strategy_name:<20} pnl={m.total_pnl_cents:+8.1f}  fills={m.fills:<3} "
              f"winr={m.win_rate:.2f}  ev_capture={m.ev_capture}")
    if result.warnings:
        print(f"  warnings ({len(result.warnings)}):")
        for w in result.warnings[:12]:
            print(f"     - {w}")


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def cmd_run(args: argparse.Namespace) -> int:
    if not args.scenario and not args.bundle:
        print("error: provide --scenario or --bundle", file=sys.stderr)
        return 2
    name = args.name or (args.scenario or Path(args.bundle).stem)
    config = BacktestConfig(
        name=name, seed=args.seed, scenario_name=args.scenario,
        bundle_path=args.bundle, output_dir=args.out,
    )
    result = BacktestRunner().run(config)
    result.warnings.extend(significance.evaluate_result_warnings(result, n_events=1))

    print(f"\n{DIVIDER}\n  BACKTEST RUN - {name}\n{DIVIDER}")
    _print_result_summary(result)

    if args.out:
        path = _save_result(result, args.out)
        result.artifacts["result"] = path
        # rewrite with artifact path included
        _save_result(result, args.out)
        print(f"\n  written to    : {path}")
    print()
    return 0


def _build_batch_configs(args: argparse.Namespace) -> List[BacktestConfig]:
    configs: List[BacktestConfig] = []
    if args.bundle_dir:
        bundles = _discover_bundles(args.bundle_dir)
        if not bundles:
            print(f"warning: no valid bundles found in {args.bundle_dir}", file=sys.stderr)
        for path in bundles:
            for seed in (args.seeds or [1]):
                configs.append(BacktestConfig(
                    name=f"{Path(path).stem}_s{seed}", seed=seed, bundle_path=path,
                ))
    else:
        scenarios = args.scenarios or ["calm"]
        for sc in scenarios:
            for seed in (args.seeds or [1]):
                configs.append(BacktestConfig(name=f"{sc}_s{seed}", seed=seed, scenario_name=sc))
    return configs


def cmd_batch(args: argparse.Namespace) -> int:
    configs = _build_batch_configs(args)
    if not configs:
        print("error: no configs to run", file=sys.stderr)
        return 2

    batch = BatchRunner(compute_robustness=not args.no_robustness).run(
        configs, batch_id=Path(args.out).name if args.out else "batch")

    print(f"\n{DIVIDER}\n  BATCH BACKTEST - {batch.batch_id}\n{DIVIDER}")
    print(f"  runs          : {len(batch.results)}/{len(configs)} succeeded")
    agg = batch.aggregate_metrics
    print(f"  total PnL     : {agg.get('total_pnl_cents', 0):+.2f}c   "
          f"fills: {agg.get('total_fills', 0)}   rejected: {agg.get('total_rejected', 0)}")
    _print_leaderboard(batch)

    if args.out:
        artifacts = export_batch(batch, args.out)
        report_paths = write_report(batch, args.out)
        artifacts.update(report_paths)
        print(f"\n  artifacts written to {args.out}:")
        for k, v in artifacts.items():
            print(f"     {k:<22} {v}")
    print()
    return 0


def _print_leaderboard(batch: BatchBacktestResult) -> None:
    print(f"\n  LEADERBOARD (balanced score):")
    print(f"  {'#':<3}{'strategy':<20}{'score':>8}{'pnl':>10}{'fills':>7}"
          f"{'winr':>7}{'robust':>8}  flags")
    for rank, row in enumerate(batch.leaderboard, 1):
        print(f"  {rank:<3}{row.strategy_name:<20}{row.score:>8.3f}{row.total_pnl_cents:>10.1f}"
              f"{row.fills:>7}{row.win_rate:>7.2f}{row.robustness_score:>8.2f}  "
              f"{','.join(row.warning_flags) or '-'}")


def cmd_leaderboard(args: argparse.Namespace) -> int:
    path = Path(args.results) / "batch_result.json"
    if not path.exists():
        print(f"error: {path} not found", file=sys.stderr)
        return 2
    with path.open("r", encoding="utf-8") as fh:
        batch = BatchBacktestResult.from_dict(json.load(fh))
    print(f"\n{DIVIDER}\n  LEADERBOARD - {batch.batch_id}\n{DIVIDER}")
    _print_leaderboard(batch)
    print()
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    result = _load_result(args.result)
    print(f"\n{DIVIDER}\n  INSPECT RESULT - {result.config.name}\n{DIVIDER}")
    _print_result_summary(result)
    print()
    return 0


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="src.backtest.cli", description="Bookie backtesting")
    sub = parser.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", help="run one backtest")
    r.add_argument("--scenario", default=None)
    r.add_argument("--bundle", default=None)
    r.add_argument("--seed", type=int, default=1)
    r.add_argument("--name", default=None)
    r.add_argument("--out", default=None)
    r.set_defaults(func=cmd_run)

    b = sub.add_parser("batch", help="run many backtests")
    b.add_argument("--scenarios", nargs="+", default=None)
    b.add_argument("--seeds", nargs="+", type=int, default=None)
    b.add_argument("--bundle-dir", default=None, dest="bundle_dir")
    b.add_argument("--out", default=None)
    b.add_argument("--no-robustness", action="store_true", dest="no_robustness",
                   help="skip robustness scoring (faster)")
    b.set_defaults(func=cmd_batch)

    lb = sub.add_parser("leaderboard", help="print leaderboard from a batch dir")
    lb.add_argument("--results", required=True)
    lb.set_defaults(func=cmd_leaderboard)

    i = sub.add_parser("inspect", help="inspect a single result.json")
    i.add_argument("--result", required=True)
    i.set_defaults(func=cmd_inspect)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
