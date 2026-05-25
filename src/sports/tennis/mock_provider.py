from __future__ import annotations

"""
Mock tennis score provider — deterministic in-memory data, no external calls.

Designed for:
- Unit tests that need realistic match states.
- CLI demos without a paid sports data subscription.
- Development of pairing / recording / bundling logic.

Provides three pre-canned matches in various states:
  1. Break-point drama (set 1, games 3-3, A at break point facing pressure)
  2. Post-break (A won first set 6-4, mid-second set, momentum)
  3. Tiebreak decider (sets 1-1, games 6-6, tiebreak in progress)

stream_match_states() advances the score by one point each call so
recorder integration tests get a non-static sequence.
"""

import time
from typing import Dict, Iterator, List, Optional

from src.sports.tennis.provider_base import TennisMatchInfo, TennisScoreProvider
from src.sports.tennis.state import Server, Surface, TennisState, Tour


# ---------------------------------------------------------------------------
# Static match snapshots
# ---------------------------------------------------------------------------

def _match_1() -> TennisState:
    """Break point drama — set 1, 3-3, A serving, 0-40."""
    return TennisState(
        match_id="MOCK-001",
        player_a="Djokovic N.",
        player_b="Alcaraz C.",
        tournament="Wimbledon 2026",
        tour=Tour.ATP,
        surface=Surface.GRASS,
        best_of=3,
        current_set=1,
        sets_a=0, sets_b=0,
        games_a=3, games_b=3,
        points_a=0, points_b=3,
        server=Server.A,
        tiebreak=False,
        timestamp="2026-07-04T14:08:00Z",
        metadata={"provider": "mock", "scenario": "break_point_drama"},
    )


def _match_2() -> TennisState:
    """Post-break — A leads 1-0 sets, 4-2 games in set 2, serving."""
    return TennisState(
        match_id="MOCK-002",
        player_a="Sinner J.",
        player_b="Zverev A.",
        tournament="US Open 2026",
        tour=Tour.ATP,
        surface=Surface.HARD,
        best_of=5,
        current_set=2,
        sets_a=1, sets_b=0,
        games_a=4, games_b=2,
        points_a=0, points_b=0,
        server=Server.A,
        tiebreak=False,
        timestamp="2026-08-29T19:15:00Z",
        metadata={"provider": "mock", "scenario": "post_break_momentum"},
    )


def _match_3() -> TennisState:
    """Tiebreak decider — sets 1-1, games 6-6, A leads 4-2 in tiebreak."""
    return TennisState(
        match_id="MOCK-003",
        player_a="Swiatek I.",
        player_b="Sabalenka A.",
        tournament="Roland Garros 2026",
        tour=Tour.WTA,
        surface=Surface.CLAY,
        best_of=3,
        current_set=3,
        sets_a=1, sets_b=1,
        games_a=6, games_b=6,
        points_a=4, points_b=2,
        server=Server.A,
        tiebreak=True,
        timestamp="2026-06-07T15:45:00Z",
        metadata={"provider": "mock", "scenario": "tiebreak_decider"},
    )


_STATIC_STATES: Dict[str, TennisState] = {
    "MOCK-001": _match_1(),
    "MOCK-002": _match_2(),
    "MOCK-003": _match_3(),
}

_STATIC_INFOS: List[TennisMatchInfo] = [
    TennisMatchInfo(
        match_id="MOCK-001",
        player_a="Djokovic N.",
        player_b="Alcaraz C.",
        tournament="Wimbledon 2026",
        tour=Tour.ATP,
        surface=Surface.GRASS,
        scheduled_start="2026-07-04T13:00:00Z",
        status="live",
    ),
    TennisMatchInfo(
        match_id="MOCK-002",
        player_a="Sinner J.",
        player_b="Zverev A.",
        tournament="US Open 2026",
        tour=Tour.ATP,
        surface=Surface.HARD,
        scheduled_start="2026-08-29T18:00:00Z",
        status="live",
    ),
    TennisMatchInfo(
        match_id="MOCK-003",
        player_a="Swiatek I.",
        player_b="Sabalenka A.",
        tournament="Roland Garros 2026",
        tour=Tour.WTA,
        surface=Surface.CLAY,
        scheduled_start="2026-06-07T14:00:00Z",
        status="live",
    ),
]


# ---------------------------------------------------------------------------
# MockProvider
# ---------------------------------------------------------------------------

class MockProvider(TennisScoreProvider):
    """
    In-memory provider for testing and development.

    list_live_matches() returns three pre-canned matches.
    get_match_state() returns a snapshot that advances by one tiebreak
    or game point each call (for realistic streaming simulation).
    stream_match_states() yields a finite sequence of advancing states.
    """

    def __init__(
        self,
        matches: Optional[List[TennisMatchInfo]] = None,
        states: Optional[Dict[str, TennisState]] = None,
        stream_ticks: int = 5,
        poll_interval: float = 0.0,   # 0 = instant for tests
    ) -> None:
        self._infos = matches if matches is not None else list(_STATIC_INFOS)
        # Deep-copy states so tests don't bleed into each other
        self._states: Dict[str, TennisState] = {}
        base = states if states is not None else _STATIC_STATES
        for mid, s in base.items():
            self._states[mid] = TennisState.from_dict(s.to_dict())
        self._stream_ticks = stream_ticks
        self._poll_interval = poll_interval
        self._call_counts: Dict[str, int] = {}

    def list_live_matches(self) -> List[TennisMatchInfo]:
        return list(self._infos)

    def get_match_state(self, match_id: str) -> TennisState:
        if match_id not in self._states:
            raise KeyError(f"Unknown match_id: {match_id!r}")
        self._call_counts[match_id] = self._call_counts.get(match_id, 0) + 1
        state = self._states[match_id]
        # Advance by one point on each repeated call so streaming is realistic
        if self._call_counts[match_id] > 1:
            self._states[match_id] = _advance_one_point(state)
        return TennisState.from_dict(self._states[match_id].to_dict())

    def stream_match_states(
        self,
        match_id: str,
        poll_interval: float = 5.0,
    ) -> Iterator[TennisState]:
        for _ in range(self._stream_ticks):
            yield self.get_match_state(match_id)
            if self._poll_interval > 0:
                time.sleep(self._poll_interval)

    def provider_name(self) -> str:
        return "MockProvider"


# ---------------------------------------------------------------------------
# Score advancement helper
# ---------------------------------------------------------------------------

def _advance_one_point(state: TennisState) -> TennisState:
    """
    Return a new TennisState with one point added to player A
    (so streaming tests see changing scores). Does not model
    full game/set completion — just increments points.
    """
    d = state.to_dict()
    d["points_a"] = min(d["points_a"] + 1, 7)  # cap to avoid overflow in tests
    return TennisState.from_dict(d)
