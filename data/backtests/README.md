# Backtest output

Backtest runs write their artifacts here (one subdirectory per run/batch).
The directory is committed but its generated contents are gitignored — see
the repo `.gitignore`.

## Per-run (`run --out <dir>`)
- `result.json` — full `BacktestResult`

## Per-batch (`batch --out <dir>`)
- `batch_result.json`    — full `BatchBacktestResult`
- `leaderboard.csv`      — ranked strategies (balanced score)
- `strategy_metrics.csv` — per-strategy-per-run metrics
- `regime_metrics.csv`   — per-regime-per-run metrics
- `warnings.txt`         — all fake-edge / robustness warnings
- `report.txt`           — human-readable research report
- `report.json`          — machine-readable report

These are research artifacts from **simulated / replayed** data with fake
fills. They are not proof of live edge — see `docs/RESEARCH_WARNINGS.md`.
