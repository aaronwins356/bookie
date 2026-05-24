from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
from src.models import Signal, SignalDirection, OrderIntent, OrderSide
from src.simulation.market_regime import MarketRegime


class Router:
    """
    Converts a Signal into an OrderIntent.

    Rules:
    - BUY signal  → YES side at (fair_value - half_spread)
    - SELL signal → NO  side at (100 - fair_value - half_spread)
    - HOLD signal → None
    - Size is proportional to confidence (Kelly-lite, capped at max_size)
    """

    def __init__(self, base_size: int = 10, max_size: int = 50) -> None:
        self.base_size = base_size
        self.max_size = max_size

    def route(self, signal: Signal) -> Optional[OrderIntent]:
        if signal.direction == SignalDirection.HOLD:
            return None
        if not signal.is_actionable():
            return None

        side = OrderSide.YES if signal.direction == SignalDirection.BUY else OrderSide.NO
        limit_price = self._limit_price(signal, side)
        size = self._kelly_size(signal)

        return OrderIntent(
            market_id=signal.market_id,
            side=side,
            price=limit_price,
            size=size,
            strategy_name=signal.strategy_name,
            signal_id=signal.signal_id,
            notes=f"edge={signal.edge:.1f} conf={signal.confidence:.2f}",
        )

    def _limit_price(self, signal: Signal, side: OrderSide) -> float:
        half_spread = 0.5
        if side == OrderSide.YES:
            return round(signal.fair_value - half_spread, 1)
        else:
            return round(100.0 - signal.fair_value - half_spread, 1)

    def _kelly_size(self, signal: Signal) -> int:
        fraction = min(signal.confidence, 0.8)
        size = int(self.base_size * fraction * (abs(signal.edge) / 5.0))
        return max(1, min(size, self.max_size))


@dataclass
class RankedOpportunity:
    signal: Signal
    ev: float
    regime_compat: float
    score: float
    strategy_name: str


@dataclass
class PortfolioState:
    """Tracks what the allocator has already committed this session."""

    open_directions: Dict[str, SignalDirection] = field(default_factory=dict)  # market_id -> dir
    cooldowns: Dict[str, int] = field(default_factory=dict)                     # strategy -> ticks left
    active_strategies: set = field(default_factory=set)

    def tick_cooldowns(self) -> None:
        for k in list(self.cooldowns.keys()):
            self.cooldowns[k] -= 1
            if self.cooldowns[k] <= 0:
                del self.cooldowns[k]


class PortfolioRouter(Router):
    """
    Portfolio-aware allocator built on top of the base Router.

    Given a batch of signals for a tick (plus the active regime and the
    strategy objects that produced them), it:
      - ranks opportunities by EV × regime compatibility
      - skips strategies on cooldown
      - caps the number of concurrently active strategies
      - avoids duplicate directional exposure in the same market
      - avoids piling onto strongly correlated strategies
      - sizes dynamically off score and risk

    It still delegates the final Signal→OrderIntent conversion to
    Router.route(), so all base routing rules are preserved.
    """

    def __init__(
        self,
        base_size: int = 10,
        max_size: int = 50,
        max_concurrent_strategies: int = 3,
        cooldown_ticks: int = 2,
        correlation_threshold: float = 0.7,
    ) -> None:
        super().__init__(base_size=base_size, max_size=max_size)
        self.max_concurrent_strategies = max_concurrent_strategies
        self.cooldown_ticks = cooldown_ticks
        self.correlation_threshold = correlation_threshold

    def rank(
        self,
        signals: List[Signal],
        strategies_by_name: Dict[str, object],
        regime: MarketRegime,
    ) -> List[RankedOpportunity]:
        from src.strategies.base import expected_value

        ranked: List[RankedOpportunity] = []
        for sig in signals:
            if not sig.is_actionable():
                continue
            strat = strategies_by_name.get(sig.strategy_name)
            compat = strat.regime_compatibility(regime) if strat is not None else 0.5
            ev = expected_value(sig)
            ranked.append(RankedOpportunity(
                signal=sig,
                ev=ev,
                regime_compat=compat,
                score=round(ev * compat, 4),
                strategy_name=sig.strategy_name,
            ))
        return sorted(ranked, key=lambda r: -r.score)

    def allocate(
        self,
        signals: List[Signal],
        strategies_by_name: Dict[str, object],
        regime: MarketRegime,
        portfolio: PortfolioState,
        correlated_pairs: Optional[List[Tuple[str, str, float]]] = None,
    ) -> List[OrderIntent]:
        portfolio.tick_cooldowns()
        ranked = self.rank(signals, strategies_by_name, regime)

        correlated = self._correlation_blocklist(correlated_pairs or [])
        intents: List[OrderIntent] = []
        chosen_strategies: set = set()
        # Duplicate-exposure guard is scoped to THIS allocation batch: we
        # won't allocate two same-direction orders in the same market this
        # tick. (Cross-tick position lifecycle is out of scope for the sim.)
        batch_directions: Dict[str, SignalDirection] = {}

        for opp in ranked:
            sig = opp.signal

            if sig.strategy_name in portfolio.cooldowns:
                continue
            if len(chosen_strategies) >= self.max_concurrent_strategies:
                break

            if batch_directions.get(sig.market_id) == sig.direction:
                continue

            # Correlation guard: don't stack a strategy correlated with one
            # already chosen this tick.
            if any(other in correlated.get(sig.strategy_name, set()) for other in chosen_strategies):
                continue

            intent = self.route(sig)
            if intent is None:
                continue

            # Dynamic sizing: scale base intent by regime compatibility.
            intent.size = max(1, int(intent.size * (0.5 + 0.5 * opp.regime_compat)))

            intents.append(intent)
            chosen_strategies.add(sig.strategy_name)
            batch_directions[sig.market_id] = sig.direction
            portfolio.open_directions[sig.market_id] = sig.direction
            portfolio.active_strategies.add(sig.strategy_name)
            portfolio.cooldowns[sig.strategy_name] = self.cooldown_ticks

        return intents

    def _correlation_blocklist(
        self, pairs: List[Tuple[str, str, float]]
    ) -> Dict[str, set]:
        block: Dict[str, set] = {}
        for a, b, c in pairs:
            if abs(c) >= self.correlation_threshold:
                block.setdefault(a, set()).add(b)
                block.setdefault(b, set()).add(a)
        return block
