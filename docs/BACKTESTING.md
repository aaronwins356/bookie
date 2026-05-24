# Backtesting (Phase 4)

A harness for running replay bundles and built-in scenarios many times,
aggregating performance, and producing **honest** research output. It reuses
the existing engine (strategies, PortfolioRouter, RiskManager, FillEngine,
analytics) — the runner only re-implements the orchestration loop so it
*returns structured results* instead of printing. The replay simulator CLI
is untouched.

## Run a single backtest

```bash
# from a built-in scenario
python -m src.backtest.cli run --scenario calm --seed 1 --out data/backtests/calm_seed1

# from a replay bundle
python -m src.backtest.cli run --bundle data/examples/replay_bundle.json --out data/backtests/example_bundle
```

Writes `result.json` and prints a summary (PnL, Sharpe-like, drawdown,
per-strategy PnL, warnings).

## Run a batch

```bash
# cross product of scenarios × seeds
python -m src.backtest.cli batch --scenarios calm panic liquidity_crisis endgame_chaos --seeds 1 2 3 --out data/backtests/scenario_batch

# every valid bundle in a directory
python -m src.backtest.cli batch --bundle-dir data/examples --out data/backtests/bundle_batch
```

Batch artifacts: `batch_result.json`, `leaderboard.csv`, `strategy_metrics.csv`,
`regime_metrics.csv`, `warnings.txt`, `report.txt`, `report.json`.

Add `--no-robustness` to skip per-strategy robustness scoring (faster).

## Inspect

```bash
python -m src.backtest.cli leaderboard --results data/backtests/scenario_batch
python -m src.backtest.cli inspect --result data/backtests/calm_seed1/result.json
```

## How results are calculated

- **Per fill**: an `OrderIntent` that passes the `RiskManager` is filled by the
  `FillEngine` (fake fills, modeled slippage + fees). Each fill opens a lot
  attributed to its strategy.
- **PnL**: each lot is marked to the final mid of its market. `total_pnl =
  realized + unrealized − fees`. Positions are not actively closed in this
  harness, so most PnL is unrealized mark-to-market.
- **Per-strategy attribution**: lots are grouped by strategy; win/loss is per
  lot at the final mark.
- **Per-regime**: equity delta per tick is attributed to the tick's classified
  `MarketRegime`.
- **Robustness**: the config is rerun under harsher slippage/latency/fees and
  across seeds; the score blends "stays positive" with seed stability.
- **Leaderboard score**: a balanced blend of bounded PnL, Sharpe-like, win
  rate, EV capture, and robustness, minus drawdown and warning penalties, with
  a low-sample haircut. See `docs/STRATEGY_LEADERBOARD.md`.

## Limitations

- **Fake fills.** No real queue, latency-adverse selection, or market impact.
- **Tiny samples.** The bundled examples are a handful of ticks; treat every
  number as anecdotal. The harness will say so via warnings.
- **No position lifecycle.** Lots are marked, not exited; this is a research
  approximation, not a trade simulator.
- **Simulated/historical ≠ live.** See `docs/RESEARCH_WARNINGS.md` and
  `docs/HISTORICAL_REPLAY.md`. This phase exists to expose fake edge early, not
  to prove edge.
