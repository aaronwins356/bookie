from __future__ import annotations

from typing import Dict, Optional
from src.models import MarketState


class MarketStateEngine:
    """Maintains and exposes the latest market snapshots."""

    def __init__(self) -> None:
        self._states: Dict[str, MarketState] = {}

    def update(self, state: MarketState) -> None:
        self._states[state.market_id] = state

    def get(self, market_id: str) -> Optional[MarketState]:
        return self._states.get(market_id)

    def all(self) -> list[MarketState]:
        return list(self._states.values())

    def open_markets(self) -> list[MarketState]:
        return [m for m in self._states.values() if m.is_open]
