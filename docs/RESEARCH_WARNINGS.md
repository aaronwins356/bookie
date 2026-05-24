# Research Warnings

This phase is about **honesty**. The goal is not to make strategies look good
— it is to find out which are real candidates, which are artifacts, and which
are too fragile. Bad results are useful. Fake edge must be exposed early.

The warnings below are raised conservatively by `src/backtest/significance.py`
and surfaced in run summaries, the leaderboard, `warnings.txt`, and the
research report.

## Fake edge

"Edge" that exists only because of a quirk of the simulation or data, not
because the strategy would profit against a real, adversarial market. The
whole harness is built to catch this before it reaches real capital.

## Lagging-mid artifact (`LAGGING_MID_ARTIFACT`)

The replay scenarios (and many historical feeds) use a mid price that **lags**
true probability — it is slow to reprice after a score change. A strategy can
look brilliant simply by buying into that lag. That is not tradeable edge; a
real market reprices instantly and you would not get those fills. Flagged when
average edge is large (≥12c) and win rate is high (≥70%).

## Overfitting

Tuning parameters on the same games used to evaluate them. Defend against it
with train/test or walk-forward splits (`src/backtest/splits.py`): tune on
train, report only on test. With the current tiny sample, *any* good result is
suspect — there is not enough data to tune honestly yet.

## Low sample size (`LOW_SAMPLE`, `TOO_FEW_EVENTS`)

A handful of fills or a single game proves nothing. Below 30 fills the
leaderboard applies a 0.5 haircut; below 5 independent events no
cross-event generalization is possible. Bootstrap confidence intervals
(`significance.bootstrap_ci`) will almost always cross zero at these sizes —
which is the honest answer.

## High variance (`HIGH_VARIANCE`)

When the standard deviation of per-fill PnL dwarfs the mean, the "average" is
meaningless noise. A positive mean PnL with high variance is not evidence of
edge.

## Slippage / latency / fee sensitivity (robustness)

A strategy that is profitable at zero slippage but collapses under realistic
costs has no edge. `src/backtest/robustness.py` reruns each config under:

- **worse_slippage** and **thin_liquidity** — higher slippage-impact coefficient
  (also stands in for wider spreads / thinner books, which are not direct config
  knobs in this phase)
- **higher_latency** — larger base latency
- **higher_fees** — higher per-contract fee
- **seed changes** — different RNG seeds

If PnL flips negative under any of these, a `COLLAPSES_UNDER_*` flag is raised
and the robustness score drops.

## Regime dependence (`REGIME_CONCENTRATION`)

If ≥80% of a strategy's PnL comes from a single market regime, it is fragile:
remove that regime and the edge vanishes. Real candidates work across several
regimes, or are explicitly scoped and sized for the one they target.

## Single-seed dependence (`SINGLE_SEED_DEPENDENT`)

If a strategy is profitable under only one RNG seed, its "edge" is luck in the
simulated draws, not structure.

## The bottom line

Simulated and historical replay performance — especially with fake fills and
tiny samples — is **not proof of live edge**. A clean leaderboard with no
warnings is a starting point for more research, never a green light to trade.
