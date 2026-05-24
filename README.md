# bookie

A modular sports prediction-market trading engine.

**Status: mock/replay only — no live exchange, no API keys required.**

## Quick start

```bash
# Install (Python 3.11+)
pip install -e ".[dev]"

# Run the replay simulator — scripted scenarios
python -m src.replay.simulator --scenario comeback
python -m src.replay.simulator --scenario blowout

# Microstructure-driven scenarios (regime-aware, slippage, liquidity collapse, analytics)
python -m src.replay.simulator --scenario calm
python -m src.replay.simulator --scenario panic
python -m src.replay.simulator --scenario liquidity_crisis
python -m src.replay.simulator --scenario endgame_chaos

# Data pipeline (Phase 3): ingest raw files → validate → bundle → replay
python -m src.data.cli validate      --game data/examples/raw_game_sample.csv  --market data/examples/raw_market_sample.csv
python -m src.data.cli build-bundle  --game data/examples/raw_game_sample.csv  --market data/examples/raw_market_sample.csv  --out data/examples/replay_bundle.json
python -m src.data.cli inspect-bundle --bundle data/examples/replay_bundle.json
python -m src.replay.simulator --bundle data/examples/replay_bundle.json

# Backtesting (Phase 4): run/batch backtests, leaderboard, research report
python -m src.backtest.cli run --scenario calm --seed 1 --out data/backtests/calm_seed1
python -m src.backtest.cli run --bundle data/examples/replay_bundle.json --out data/backtests/example_bundle
python -m src.backtest.cli batch --scenarios calm panic liquidity_crisis endgame_chaos --seeds 1 2 3 --out data/backtests/scenario_batch
python -m src.backtest.cli leaderboard --results data/backtests/scenario_batch

# Run tests
pytest tests/ -v
```

## Architecture overview

```
src/
├── engine/       # Deterministic math: features, fair value, router, risk, execution
├── strategies/   # Signal generators — output Signal objects only
├── adapters/     # Market / game / execution adapters (mock only right now)
├── controller/   # Brain + decision loop (future LLM hook point)
├── replay/       # Replay simulator + scenario engine + sample data loader
├── simulation/   # Market microstructure: orderbook, liquidity, slippage, regimes…
├── analytics/    # PnL, drawdown, exposure, expectancy, correlation, performance
├── storage/      # JSON/JSONL audit, replay, and snapshot stores
├── data/         # Phase 3: ingestion, canonical schema, validation, bundles, CLI
├── backtest/     # Phase 4: runner, batch, splits, significance, robustness, leaderboard, CLI
└── models/       # Shared data types (Signal, OrderIntent, GameState, …)
```

See `docs/` for full design documentation:
`CONCEPT.md`, `ARCHITECTURE.md`, `STRATEGIES.md`, `SIMULATION.md`,
`LOCAL_BRAIN.md`, `DATA_PIPELINE.md`, `CANONICAL_SCHEMA.md`,
`HISTORICAL_REPLAY.md`, `BACKTESTING.md`, `STRATEGY_LEADERBOARD.md`,
`RESEARCH_WARNINGS.md`, `LINUX_PLUG_AND_PLAY.md`, `SECRETS.md`.

## Design principles

- Strategies output `Signal` objects — never execute orders directly
- `Router` converts `Signal` → `OrderIntent`
- `RiskManager` can veto any order; the brain cannot override it
- `ExecutionEngine` defaults to `MockExecutionAdapter` (fake fills)
- The future LLM controller calls deterministic tools — it never bypasses risk rules

## Running on Linux

See `docs/LINUX_PLUG_AND_PLAY.md`.
