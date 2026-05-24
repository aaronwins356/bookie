from __future__ import annotations

"""
Loads scripted replay scenarios. Each scenario is a list of ticks;
each tick contains a GameState + list of MarketState snapshots.
"""

from typing import List, Tuple
from src.models import GameState, MarketState, GamePhase


Tick = Tuple[GameState, List[MarketState]]


def _make_market(game_id: str, mid: float, spread: float = 4.0, volume: int = 300) -> MarketState:
    half = spread / 2.0
    return MarketState(
        market_id=f"{game_id}-win",
        game_id=game_id,
        title=f"{game_id} Home Win",
        yes_ask=mid + half,
        yes_bid=mid - half,
        volume=volume,
        open_interest=80,
        is_open=True,
    )


class SampleDataLoader:
    """Returns a list of (GameState, [MarketState]) ticks for replay."""

    def load_nfl_comeback(self) -> List[Tick]:
        """Home team trails by 14 at half, wins in overtime."""
        game_id = "nfl-2024-001"
        return [
            (
                GameState(game_id, "NFL", "Eagles", "Cowboys", 0, 14,
                          GamePhase.HALFTIME, 0),
                [_make_market(game_id, 22.0, 6.0, 120)],
            ),
            (
                GameState(game_id, "NFL", "Eagles", "Cowboys", 7, 14,
                          GamePhase.SECOND_HALF, 1200),
                [_make_market(game_id, 28.0, 5.0, 280)],
            ),
            (
                GameState(game_id, "NFL", "Eagles", "Cowboys", 14, 14,
                          GamePhase.SECOND_HALF, 300),
                [_make_market(game_id, 50.0, 4.0, 600)],
            ),
            (
                GameState(game_id, "NFL", "Eagles", "Cowboys", 21, 14,
                          GamePhase.OVERTIME, 240),
                [_make_market(game_id, 72.0, 3.0, 900)],
            ),
            (
                GameState(game_id, "NFL", "Eagles", "Cowboys", 24, 14,
                          GamePhase.FINAL, 0),
                [_make_market(game_id, 98.0, 1.0, 1100)],
            ),
        ]

    def load_blowout(self) -> List[Tick]:
        """Home team dominates from start."""
        game_id = "nfl-2024-002"
        return [
            (
                GameState(game_id, "NFL", "Chiefs", "Raiders", 21, 0,
                          GamePhase.FIRST_HALF, 900),
                [_make_market(game_id, 78.0, 4.0, 400)],
            ),
            (
                GameState(game_id, "NFL", "Chiefs", "Raiders", 35, 7,
                          GamePhase.SECOND_HALF, 600),
                [_make_market(game_id, 88.0, 3.0, 750)],
            ),
            (
                GameState(game_id, "NFL", "Chiefs", "Raiders", 42, 7,
                          GamePhase.SECOND_HALF, 120),
                [_make_market(game_id, 62.0, 8.0, 200)],  # thin market, mispriced
            ),
        ]
