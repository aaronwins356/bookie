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
└── models/       # Shared data types (Signal, OrderIntent, GameState, …)
```

See `docs/` for full design documentation:
`CONCEPT.md`, `ARCHITECTURE.md`, `STRATEGIES.md`, `SIMULATION.md`,
`LOCAL_BRAIN.md`, `LINUX_PLUG_AND_PLAY.md`, `SECRETS.md`.

## Design principles

- Strategies output `Signal` objects — never execute orders directly
- `Router` converts `Signal` → `OrderIntent`
- `RiskManager` can veto any order; the brain cannot override it
- `ExecutionEngine` defaults to `MockExecutionAdapter` (fake fills)
- The future LLM controller calls deterministic tools — it never bypasses risk rules

## Running on Linux

See `docs/LINUX_PLUG_AND_PLAY.md`.
