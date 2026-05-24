from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any


class GamePhase(str, Enum):
    PRE_GAME = "PRE_GAME"
    FIRST_HALF = "FIRST_HALF"
    HALFTIME = "HALFTIME"
    SECOND_HALF = "SECOND_HALF"
    OVERTIME = "OVERTIME"
    FINAL = "FINAL"


@dataclass
class GameState:
    """Snapshot of the live game."""

    game_id: str
    sport: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    phase: GamePhase
    clock_seconds: int         # seconds remaining in current period
    possession: Optional[str] = None   # team name or None
    down_and_distance: Optional[str] = None  # football-specific
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def score_diff(self) -> int:
        return self.home_score - self.away_score

    @property
    def total_score(self) -> int:
        return self.home_score + self.away_score

    @property
    def is_final(self) -> bool:
        return self.phase == GamePhase.FINAL


@dataclass
class MarketState:
    """Snapshot of a prediction-market contract."""

    market_id: str
    game_id: str
    title: str
    yes_ask: float    # best ask for YES contracts (cents)
    yes_bid: float    # best bid for YES contracts (cents)
    volume: int       # total contracts traded
    open_interest: int
    is_open: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def mid(self) -> float:
        return (self.yes_ask + self.yes_bid) / 2.0

    @property
    def spread(self) -> float:
        return self.yes_ask - self.yes_bid
