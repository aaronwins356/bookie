from __future__ import annotations

"""
DecisionLoop orchestrates one tick of the engine:
  1. Fetch game + market state
  2. Extract features
  3. Run all strategies → collect Signals
  4. Brain classifies regime, filters signals
  5. Router converts Signals → OrderIntents
  6. RiskManager evaluates each intent
  7. ExecutionEngine submits approved intents
  8. AuditLog records everything
"""

from typing import List, Tuple
from src.models import GameState, MarketState, Signal, OrderIntent, ExecutionResult
from src.engine.features import FeatureExtractor
from src.engine.router import Router
from src.engine.risk import RiskManager
from src.engine.execution import ExecutionEngine
from src.engine.audit import AuditLog
from src.controller.local_brain import LocalBrain


class DecisionLoop:
    def __init__(
        self,
        strategies: list,
        brain: LocalBrain,
        router: Router,
        risk: RiskManager,
        execution: ExecutionEngine,
        audit: AuditLog,
    ) -> None:
        self.strategies = strategies
        self.brain = brain
        self.router = router
        self.risk = risk
        self.execution = execution
        self.audit = audit
        self._features = FeatureExtractor()

    def tick(
        self, game: GameState, markets: List[MarketState]
    ) -> Tuple[List[Signal], List[ExecutionResult]]:
        signals: List[Signal] = []
        results: List[ExecutionResult] = []

        observation = self.brain.observe(game, markets)
        regime = self.brain.classify_regime(observation)

        for market in markets:
            features = self._features.extract(game, market)
            for strategy in self.strategies:
                sig = strategy.evaluate(features)
                sig.regime = regime
                signals.append(sig)
                self.audit.record("signal", **{
                    "strategy": sig.strategy_name,
                    "direction": sig.direction.value,
                    "edge": sig.edge,
                    "confidence": sig.confidence,
                })

        actionable = self.brain.route(signals)

        for sig in actionable:
            intent = self.router.route(sig)
            if intent is None:
                continue

            market_snap = next((m for m in markets if m.market_id == sig.market_id), None)
            spread = market_snap.spread if market_snap else 0.0

            approved, reason = self.risk.evaluate(intent, spread)
            self.audit.record("risk", intent_id=intent.intent_id, approved=approved, reason=reason)

            if approved:
                result = self.execution.submit(intent)
                results.append(result)
                self.audit.record("execution", intent_id=intent.intent_id, status=result.status.value)
            else:
                self.audit.record("vetoed", intent_id=intent.intent_id, reason=reason)

        return signals, results
