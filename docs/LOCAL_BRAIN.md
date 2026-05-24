# Local Brain (Controller)

## Philosophy

The brain is **NOT** the edge. The edge comes from market microstructure,
execution quality, regime understanding, liquidity behavior, emotional
overreaction, timing, and portfolio construction — all deterministic.

The brain is only a **coordinator, classifier, tool-caller, and
summarizer**. No brain implementation may bypass the deterministic
`RiskManager`. Math, risk, and execution stay deterministic.

## Loop

```
observe → call tools → classify regime → evaluate opportunities → route → summarize
```

- `observe(game, markets)` — build a state snapshot
- `inspect_regime(RegimeInputs)` — rich microstructure regime
- `evaluate_opportunities(signals, strategies, regime)` — rank by EV × regime compat
- `route(signals)` — filter to actionable (deterministic)
- `summarize_reasoning(...)` — natural-language summary via the active backend

## Backends (the future-model seam)

`BrainBackend` is a protocol with one method: `reason(prompt, context) -> str`.
It never returns orders — only narration.

| Backend                     | Status     | Notes                                  |
|-----------------------------|------------|----------------------------------------|
| `DeterministicBackend`      | active     | Templated, reproducible, no model      |
| `OllamaBackend`             | stub       | Future: POST to `localhost:11434`      |
| `OpenAICompatibleBackend`   | stub       | Future: vLLM / LM Studio `/v1` endpoint|
| `MCPToolProvider`           | stub       | Future: expose `ToolRegistry` over MCP |

Swap the backend at construction:

```python
brain = LocalBrain(registry, backend=OllamaBackend(model="llama3"))
```

Stubs raise `NotImplementedError` so they can never silently no-op in
production. When a real local model is added, it plugs in here — and still
cannot override risk or execution.
