from __future__ import annotations

"""
Tennis live feed coordinator.

Wraps a TennisScoreProvider and exposes a simple polling loop that
yields (TennisState, timestamp) pairs. The caller is responsible for
pairing the states with market data and recording them.

This module does NOT connect to Kalshi. It only drives the score provider.
"""

import time
from datetime import datetime, timezone
from typing import Iterator, Optional, Tuple

from src.sports.tennis.provider_base import TennisScoreProvider
from src.sports.tennis.state import TennisState


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TennisLiveFeed:
    """
    Polls a TennisScoreProvider and yields successive TennisState snapshots.

    Usage:
        provider = MockProvider()
        feed = TennisLiveFeed(provider)
        for state, ts in feed.stream("MOCK-001", poll_interval=5.0):
            ...
    """

    def __init__(self, provider: TennisScoreProvider) -> None:
        self._provider = provider

    @property
    def provider(self) -> TennisScoreProvider:
        return self._provider

    def stream(
        self,
        match_id: str,
        poll_interval: float = 5.0,
        max_ticks: Optional[int] = None,
    ) -> Iterator[Tuple[TennisState, str]]:
        """
        Yield (TennisState, received_at_iso) indefinitely (or up to max_ticks).
        Uses the provider's stream_match_states() if available; falls back to
        repeated get_match_state() polls.
        """
        count = 0
        for state in self._provider.stream_match_states(match_id, poll_interval=poll_interval):
            ts = state.timestamp or utc_now_iso()
            yield state, ts
            count += 1
            if max_ticks is not None and count >= max_ticks:
                break

    def get_once(self, match_id: str) -> Tuple[TennisState, str]:
        """Single snapshot fetch."""
        state = self._provider.get_match_state(match_id)
        ts = state.timestamp or utc_now_iso()
        return state, ts

    def list_live(self):
        return self._provider.list_live_matches()
