from __future__ import annotations

from typing import List
from src.models import MarketState


class MockMarketAdapter:
    """Returns static / scripted market snapshots for replay."""

    def fetch(self, market_id: str) -> MarketState:
        return MarketState(
            market_id=market_id,
            game_id="game-001",
            title=f"Mock Market {market_id}",
            yes_ask=55.0,
            yes_bid=50.0,
            volume=500,
            open_interest=120,
            is_open=True,
        )

    def fetch_all(self, game_id: str) -> List[MarketState]:
        return [self.fetch(f"{game_id}-win"), self.fetch(f"{game_id}-spread")]
