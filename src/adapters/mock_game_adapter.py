from __future__ import annotations

from src.models import GameState, GamePhase


class MockGameAdapter:
    """Returns scripted game snapshots for replay."""

    def fetch(self, game_id: str) -> GameState:
        return GameState(
            game_id=game_id,
            sport="NFL",
            home_team="Eagles",
            away_team="Cowboys",
            home_score=17,
            away_score=10,
            phase=GamePhase.SECOND_HALF,
            clock_seconds=480,
            possession="Eagles",
        )
