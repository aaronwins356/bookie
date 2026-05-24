# Architecture

## Module map

```
src/
├── models/
│   ├── signal.py        Signal, SignalDirection, Regime
│   ├── order.py         OrderIntent, OrderSide, ExecutionResult
│   └── game.py          GameState, MarketState, GamePhase
│
├── engine/
│   ├── market_state.py  MarketStateEngine  — cache of latest market snapshots
│   ├── game_state.py    GameStateEngine    — cache of latest game snapshots
│   ├── features.py      FeatureExtractor   — computes FeatureSet from state
│   ├── fair_value.py    FairValueModel     — deterministic probability estimate
│   ├── router.py        Router             — Signal → OrderIntent
│   ├── risk.py          RiskManager        — veto gate with hard limits
│   ├── execution.py     ExecutionEngine    — wraps adapter, defaults to mock
│   └── audit.py         AuditLog           — append-only event log
│
├── strategies/
│   ├── favorite_grinder.py   Back leading team when underpriced
│   ├── endgame_bonding.py    Late-game large-lead capture
│   ├── momentum.py           Follow strong price moves
│   ├── overpriced_fade.py    Fade overreaction after scoring event
│   └── liquidity_vacuum.py   Provide liquidity in thin markets
│
├── adapters/
│   ├── mock_market_adapter.py     Static market data for replay
│   ├── mock_game_adapter.py       Static game data for replay
│   ├── mock_execution_adapter.py  Always fills at limit price
│   └── kalshi_adapter_stub.py     NotImplementedError stub
│
├── controller/
│   ├── tool_registry.py   Dict of callable tools for the brain
│   ├── local_brain.py     observe → classify → route → summarize
│   └── decision_loop.py   Orchestrates one full tick
│
├── replay/
│   ├── sample_data_loader.py  Scripted NFL scenarios
│   ├── scenario_engine.py     Microstructure-driven scenario generator
│   └── simulator.py           CLI entry point (scripted + simulated paths)
│
├── simulation/                Market microstructure (see docs/SIMULATION.md)
│   ├── market_regime.py       MarketRegime enum + RegimeClassifier
│   ├── orderbook.py           YES/NO limit book, depth, queue walk
│   ├── liquidity.py           Depth profile + collapse modeling
│   ├── slippage.py            Size/regime-aware realized fill price
│   ├── latency.py             Quote/fill delays, stale snapshots
│   ├── volatility.py          Per-tick increments per volatility regime
│   ├── spread_engine.py       Spread = f(vol, liquidity, price)
│   ├── fill_engine.py         book+slippage+latency+queue → fills
│   ├── queue_model.py         FIFO queue position + fill probability
│   └── event_engine.py        Random scoring/panic/collapse events
│
├── analytics/                 Pure metrics over trade/fill/PnL records
│   ├── pnl.py                 Positions, realized/unrealized PnL
│   ├── drawdown.py            Max drawdown over equity curve
│   ├── exposure.py            Exposure by market/strategy/direction
│   ├── correlation.py         Strategy-return correlation
│   ├── expectancy.py          Expectancy + EV capture
│   ├── strategy_metrics.py    Per-strategy attribution
│   └── performance.py         Sharpe-like report aggregator
│
└── storage/                   Dependency-free JSON/JSONL persistence
    ├── audit_store.py         Append-only audit trail (JSONL)
    ├── replay_store.py        Save/load replay scenarios
    └── snapshot_store.py      Per-tick state snapshots
```

## Layering & dependencies

```
models  ←  simulation   (microstructure depends only on models)
models  ←  analytics     (pure; reusable for live trading later)
models  ←  storage
models, simulation  ←  strategies (regime metadata)
models, simulation  ←  engine (router ranking, risk regime scaling)
everything           ←  controller / replay (orchestration)
```

## Upgraded engine components

- **PortfolioRouter** (`engine/router.py`) — ranks opportunities by
  EV × regime compatibility, enforces cooldowns, max-concurrent-strategy
  caps, duplicate-direction and correlation guards, and dynamic sizing.
  The base `Router.route()` is preserved.
- **RiskManager** (`engine/risk.py`) — adds drawdown tracking, regime risk
  scaling, volatility/liquidity-adjusted sizing, per-strategy exposure
  limits, slippage-aware checks, and a catastrophic-loss kill switch. All
  extended checks have permissive defaults, so the base contract is intact.
- **Strategies** — each exposes a `StrategyProfile` (liquidity/volatility
  sensitivity, risk, holding time, favored/averse regimes) and
  `regime_compatibility()`, and behaves differently per regime.
- **LocalBrain** — see docs/LOCAL_BRAIN.md.

## Data flow (one tick)

1. `SampleDataLoader` yields `(GameState, [MarketState])`
2. `DecisionLoop.tick()` called
3. `LocalBrain.observe()` → dict snapshot
4. `LocalBrain.classify_regime()` → `Regime`
5. For each market × strategy: `FeatureExtractor.extract()` → `FeatureSet`
6. `strategy.evaluate(features)` → `Signal`
7. `LocalBrain.route()` filters to actionable signals
8. `Router.route(signal)` → `OrderIntent`
9. `RiskManager.evaluate(intent)` → `(approved, reason)`
10. If approved: `ExecutionEngine.submit(intent)` → `ExecutionResult`
11. All events written to `AuditLog`

## Extending

- **Add a strategy**: create `src/strategies/my_strategy.py`, export a class with `.evaluate(features) -> Signal`, add to `DecisionLoop`.
- **Add a market adapter**: implement `fetch(market_id) -> MarketState`, pass to `MarketStateEngine`.
- **Wire live execution**: implement `submit(intent) -> ExecutionResult`, pass to `ExecutionEngine`.
- **Plug in LLM**: override `LocalBrain.classify_regime()` with an Ollama call.
