# Tennis Strategies

## Overview

Five strategies cover the main alpha theses in tennis prediction markets:
overreaction to score events and mispricing of server/returner dynamics.

All strategies are read-only research tools — they produce `Signal` objects,
never order intents.

---

## Strategy 1 — TennisFavoriteHold

**Thesis**: Markets underestimate the difficulty of coming back from a set down,
especially on fast surfaces (grass, hard) and in best-of-5 formats.

**When it fires**:
- Set lead > 0 (A leads) with edge ≥ 3.0¢ → BUY
- Set lead < 0 (B leads) with edge ≥ 3.0¢ → SELL

**Held back by**: TIEBREAK_CHAOS, MATCH_POINT_PRESSURE, RETIREMENT_RISK,
LOW_LIQUIDITY, SUSPENDED_OR_DELAYED.

**Confidence cap**: 0.85

**Market regime fit**: CALM, MEAN_REVERSION, DEAD_MARKET (1.0); LIQUIDITY_COLLAPSE,
ENDGAME_CHAOS, PANIC_BUYING (0.1).

---

## Strategy 2 — TennisBreakPointOverreaction

**Thesis**: At break point, markets overreact — implied probability shifts more
than the ~35-40% historical break rate warrants. The server holds more often
than panicked markets price in.

**When it fires**:
- `break_point = True`
- `market_overreaction_score ≥ 0.08`
- Edge ≥ 2.5¢

**Direction**: Fades the overreaction (backs server recovery).

**Confidence formula**: `min(0.75, 0.45 + overreaction_score × 2.0)`

**Market regime fit**: MEAN_REVERSION, PANIC_SELLING, PANIC_BUYING (1.0);
LIQUIDITY_COLLAPSE, TRENDING_UP, TRENDING_DOWN (0.2).

---

## Strategy 3 — TennisPostBreakReversion

**Thesis**: After a break of serve, the breaker's probability is typically
over-extended beyond what the new game state warrants. The market moves too far.

**When it fires**:
- `tennis_regime = POST_BREAK_OVERREACTION`
- `market_overreaction_score ≥ 0.08`
- Edge ≥ 2.0¢

**Direction**: Fades the post-break spike.

**Confidence cap**: 0.72

**Market regime fit**: MEAN_REVERSION, FAVORITE_EUPHORIA (1.0);
TRENDING_UP, TRENDING_DOWN, PANIC_BUYING (0.15).

---

## Strategy 4 — TennisTiebreakChaosAvoider

**Thesis**: Tiebreaks are low-predictability situations. Markets thin out, spreads
widen, and random mini-runs determine outcomes. The primary contribution is NOT
trading — avoiding bad fills in tiebreaks is positive EV.

**When it fires (rarely)**:
- `tiebreak = True`
- `liquidity_score ≥ 0.50`
- `match_point = False`
- `market_overreaction_score ≥ 0.20` (very high threshold)
- Edge ≥ 4.0¢

**Confidence cap**: 0.45 (even when entering, very uncertain)

**Market regime fit**: CALM, DEAD_MARKET (1.0); ENDGAME_CHAOS, PANIC_BUYING,
PANIC_SELLING, LIQUIDITY_COLLAPSE (0.05).

---

## Strategy 5 — TennisMomentumContinuation

**Thesis**: When one player has strong momentum (consecutive games, set lead),
the market sometimes lags repricing — especially on fast surfaces and after
dominant service games. The strategy follows momentum when the market hasn't
fully adjusted.

**When it fires**:
- `|momentum_proxy| ≥ 0.35`
- Edge ≥ 2.5¢
- Momentum direction agrees with edge direction

**Direction**: BUY when momentum_proxy > 0 and edge > 0; SELL when both negative.

**Confidence formula**: `min(0.80, 0.40 + |momentum| × 0.5 + fair_confidence × 0.2)`

**Market regime fit**: TRENDING_UP, TRENDING_DOWN, CALM, FAVORITE_EUPHORIA (1.0);
MEAN_REVERSION, DEAD_MARKET, LIQUIDITY_COLLAPSE (0.15).

---

## Combining Strategies

The existing `PortfolioRouter` uses `regime_compatibility(MarketRegime)` scores
to weight and rank strategies. Tennis strategies participate in the router
identically to existing strategies — no router changes needed.

When multiple strategies fire simultaneously, the router's existing conflict
resolution (highest confidence / regime-adjusted score) applies.

---

## Research Warnings

- All fair value estimates are heuristic. Coefficients are based on published
  win-probability research but not calibrated to specific tours, players, or surfaces.
- Backtest across 50+ matches before trusting any strategy's edge.
- Do not deploy any strategy live without understanding its failure modes.
