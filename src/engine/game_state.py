from __future__ import annotations

from typing import Dict, Optional
from src.models import GameState


class GameStateEngine:
    """Maintains and exposes the latest game snapshots."""

    def __init__(self) -> None:
        self._states: Dict[str, GameState] = {}

    def update(self, state: GameState) -> None:
        self._states[state.game_id] = state

    def get(self, game_id: str) -> Optional[GameState]:
        return self._states.get(game_id)

    def all(self) -> list[GameState]:
        return list(self._states.values())

    def live_games(self) -> list[GameState]:
        from src.models import GamePhase
        terminal = {GamePhase.FINAL, GamePhase.PRE_GAME}
        return [g for g in self._states.values() if g.phase not in terminal]
