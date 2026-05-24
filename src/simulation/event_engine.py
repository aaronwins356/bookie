from __future__ import annotations

"""
Event engine. Injects discrete market/game events during replay:
scoring runs, panic, liquidity collapse, stale-quote bursts, and
emotional overreactions. Deterministic given a seed.
"""

import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class EventType(str, Enum):
    NONE = "NONE"
    SCORE_HOME = "SCORE_HOME"
    SCORE_AWAY = "SCORE_AWAY"
    PANIC_SELL = "PANIC_SELL"
    PANIC_BUY = "PANIC_BUY"
    LIQUIDITY_COLLAPSE = "LIQUIDITY_COLLAPSE"
    STALE_QUOTE = "STALE_QUOTE"
    OVERREACTION = "OVERREACTION"
    SPREAD_EXPLOSION = "SPREAD_EXPLOSION"


@dataclass
class MarketEvent:
    type: EventType
    magnitude: float       # event-specific scale (e.g. price shock cents)
    description: str


class EventEngine:
    def __init__(self, event_prob: float = 0.25, seed: int = 99) -> None:
        self.event_prob = event_prob
        self._rng = random.Random(seed)

    def maybe_emit(self, time_remaining: int = 1800) -> MarketEvent:
        """Possibly emit an event this tick. Endgame raises event odds."""
        prob = self.event_prob
        if time_remaining < 180:
            prob = min(1.0, prob * 2.0)

        if self._rng.random() > prob:
            return MarketEvent(EventType.NONE, 0.0, "no event")

        choices = [
            (EventType.SCORE_HOME, 7.0, "home team scores"),
            (EventType.SCORE_AWAY, 7.0, "away team scores"),
            (EventType.PANIC_SELL, 6.0, "panic selling cascade"),
            (EventType.PANIC_BUY, 6.0, "panic buying cascade"),
            (EventType.LIQUIDITY_COLLAPSE, 0.0, "liquidity withdrawn"),
            (EventType.STALE_QUOTE, 0.0, "quote feed stalls"),
            (EventType.OVERREACTION, 9.0, "market overreacts to event"),
            (EventType.SPREAD_EXPLOSION, 0.0, "spread blows out"),
        ]
        etype, mag, desc = self._rng.choice(choices)
        return MarketEvent(type=etype, magnitude=mag, description=desc)
