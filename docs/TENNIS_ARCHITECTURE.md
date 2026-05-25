# Tennis Architecture

## Overview

Tennis is the primary sport in bookie. The tennis layer sits in `src/sports/tennis/` and plugs into the existing backtest and simulation pipeline without modifying any existing files except:
- `src/live/market_discovery.py` — added `sport` and `query` filter params
- `src/live/cli.py` — added `--sport` and `--query` to `list-markets`

## Data Flow

```
TennisState (match snapshot)
    │
    ├─► TennisFeatureExtractor ──► TennisFeatureSet
    │         │
    │         └─► TennisRegimeClassifier ──► TennisRegime
    │                   │
    │                   └─► Strategy.evaluate(features, state, regime) ──► Signal
    │
    └─► replay_adapter.tennis_state_to_game_state() ──► GameState
              │
              └─► Existing BacktestEngine / RiskManager / PortfolioRouter
```

## Module Descriptions

### `state.py` — TennisState

Canonical snapshot of a live match. Contains:
- Player names, tournament, tour (ATP/WTA/CHALLENGER/ITF), surface (hard/clay/grass/indoor)
- Score: `sets_a`, `sets_b`, `games_a`, `games_b`, `points_a`, `points_b`
- Server identity, tiebreak flag, retired/suspended flags
- Derived properties: `set_lead`, `game_lead`, `point_lead`, `match_over`, `is_final_set`
- Serialisation: `to_dict()` / `from_dict()`

### `scoring.py` — Pure Scoring Functions

All functions are pure (no side effects). Key functions:
- `is_break_point(state)` — returner can win game next point (False in tiebreaks)
- `break_point_count(state)` — 1, 2, or 3 break points
- `is_set_point(state)` — either player one point from winning the set
- `is_match_point(state)` — set point AND winning it wins the match
- `parse_score_string("6-4 3-2 30-15")` → `(sets_a, sets_b, games_a, games_b, pts_a, pts_b)`

### `features.py` — TennisFeatureSet

Extracted from `(TennisState, MarketState)`. Normalized to [-1,1] or [0,1] where possible:
- Score position: `set_lead`, `game_lead`, `point_lead`
- Pressure flags: `break_point`, `set_point`, `match_point`, `tiebreak`, `deuce`
- Momentum: `momentum_proxy` (−1 to +1)
- Market: `market_mid`, `market_spread`, `liquidity_score`, `market_overreaction_score`

`market_overreaction_score` = `min(1.0, |implied − rough_fair| / 0.20)` where `rough_fair` uses only set/game position (no market data). This is the key signal for reversion strategies.

### `fair_value.py` — TennisFairValueModel

Logit-adjustment model:
1. Set score: ±0.70 logit per set of lead
2. Game lead: ±0.10/game (capped at ±0.50)
3. Server on surface: grass=0.15, hard=0.10, indoor=0.12, clay=0.06
4. Tiebreak point lead: ±0.15/pt (capped at ±1.0)
5. Pressure: match_point ±0.10, set_point ±0.05, break_point ±0.08

**WARNING**: This model is heuristic, not empirically fitted. It is a starting point for research, not a proven edge.

### `regimes.py` — TennisRegimeClassifier

10-regime priority decision tree (see README.md for priority order). Used to gate strategy activity — most strategies HOLD in TIEBREAK_CHAOS, MATCH_POINT_PRESSURE, and LOW_LIQUIDITY.

### `strategies.py` — 5 Strategies

Each strategy implements:
- `evaluate(features, state, tennis_regime) → Signal`
- `regime_compatibility(MarketRegime) → float` (0–1, for router ranking)

### `market_mapping.py` — Kalshi Tennis Market Discovery

Helpers for filtering Kalshi markets to tennis-specific ones. No API calls — pure filtering logic applied to results from `KalshiRestClient`.

### `replay_adapter.py` — GameState Bridge

Converts `TennisState` → `GameState` for the existing backtest engine:
- `home_team` = player_a, `away_team` = player_b
- `home_score` = sets_a, `away_score` = sets_b
- `clock_seconds` = 0 (tennis has no clock)
- Full `TennisState.to_dict()` stored in `metadata["tennis_state"]`
- `extract_tennis_state(game_state)` reverses the conversion

## Adding New Tennis Strategies

1. Add a class to `strategies.py` with `NAME`, `evaluate()`, and `regime_compatibility()`.
2. Add the class to `ALL_TENNIS_STRATEGIES`.
3. Add tests to `tests/test_tennis_strategies.py`.

## Safety Boundaries

- No order submission code exists anywhere in `src/sports/`.
- All strategies output `Signal` objects consumed by the research pipeline.
- The pipeline's `RiskManager` and position limits remain unchanged.
