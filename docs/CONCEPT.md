# Concept

## What is bookie?

Bookie is a modular prediction-market trading engine for sports events.
It is designed to trade on exchanges like Kalshi where outcomes are priced
as binary contracts (YES/NO, 0–100 cents).

## Why modular?

Each concern is isolated so it can be swapped, tested, or audited independently:

| Layer       | Responsibility                          | Swappable?       |
|-------------|------------------------------------------|------------------|
| Adapters    | Fetch game/market data, submit orders   | Yes (mock → live)|
| Engine      | Features, fair value, routing, risk     | Config only      |
| Strategies  | Generate signals from features          | Yes (add/remove) |
| Controller  | Observe → classify → route loop         | Yes (LLM later)  |

## The signal pipeline

```
GameState + MarketState
        ↓
   FeatureExtractor
        ↓
   Strategy.evaluate()  →  Signal
        ↓
     Router             →  OrderIntent
        ↓
   RiskManager          →  approve / veto
        ↓
  ExecutionAdapter      →  ExecutionResult
        ↓
     AuditLog
```

## Future LLM role

The local brain (Ollama / MCP) will:
1. Observe the current state snapshot
2. Call registered tools (get_features, list_signals, submit_to_router, etc.)
3. Classify the market regime
4. Optionally override strategy weights (NOT risk rules)
5. Summarize the tick for logging

The LLM never touches execution or risk directly.
