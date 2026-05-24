from __future__ import annotations

"""
Replay store. Serializes / deserializes replay scenarios (lists of
game+market ticks) to JSON so scenarios can be saved, shared, and rerun
deterministically.
"""

import json
from pathlib import Path
from typing import List, Tuple
from src.models import GameState, MarketState, GamePhase

Tick = Tuple[GameState, List[MarketState]]


class ReplayStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def save(self, ticks: List[Tick]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = []
        for game, markets in ticks:
            payload.append({
                "game": {
                    "game_id": game.game_id,
                    "sport": game.sport,
                    "home_team": game.home_team,
                    "away_team": game.away_team,
                    "home_score": game.home_score,
                    "away_score": game.away_score,
                    "phase": game.phase.value,
                    "clock_seconds": game.clock_seconds,
                },
                "markets": [{
                    "market_id": m.market_id,
                    "game_id": m.game_id,
                    "title": m.title,
                    "yes_ask": m.yes_ask,
                    "yes_bid": m.yes_bid,
                    "volume": m.volume,
                    "open_interest": m.open_interest,
                } for m in markets],
            })
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)

    def load(self) -> List[Tick]:
        with self.path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        ticks: List[Tick] = []
        for entry in payload:
            g = entry["game"]
            game = GameState(
                game_id=g["game_id"], sport=g["sport"],
                home_team=g["home_team"], away_team=g["away_team"],
                home_score=g["home_score"], away_score=g["away_score"],
                phase=GamePhase(g["phase"]), clock_seconds=g["clock_seconds"],
            )
            markets = [
                MarketState(
                    market_id=m["market_id"], game_id=m["game_id"], title=m["title"],
                    yes_ask=m["yes_ask"], yes_bid=m["yes_bid"],
                    volume=m["volume"], open_interest=m["open_interest"],
                )
                for m in entry["markets"]
            ]
            ticks.append((game, markets))
        return ticks
