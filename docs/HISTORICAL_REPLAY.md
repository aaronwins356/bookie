# Historical Replay

Run the engine against a normalized replay bundle built from historical-style
data, instead of a synthetic scenario.

## How to run

```bash
# 1. build a bundle from raw files
python -m src.data.cli build-bundle \
    --game data/examples/raw_game_sample.csv \
    --market data/examples/raw_market_sample.csv \
    --out data/examples/replay_bundle.json

# 2. replay it through the full engine
python -m src.replay.simulator --bundle data/examples/replay_bundle.json
```

The `--bundle` flag overrides `--scenario`. Scenario modes (`comeback`,
`blowout`, `calm`, `panic`, `liquidity_crisis`, `endgame_chaos`) are
unchanged.

## What happens

Each `CanonicalReplayTick` is converted to engine `GameState` / `MarketState`
(`bundle.to_engine_ticks`) and fed through the **same** path as the simulated
scenarios:

```
features → strategies (regime-aware) → PortfolioRouter → RiskManager → FillEngine (fake) → analytics
```

Per tick the simulator prints game/market state, a classified market regime
(derived from spread, odds velocity, liquidity, score, time), signals, router
allocations, risk vetoes/fills with slippage, and running PnL. A final
analytics block reports PnL, drawdown, a Sharpe-like ratio, exposure, and
per-regime PnL. Ticks flagged `stale_market` / `stale_game` during alignment
are marked `[STALE DATA]`.

## Limitations — read this

**Historical replay is NOT proof of live edge.** Treat results as a sanity
check on plumbing and behavior, not as backtest performance:

- **Fills are simulated.** The `FillEngine` provides fake fills with modeled
  slippage. Real fills depend on live queue position, latency, and adverse
  selection not present here.
- **No market impact.** Replaying assumes your orders would not have moved the
  historical prices. At any non-trivial size this is false.
- **Survivorship & selection bias.** A hand-picked event (like the sample) is
  not a representative sample of all games/markets.
- **Lagging-mid artifacts.** Edge can appear simply because the recorded mid
  lags the true probability. That is a property of the data cadence, not a
  tradeable edge.
- **Look-ahead risk.** Misaligned timestamps can leak future information.
  The aligner records `lag_seconds` and staleness so you can audit this —
  check the quality report before trusting any result.
- **Small samples.** A few ticks produce noisy PnL; do not read significance
  into them.

The point of Phase 3 is clean ingestion and obvious bad-data detection — so
that when real data flows in later, it does so honestly. Proving edge is a
later phase and requires far more rigor (out-of-sample testing, realistic
fills, transaction costs, and statistical significance).
