# Live Data Training Pipeline

**This is research tooling only. No orders are placed at any stage.**

---

## The Capture → Bundle → Backtest Loop

```
Live WS Stream
     │
     ▼
JSONL Capture (data/live/YYYY-MM-DD/<ticker>.jsonl)
     │
     ▼
ReplayBundle (live_capture_bundle.json)
     │
     ▼
Batch Backtest (across seeds)
     │
     ▼
Strategy Leaderboard + Research Report
```

### Run the full loop in one command:

```bash
python -m src.live.cli train-from-capture \
  --input data/live/2025-05-25/KXBTC15M-25MAY-BTC15T32000.jsonl \
  --out data/backtests/live_capture_check
```

Or step-by-step:

```bash
# Step 1: record
python -m src.live.cli record \
  --tickers KXBTC15M-25MAY-BTC15T32000 \
  --seconds 3600 \
  --out data/live

# Step 2: build bundle
python -m src.live.cli build-bundle \
  --input data/live/2025-05-25/KXBTC15M-25MAY-BTC15T32000.jsonl \
  --out data/live/KXBTC15M-25MAY-BTC15T32000_bundle.json

# Step 3: backtest
python -m src.backtest.cli run \
  --bundle data/live/KXBTC15M-25MAY-BTC15T32000_bundle.json \
  --out data/backtests/live_run1
```

---

## Why Market-Only Data Is Incomplete

Bookie strategies are designed with game state as a primary signal source:
- Score differential → `favorite_grinder`, `overpriced_fade`
- Game phase (half/quarter/overtime) → `endgame_bonding`
- Clock seconds remaining → `endgame_bonding`, `liquidity_vacuum`

When the capture contains only market/orderbook data (no sports feed),
placeholder game events with `status=LIVE_UNKNOWN` are created. All
game-state-dependent strategies will produce zero signal from these ticks.

**What the backtest CAN tell you from market-only data:**
- Whether the orderbook structure triggers momentum or spread signals
- Slippage and fill behavior under realistic liquidity
- Regime detection from order flow patterns

**What it CANNOT tell you:**
- Whether game-context signals have edge
- How the strategy would have performed with real game context
- Whether the strategy is net-profitable live

---

## Why Positive Backtest PnL Is Not Proof of Live Edge

Even if backtest PnL is positive on captured live data:

1. **Simulation slippage ≠ live slippage.** The fill engine uses a slippage model;
   real Kalshi fills may have higher impact, especially in thin books.

2. **Look-ahead bias.** The backtest sees the full tick stream at once; a live
   system sees only the current and past ticks.

3. **Sample size.** One recording session is not sufficient to generalize.
   A strategy needs hundreds of events across many market regimes.

4. **Regime concentration.** If all your data comes from one market regime
   (e.g., low-volatility late game), the strategy may not generalize.

5. **Missing game state.** If game context is absent, all game-state strategies
   are effectively flat — their apparent "edge" is zero signal, not real edge.

---

## How Much Data Is Needed Before 1-Contract Mode

There is no hard rule, but the research minimum is:

| Metric | Suggested Threshold |
|---|---|
| Total fills (backtest) | ≥ 200 across all seeds |
| Distinct market sessions | ≥ 50 |
| Market regimes covered | All 4+ (calm, panic, mean-reversion, endgame) |
| Win rate consistency | Win rate stable across seeds and sessions |
| Sharpe-like score | Positive across ≥ 80% of seeds |
| Game state coverage | At least some sessions WITH game state data |

If these thresholds are met AND the strategy passes the significance tests
(`src.backtest.significance`), it may be appropriate to consider 1-contract
mode. That is a separate, future phase — not implemented here.

---

## Research Warnings Reference

The training loop injects these warning codes into backtest results:

| Code | Meaning |
|---|---|
| `LIVE_CAPTURE_MARKET_ONLY` | Backtest used live data without game state |
| `LIVE_CAPTURE_NOT_PROOF` | Positive PnL is not proof of live edge |
| `LIVE_CAPTURE_SMALL_SAMPLE` | Too few fills to generalize |
| `LIVE_CAPTURE_GAME_STATE_ABSENT` | Game-context strategies are unreliable |

These warnings appear in `result.json` under `warnings[]` and in the report.

---

## Artifacts Written by train-from-capture

```
data/backtests/live_capture_check/
├── live_capture_bundle.json   ← the converted ReplayBundle
├── batch_result.json          ← full batch backtest results
├── leaderboard.csv            ← strategy ranking
├── strategy_metrics.csv       ← per-strategy breakdown
├── regime_metrics.csv         ← per-regime breakdown
├── warnings.txt               ← all warnings in one file
├── report.txt                 ← human-readable report
└── report.json                ← machine-readable report
```
