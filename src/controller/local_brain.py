from __future__ import annotations

"""
LocalBrain — the orchestration / coordination layer.

DESIGN PHILOSOPHY: the brain is NOT the edge. It is a coordinator, a
classifier, a tool-caller, and a summarizer. All math, risk, and execution
are deterministic and live elsewhere. No brain implementation — present or
future (Ollama / OpenAI-compatible / MCP) — may bypass the RiskManager.

Today the default backend is fully deterministic. The `BrainBackend`
protocol and the stub backends below define the seam where a real local
model will plug in later.

Loop: observe → call tools → classify regime → evaluate → route → summarize
"""

from dataclasses import dataclass, field
from typing import List, Any, Dict, Optional, Protocol, runtime_checkable

from src.models import GameState, MarketState, Signal, Regime
from src.controller.tool_registry import ToolRegistry
from src.simulation.market_regime import MarketRegime, RegimeInputs, RegimeClassifier


# ---------------------------------------------------------------------------
# Backend seam — future model integrations implement this protocol.
# ---------------------------------------------------------------------------
@runtime_checkable
class BrainBackend(Protocol):
    name: str

    def reason(self, prompt: str, context: Dict[str, Any]) -> str:
        """Produce a natural-language reasoning summary. Never returns orders."""
        ...


@dataclass
class DeterministicBackend:
    """Default backend. Pure templated reasoning — no model, fully reproducible."""

    name: str = "deterministic"

    def reason(self, prompt: str, context: Dict[str, Any]) -> str:
        regime = context.get("regime", "UNKNOWN")
        n = context.get("n_opportunities", 0)
        return f"[{self.name}] regime={regime}; {n} ranked opportunity(ies); {prompt}"


@dataclass
class OllamaBackend:
    """
    Stub for a local Ollama model. Not wired up — raises on use so it can
    never silently no-op in production. Future: POST to /api/chat.
    """

    model: str = "llama3"
    host: str = "http://localhost:11434"
    name: str = "ollama"

    def reason(self, prompt: str, context: Dict[str, Any]) -> str:
        raise NotImplementedError("OllamaBackend not yet implemented (see docs/LOCAL_BRAIN.md).")


@dataclass
class OpenAICompatibleBackend:
    """Stub for any OpenAI-compatible chat endpoint (vLLM, LM Studio, etc.)."""

    model: str = "local-model"
    base_url: str = "http://localhost:8000/v1"
    name: str = "openai-compatible"

    def reason(self, prompt: str, context: Dict[str, Any]) -> str:
        raise NotImplementedError("OpenAICompatibleBackend not yet implemented.")


@dataclass
class MCPToolProvider:
    """
    Future MCP exposure: advertises the ToolRegistry's tools as MCP tool
    definitions so an external MCP client can drive the brain. Stub only.
    """

    registry: ToolRegistry

    def list_mcp_tools(self) -> List[Dict[str, str]]:
        return [{"name": t, "description": f"bookie tool: {t}"} for t in self.registry.list_tools()]

    def serve(self) -> None:
        raise NotImplementedError("MCP server not yet implemented.")


# ---------------------------------------------------------------------------
# The brain itself.
# ---------------------------------------------------------------------------
@dataclass
class Opportunity:
    strategy_name: str
    market_id: str
    direction: str
    ev: float
    confidence: float
    regime_compat: float
    score: float


class LocalBrain:
    def __init__(
        self,
        registry: ToolRegistry,
        backend: Optional[BrainBackend] = None,
        classifier: Optional[RegimeClassifier] = None,
    ) -> None:
        self._registry = registry
        self.backend: BrainBackend = backend or DeterministicBackend()
        self._classifier = classifier or RegimeClassifier()
        self._last_micro_regime: MarketRegime = MarketRegime.CALM

    # ---- observe ------------------------------------------------------
    def observe(self, game: GameState, markets: List[MarketState]) -> Dict[str, Any]:
        return {
            "game_id": game.game_id,
            "phase": game.phase.value,
            "score_diff": game.score_diff,
            "clock_seconds": game.clock_seconds,
            "market_ids": [m.market_id for m in markets],
            "mid_prices": {m.market_id: m.mid for m in markets},
            "spreads": {m.market_id: m.spread for m in markets},
        }

    # ---- tool calling -------------------------------------------------
    def call_tool(self, name: str, **kwargs: Any) -> Any:
        """All tool access goes through the registry; deterministic tools
        downstream still enforce their own rules."""
        return self._registry.call(name, **kwargs)

    # ---- regime classification ---------------------------------------
    def classify_regime(self, observation: Dict[str, Any]) -> Regime:
        """Lightweight strategy-facing regime (backward-compatible)."""
        clock = observation.get("clock_seconds", 9999)
        diff = abs(observation.get("score_diff", 0))
        if clock < 300 and diff > 14:
            return Regime.ENDGAME
        if diff > 7:
            return Regime.TRENDING
        return Regime.MEAN_REVERTING

    def inspect_regime(self, inputs: RegimeInputs) -> MarketRegime:
        """Rich microstructure regime via the deterministic classifier."""
        self._last_micro_regime = self._classifier.classify(inputs)
        return self._last_micro_regime

    # ---- opportunity evaluation --------------------------------------
    def evaluate_opportunities(
        self,
        signals: List[Signal],
        strategies_by_name: Dict[str, Any],
        regime: MarketRegime,
    ) -> List[Opportunity]:
        from src.strategies.base import expected_value

        opps: List[Opportunity] = []
        for sig in signals:
            if not sig.is_actionable():
                continue
            strat = strategies_by_name.get(sig.strategy_name)
            compat = strat.regime_compatibility(regime) if strat is not None else 0.5
            ev = expected_value(sig)
            opps.append(Opportunity(
                strategy_name=sig.strategy_name,
                market_id=sig.market_id,
                direction=sig.direction.value,
                ev=ev,
                confidence=sig.confidence,
                regime_compat=compat,
                score=round(ev * compat, 4),
            ))
        return sorted(opps, key=lambda o: -o.score)

    # ---- routing (backward-compatible filter) ------------------------
    def route(self, signals: List[Signal]) -> List[Signal]:
        return [s for s in signals if s.is_actionable()]

    # ---- summarize ----------------------------------------------------
    def summarize_reasoning(
        self,
        regime: MarketRegime,
        opportunities: List[Opportunity],
        n_executed: int,
    ) -> str:
        context = {
            "regime": regime.value,
            "n_opportunities": len(opportunities),
            "n_executed": n_executed,
        }
        top = opportunities[0] if opportunities else None
        prompt = (
            f"top={top.strategy_name}/{top.direction} (score {top.score})"
            if top else "no actionable opportunities"
        )
        return self.backend.reason(prompt, context)

    def summarize(self, signals: List[Signal], results: List[Any]) -> str:
        n_action = len([s for s in signals if s.is_actionable()])
        return (
            f"Brain summary: {len(signals)} signals evaluated, "
            f"{n_action} actionable, {len(results)} orders submitted."
        )
