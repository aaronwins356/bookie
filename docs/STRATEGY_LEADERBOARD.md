# Strategy Leaderboard

The leaderboard ranks strategies by a **balanced score**, not raw PnL. A
strategy with huge PnL from two lucky fills should not beat a steady, robust
performer — and here it won't.

## Columns

| Column              | Meaning                                                        |
|---------------------|----------------------------------------------------------------|
| `total_pnl_cents`   | summed mark-to-market PnL across all runs                      |
| `fills`             | number of filled lots (sample size)                            |
| `win_rate`          | fraction of lots positive at final mark                        |
| `avg_pnl_cents`     | mean PnL per fill (also used as expectancy)                    |
| `max_drawdown_cents`| peak-to-trough over the per-run cumulative PnL                 |
| `sharpe_like`       | mean/stdev × √n over per-run PnLs                              |
| `ev_capture`        | realized PnL ÷ claimed edge (>1 = beat its own model)          |
| `robustness_score`  | 0–1, survival under slippage/latency/fee/seed stress           |
| `warning_flags`     | fake-edge / fragility flags (see below)                        |
| `score`             | the balanced ranking score                                     |

## Score formula

All raw terms are squashed with `tanh` so no single dimension dominates:

```
score = 0.30·tanh(pnl/500)
      + 0.20·tanh(sharpe_like)
      + 0.15·(win_rate − 0.5)·2
      + 0.10·tanh(ev_capture)
      + 0.25·robustness_score
      − 0.20·tanh(drawdown/500)
      − 0.10·(number of warning flags)
score ×= 0.5   if fills < 30   (low-sample haircut)
```

The weights are deliberate: robustness (0.25) and PnL (0.30) matter most, but
warnings and a low sample actively pull a strategy down.

## Warning flags

| Flag                    | Triggered when…                                              |
|-------------------------|--------------------------------------------------------------|
| `LOW_SAMPLE`            | fewer than 30 fills — results are anecdotal                  |
| `PERFECT_WINRATE`       | ≥3 fills, all winners — almost certainly an artifact         |
| `LAGGING_MID_ARTIFACT`  | large avg edge + high win rate — edge may be a slow mid       |
| `REGIME_CONCENTRATION`  | one regime drives ≥80% of PnL — fragile                       |
| `HIGH_VARIANCE`         | stdev/|mean| of fill PnL is large — noisy                    |
| `TOO_FEW_EVENTS`        | fewer than 5 independent events — cannot generalize          |

## What the leaderboard makes obvious

- **High PnL, low sample** → low-sample haircut + `LOW_SAMPLE` flag.
- **High win rate, terrible tails** → drawdown penalty drags the score down.
- **Strong in one regime only** → `REGIME_CONCENTRATION` + low robustness.
- **Only works with zero slippage / one seed** → low `robustness_score`.

A strategy at the top of the board with no warnings and high robustness is a
*candidate for more research* — never a proven edge.
