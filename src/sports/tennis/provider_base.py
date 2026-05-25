from __future__ import annotations

"""
Abstract base class for tennis score data providers.

Implementations must return TennisState objects so the match_pairing
and live_recorder modules can operate against any feed uniformly.

Current implementations:
  - MockProvider  (src/sports/tennis/mock_provider.py) — in-memory fake data
  Future:
  - SportradarProvider, GeniusSportsProvider, etc.

IMPORTANT: Providers supply match state only. No orders are placed.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional

from src.sports.tennis.state import Surface, TennisState, Tour


@dataclass
class TennisMatchInfo:
    """
    Lightweight match descriptor returned by list_live_matches().
    Contains just enough to pair with a Kalshi market; full state
    is fetched via get_match_state().
    """
    match_id: str
    player_a: str
    player_b: str
    tournament: str
    tour: Tour = Tour.UNKNOWN
    surface: Surface = Surface.UNKNOWN
    scheduled_start: Optional[str] = None   # ISO UTC if known
    status: str = "live"                    # "live", "scheduled", "finished"
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return f"{self.player_a} vs {self.player_b} ({self.tournament})"


class TennisScoreProvider(ABC):
    """
    Interface all tennis score providers must implement.

    Providers are read-only. No write/order methods are defined here.
    """

    @abstractmethod
    def list_live_matches(self) -> List[TennisMatchInfo]:
        """
        Return all currently live (or recently started) matches.
        Should return an empty list if no matches are live.
        """

    @abstractmethod
    def get_match_state(self, match_id: str) -> TennisState:
        """
        Return the current state for a single match.
        Raises KeyError if match_id is unknown.
        """

    @abstractmethod
    def stream_match_states(
        self,
        match_id: str,
        poll_interval: float = 5.0,
    ) -> Iterator[TennisState]:
        """
        Yield successive TennisState snapshots for a match.
        Implementations may poll or use push subscriptions.
        The caller is responsible for breaking out of the iterator.

        poll_interval: seconds between polls for polling implementations.
        """

    def provider_name(self) -> str:
        return type(self).__name__
