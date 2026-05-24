# Market Microstructure Simulation

The `src/simulation/` layer turns the replay engine from a scripted price
player into a realistic, deterministic-with-seed market simulator. It
depends only on `src.models`.

## Modules

| Module             | Responsibility                                                   |
|--------------------|------------------------------------------------------------------|
| `market_regime.py` | `MarketRegime` enum + deterministic `RegimeClassifier`           |
| `orderbook.py`     | YES/NO limit book, depth, queue walk, liquidity exhaustion       |
| `liquidity.py`     | Depth profile; endgame decay, regime collapse, sudden vanish     |
| `slippage.py`      | Size- and regime-sensitive realized fill price                   |
| `latency.py`       | Quote/fill delays, stale-snapshot detection                      |
| `volatility.py`    | Per-tick price increments per `VolatilityRegime`                 |
| `spread_engine.py` | Spread as a function of vol, liquidity, and price boundaries     |
| `fill_engine.py`   | Combines book+slippage+latency+queue → `ExecutionResult`         |
| `queue_model.py`   | FIFO queue position and fill probability at a level              |
| `event_engine.py`  | Random scoring/panic/collapse/stale events (seeded)              |

## Market regimes

`MarketRegime`: CALM, TRENDING_UP, TRENDING_DOWN, PANIC_BUYING,
PANIC_SELLING, FAVORITE_EUPHORIA, ENDGAME_CHAOS, LIQUIDITY_COLLAPSE,
DEAD_MARKET, MEAN_REVERSION.

Classified deterministically from: spread width, odds velocity, liquidity
depth, volatility, time remaining, score differential, and order-flow
imbalance. The decision tree checks the most structurally-dominant
conditions first (liquidity failure → endgame chaos → dead → panic → …).

## Determinism

Every stochastic component takes a `seed`. Given the same seed, a scenario
replays identically — essential for reproducible strategy evaluation.

## Scenarios

`ScenarioEngine` (in `src/replay/scenario_engine.py`) drives these
primitives along a scripted score path while keeping the mid a *lagging*
tracker of fair value. That lag — the market being slow to reprice after a
score change — is the edge the strategies are designed to exploit.

```
python -m src.replay.simulator --scenario calm
python -m src.replay.simulator --scenario panic
python -m src.replay.simulator --scenario liquidity_crisis
python -m src.replay.simulator --scenario endgame_chaos
```
