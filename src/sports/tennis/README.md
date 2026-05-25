# Tennis Module

Tennis-specific modeling layer for the bookie trading research platform.

## Modules

| File | Purpose |
|------|---------|
| `state.py` | `TennisState` dataclass — canonical match snapshot |
| `scoring.py` | Pure scoring functions (deuce, break point, set/match winner) |
| `features.py` | `TennisFeatureExtractor` → `TennisFeatureSet` |
| `fair_value.py` | Heuristic logit-adjustment fair value model |
| `regimes.py` | `TennisRegimeClassifier` — 10-regime decision tree |
| `strategies.py` | 5 alpha strategies, each outputting `Signal` objects |
| `market_mapping.py` | Kalshi tennis market discovery helpers |
| `replay_adapter.py` | `TennisState` → `GameState` bridge for the backtest engine |

## Design Principles

- **No clock**: Tennis uses a score hierarchy (sets → games → points), not a timer.
- **Server identity is first-class**: Serve advantage varies by surface and situation.
- **Regime-gated strategies**: Each strategy declares which regimes it respects and blocks most activity in chaotic situations (tiebreak, match point, low liquidity).
- **Heuristic, not fitted**: The fair value model is a starting point. It is NOT proven live edge. Backtest across 50+ matches before trusting any signals.
- **Existing pipeline compatibility**: `TennisState` converts to `GameState` via `replay_adapter.py` so the existing backtest engine requires no changes.

## Regimes (Priority Order)

1. `RETIREMENT_RISK` — player retired
2. `SUSPENDED_OR_DELAYED` — rain / medical delay
3. `LOW_LIQUIDITY` — spread ≥ 8¢ or liquidity score < 0.25
4. `MATCH_POINT_PRESSURE` — either player can win the match next point
5. `TIEBREAK_CHAOS` — in a tiebreak
6. `SET_POINT_PRESSURE` — set point for either player
7. `BREAK_POINT_PRESSURE` — returner can win game next point
8. `POST_BREAK_OVERREACTION` — |implied − rough_fair| ≥ 12%
9. `SERVER_PRESSURE` — sustained return pressure on server
10. `CALM_HOLD_PATTERN` — default

## Strategies

| Strategy | Regime | Direction |
|----------|--------|-----------|
| `TennisFavoriteHold` | CALM / MEAN_REVERSION | Follow set leader |
| `TennisBreakPointOverreaction` | BREAK_POINT_PRESSURE | Fade market panic |
| `TennisPostBreakReversion` | POST_BREAK_OVERREACTION | Fade spike |
| `TennisTiebreakChaosAvoider` | TIEBREAK_CHAOS | Almost always HOLD |
| `TennisMomentumContinuation` | TRENDING | Follow momentum |

## Safety

- No orders are submitted anywhere in this module.
- All outputs are `Signal` objects consumed by the research pipeline.
- `TennisTiebreakChaosAvoider` returns HOLD in ~95% of tiebreak situations by design.
