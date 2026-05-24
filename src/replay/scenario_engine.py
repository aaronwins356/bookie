from __future__ import annotations

"""
Scenario engine. Generates realistic per-tick market evolution by driving
the simulation primitives (volatility, liquidity, spread, events) instead
of using hand-scripted prices. Fully deterministic given a seed.

Each scenario specifies a score trajectory and a per-tick volatility regime.
The mid price is a *lagging* tracker of fair value plus volatility noise and
event shocks — the lag (the market being slow to reprice after the score
changes) is exactly the edge the strategies are built to exploit.

Each generated tick carries a ScenarioContext alongside the GameState /
MarketState so the simulator can print regime, liquidity, and event detail.
"""

import math
import random
from dataclasses import dataclass
from typing import List, Tuple

from src.models import GameState, MarketState, GamePhase
from src.simulation.volatility import VolatilityEngine, VolatilityRegime
from src.simulation.liquidity import LiquidityEngine, LiquidityProfile
from src.simulation.spread_engine import SpreadEngine
from src.simulation.event_engine import EventEngine, MarketEvent, EventType
from src.simulation.market_regime import MarketRegime, RegimeInputs, RegimeClassifier


@dataclass
class _Step:
    vol: VolatilityRegime
    home: int
    away: int


@dataclass
class ScenarioContext:
    tick: int
    micro_regime: MarketRegime
    vol_regime: VolatilityRegime
    liquidity: LiquidityProfile
    event: MarketEvent
    mid: float
    spread: float
    odds_velocity: float


_C = VolatilityRegime.CALM
_T = VolatilityRegime.TRENDING
_P = VolatilityRegime.PANIC
_R = VolatilityRegime.REVERSAL
_D = VolatilityRegime.DEAD
_X = VolatilityRegime.CHAOTIC_ENDGAME

# Each scenario: a sequence of (volatility regime, home score, away score).
_SCENARIOS = {
    "calm": [
        _Step(_C, 0, 0), _Step(_C, 3, 0), _Step(_C, 7, 3),
        _Step(_C, 10, 3), _Step(_C, 13, 7), _Step(_C, 17, 7),
    ],
    "panic": [
        _Step(_C, 7, 0), _Step(_T, 14, 0), _Step(_P, 14, 14),
        _Step(_P, 14, 21), _Step(_R, 21, 21), _Step(_C, 24, 21),
    ],
    "liquidity_crisis": [
        _Step(_C, 7, 0), _Step(_D, 14, 0), _Step(_P, 21, 0),
        _Step(_D, 21, 3), _Step(_P, 28, 3), _Step(_C, 28, 7),
    ],
    "endgame_chaos": [
        _Step(_T, 17, 14), _Step(_R, 17, 17), _Step(_X, 20, 17),
        _Step(_X, 20, 20), _Step(_P, 23, 20), _Step(_X, 23, 23),
    ],
}

GeneratedTick = Tuple[GameState, List[MarketState], ScenarioContext]


class ScenarioEngine:
    def __init__(self, seed: int = 42, mid_lag: float = 0.35) -> None:
        self.seed = seed
        self.mid_lag = mid_lag
        self._rng = random.Random(seed)
        self.vol = VolatilityEngine(seed=seed)
        self.liq = LiquidityEngine(seed=seed + 1)
        self.spread = SpreadEngine()
        self.events = EventEngine(seed=seed + 2)
        self.classifier = RegimeClassifier()

    def available_scenarios(self) -> List[str]:
        return list(_SCENARIOS.keys())

    def generate(self, scenario: str, game_id: str = "sim-game") -> List[GeneratedTick]:
        program = _SCENARIOS.get(scenario)
        if program is None:
            raise ValueError(f"unknown scenario {scenario!r}; choose from {self.available_scenarios()}")

        ticks: List[GeneratedTick] = []
        mid = 50.0
        prev_mid = 50.0
        total_clock = 1800
        clock = total_clock
        tick_seconds = 300
        n = len(program)

        for i, step in enumerate(program, 1):
            score_diff = step.home - step.away
            time_pressure = 1.0 - (clock / total_clock)

            # Fair-value anchor (market is *slow* to reach this).
            anchor = self._anchor(score_diff, time_pressure)

            event = self.events.maybe_emit(time_remaining=clock)

            # Mid lags the anchor, then gets volatility noise + event shocks.
            mid += (anchor - mid) * self.mid_lag
            mid += self.vol.increment(step.vol)
            mid = self._apply_event_shock(event, mid)
            mid = max(2.0, min(98.0, mid))

            liq = self.liq.profile(step.vol, clock, total_clock)
            spread = self.spread.compute(
                regime=step.vol,
                liquidity_multiplier=liq.depth_multiplier,
                mid_price=mid,
                realized_vol=self.vol.realized_vol(step.vol),
            )

            odds_velocity = (mid - prev_mid) / max(1, tick_seconds)
            imbalance = self._imbalance(event, mid - prev_mid)

            micro = self.classifier.classify(RegimeInputs(
                spread=spread,
                odds_velocity=odds_velocity,
                liquidity_depth=liq.depth,
                volatility=self.vol.realized_vol(step.vol),
                time_remaining=clock,
                score_diff=score_diff,
                order_flow_imbalance=imbalance,
                mid_price=mid,
            ))

            game = GameState(
                game_id=game_id, sport="NFL",
                home_team="Eagles", away_team="Cowboys",
                home_score=step.home, away_score=step.away,
                phase=self._phase(i, n), clock_seconds=clock,
            )
            half = spread / 2.0
            market = MarketState(
                market_id=f"{game_id}-win", game_id=game_id,
                title="Home Win", yes_ask=round(mid + half, 1),
                yes_bid=round(mid - half, 1),
                volume=max(10, liq.depth * 2), open_interest=liq.depth,
            )
            ctx = ScenarioContext(
                tick=i, micro_regime=micro, vol_regime=step.vol,
                liquidity=liq, event=event, mid=round(mid, 1),
                spread=spread, odds_velocity=round(odds_velocity, 4),
            )
            ticks.append((game, [market], ctx))

            prev_mid = mid
            clock = max(0, clock - tick_seconds)

        return ticks

    def _anchor(self, score_diff: int, time_pressure: float) -> float:
        base = 1.0 / (1.0 + math.exp(-0.12 * score_diff))
        if base > 0.5:
            base += (1.0 - base) * time_pressure * 0.4
        elif base < 0.5:
            base -= base * time_pressure * 0.4
        return max(2.0, min(98.0, base * 100.0))

    def _apply_event_shock(self, event: MarketEvent, mid: float) -> float:
        if event.type in (EventType.PANIC_BUY, EventType.OVERREACTION):
            mid += event.magnitude
        elif event.type == EventType.PANIC_SELL:
            mid -= event.magnitude
        return mid

    def _imbalance(self, event: MarketEvent, delta: float) -> float:
        if event.type in (EventType.PANIC_BUY, EventType.OVERREACTION):
            return 0.8
        if event.type == EventType.PANIC_SELL:
            return -0.8
        return max(-1.0, min(1.0, delta / 5.0))

    def _phase(self, i: int, n: int) -> GamePhase:
        frac = i / n
        if frac <= 0.34:
            return GamePhase.FIRST_HALF
        if frac <= 0.67:
            return GamePhase.SECOND_HALF
        if frac < 1.0:
            return GamePhase.OVERTIME
        return GamePhase.FINAL
