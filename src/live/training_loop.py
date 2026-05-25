from __future__ import annotations

"""
Training loop: capture JSONL -> bundle -> backtest -> report.

This is DATA_CAPTURE_ONLY research. Results should be treated
with caution when game state is missing (market-microstructure only).
"""

from pathlib import Path
from typing import List, Optional

from src.backtest.batch import BatchRunner, export_batch
from src.backtest.config import BacktestConfig
from src.backtest.result import BatchBacktestResult
from src.live.live_to_bundle import jsonl_to_bundle

_RESEARCH_WARNINGS = [
    "LIVE_CAPTURE_MARKET_ONLY: This backtest used live capture data without game state.",
    "LIVE_CAPTURE_NOT_PROOF: Positive backtest PnL on capture data is NOT proof of live edge.",
    "LIVE_CAPTURE_SLIPPAGE: Live fill costs are higher than simulated slippage.",
    "LIVE_CAPTURE_SMALL_SAMPLE: Captures under 1 hour are too short to generalize.",
]


def run_training_from_capture(
    input_path: str | Path,
    out_dir: str | Path,
    ticker: Optional[str] = None,
    seeds: Optional[List[int]] = None,
) -> BatchBacktestResult:
    """
    Full pipeline: JSONL -> bundle -> batch backtest -> report.

    Returns the BatchBacktestResult with research warnings injected.
    """
    input_path = Path(input_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: convert capture to bundle
    bundle_path = out_dir / "live_capture_bundle.json"
    bundle = jsonl_to_bundle(input_path, ticker=ticker, out_path=bundle_path)

    missing_game = bundle.source_metadata.get("missing_game_state", True)

    # Step 2: build backtest configs
    use_seeds = seeds or [1, 2, 3]
    configs = [
        BacktestConfig(
            name=f"live_capture_s{seed}",
            seed=seed,
            bundle_path=str(bundle_path),
        )
        for seed in use_seeds
    ]

    # Step 3: run batch
    batch = BatchRunner(compute_robustness=True).run(configs, batch_id="live_capture")

    # Step 4: inject research warnings
    for result in batch.results:
        if missing_game:
            result.warnings.insert(0, "LIVE_CAPTURE_MARKET_ONLY: backtest used live data without game state")
        result.warnings.extend(_research_warnings_for_result(result, missing_game))

    # Step 5: export artifacts
    export_batch(batch, str(out_dir))

    return batch


def _research_warnings_for_result(result, missing_game: bool) -> List[str]:
    warnings = [
        "LIVE_CAPTURE_NOT_PROOF: live backtest PnL is not proof of live edge",
    ]
    if result.fills < 30:
        warnings.append(f"LIVE_CAPTURE_SMALL_SAMPLE: only {result.fills} fills — need 30+ to generalize")
    if missing_game:
        warnings.append(
            "LIVE_CAPTURE_GAME_STATE_ABSENT: strategies using score/period/clock are unreliable"
        )
    return warnings


def print_training_report(batch: BatchBacktestResult, missing_game: bool) -> None:
    print("\n" + "=" * 64)
    print("  LIVE CAPTURE TRAINING REPORT")
    print("=" * 64)
    print(f"  batch_id      : {batch.batch_id}")
    print(f"  runs          : {len(batch.results)}")
    agg = batch.aggregate_metrics
    print(f"  total PnL     : {agg.get('total_pnl_cents', 0):+.2f}c")
    print(f"  fills         : {agg.get('total_fills', 0)}")

    if missing_game:
        print("\n  WARNINGS:")
        print("  [!] Game state was NOT present in capture data.")
        print("      Strategies using score/period/clock have no signal.")
        print("      Results reflect market microstructure only.")

    print("\n  RESEARCH CAVEATS:")
    print("  - Positive PnL here is NOT proof of live edge.")
    print("  - Live fills have higher slippage than simulation.")
    print("  - Need many sessions of data before considering 1-contract mode.")
    print("  - See docs/LIVE_TRAINING.md for interpretation guidance.")
    print()
