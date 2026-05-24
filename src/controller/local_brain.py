from __future__ import annotations

"""
LocalBrain — placeholder for future LLM controller (e.g. Ollama / MCP).

Today it runs a simple deterministic observe→classify→route loop.
The LLM will eventually replace the classify step only; risk and execution
remain deterministic and cannot be overridden by any brain implementation.

Flow: observe → call_tools → classify_regime → route → summarize
"""

from typing import List, Any, Dict
from src.models import GameState, MarketState, Signal, Regime
from src.controller.tool_registry import ToolRegistry


class LocalBrain:
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def observe(self, game: GameState, markets: List[MarketState]) -> Dict[str, Any]:
        return {
            "game_id": game.game_id,
            "phase": game.phase.value,
            "score_diff": game.score_diff,
            "clock_seconds": game.clock_seconds,
            "market_ids": [m.market_id for m in markets],
        }

    def classify_regime(self, observation: Dict[str, Any]) -> Regime:
        """Deterministic regime classifier. LLM replaces this in the future."""
        clock = observation.get("clock_seconds", 9999)
        diff = abs(observation.get("score_diff", 0))

        if clock < 300 and diff > 14:
            return Regime.ENDGAME
        if diff > 7:
            return Regime.TRENDING
        return Regime.MEAN_REVERTING

    def route(self, signals: List[Signal]) -> List[Signal]:
        """Filter signals by regime coherence."""
        return [s for s in signals if s.is_actionable()]

    def summarize(self, signals: List[Signal], results: List[Any]) -> str:
        n_action = len([s for s in signals if s.is_actionable()])
        n_exec = len(results)
        return (
            f"Brain summary: {len(signals)} signals evaluated, "
            f"{n_action} actionable, {n_exec} orders submitted."
        )
