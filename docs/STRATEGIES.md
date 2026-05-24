# Strategies

Each strategy implements a single method:

```python
def evaluate(self, features: FeatureSet) -> Signal
```

Strategies NEVER call the router, risk manager, or execution adapter.
They only observe features and return a Signal.

---

## FavoriteGrinder

**When**: Leading team is underpriced relative to fair value given score + time.

**Logic**:
- Compute fair value via `FairValueModel`
- If `fair_value - mid_price >= min_edge` and `score_diff > 0` → BUY
- Confidence scales with edge magnitude
- Ignores games within 3 points (too noisy)

---

## EndgameBonding

**When**: Late game (time_pressure > 0.85) with a large lead (> 10 points).

**Logic**:
- Market is slow to reach 95+ even when lead is decisive
- High confidence buy/sell depending on direction
- Confidence scales with time_pressure

---

## MomentumStrategy

**When**: Price moved more than `momentum_threshold` cents since last tick.

**Logic**:
- Maintains per-market previous mid price
- Large upward move → BUY; large downward move → SELL
- No signal on first tick (no previous reference)

---

## OverpricedFade

**When**: Market overprices YES by more than `fade_threshold` vs fair value.

**Logic**:
- Detects post-score overreaction
- Sells YES when `mid_price - fair_value >= fade_threshold`
- Mean-reversion regime

---

## LiquidityVacuum

**When**: Spread is wide AND volume is low AND price is at an extreme.

**Logic**:
- Identifies illiquid conditions (spread ≥ 6, volume ≤ 200)
- Fades price extremes (mid > 80 or mid < 20)
- Acts as a market-maker in thin books
