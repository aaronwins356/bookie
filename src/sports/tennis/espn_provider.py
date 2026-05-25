from __future__ import annotations

"""
ESPN tennis score provider adapter.

Attempts to fetch live tennis match data from ESPN's endpoints.
Designed to be resilient to:
  - Network failures (returns empty match list, not an exception)
  - API changes (returns partial TennisState with available fields)
  - Rate limiting (adds backoff)
  - Missing fields (safe None defaults)

IMPORTANT: ESPN API is undocumented and can change or break without notice.
This provider should not be your only data source for production systems.
Use MockProvider for tests and demos; EspnProvider for research only.

Current limitations:
  - No live point-by-point stream (ESPN updates every ~5-10s)
  - Limited surface/tour info (often inferred from tournament name)
  - Player names may have formatting inconsistencies
  - Tiebreak detection relies on game count (6-6 in set)
"""

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from src.sports.tennis.provider_base import TennisMatchInfo, TennisScoreProvider
from src.sports.tennis.state import Server, Surface, TennisState, Tour


logger = logging.getLogger(__name__)


class EspnProvider(TennisScoreProvider):
    """
    Adapter for ESPN tennis match data.

    Fetches from ESPN's live tennis endpoint and parses match state.
    Tolerates missing fields and API changes by returning partial state.

    Usage:
        provider = EspnProvider(timeout=10.0)
        matches = provider.list_live_matches()
        for match in matches:
            state = provider.get_match_state(match.match_id)
    """

    def __init__(
        self,
        base_url: str = "https://site.api.espn.com/apis/site/v2/sports/tennis",
        timeout: float = 10.0,
        max_retries: int = 2,
    ) -> None:
        self._base_url = base_url
        self._timeout = timeout
        self._max_retries = max_retries
        self._cache: Dict[str, Any] = {}
        self._cache_time: Dict[str, float] = {}
        self._cache_ttl = 5.0  # cache live data for 5 seconds

    def list_live_matches(self) -> List[TennisMatchInfo]:
        """
        Fetch live tennis matches from ESPN.
        Returns empty list on network error (rather than raising).
        """
        try:
            events = self._fetch_events()
            if not events:
                return []
            matches = [_parse_event_to_match_info(e) for e in events if e]
            return [m for m in matches if m]  # filter None
        except Exception as exc:
            logger.warning(f"EspnProvider.list_live_matches failed: {exc}")
            return []

    def get_match_state(self, match_id: str) -> TennisState:
        """
        Get current state for one match by match_id.
        Raises KeyError if match_id not found.
        """
        events = self._fetch_events()
        for event in events:
            if not event:
                continue
            parsed = _parse_event_to_state(event, match_id)
            if parsed and parsed.match_id == match_id:
                return parsed
        raise KeyError(f"Match {match_id!r} not found")

    def stream_match_states(
        self,
        match_id: str,
        poll_interval: float = 10.0,
    ) -> Iterator[TennisState]:
        """
        Yield successive TennisState snapshots by polling ESPN.
        Caller is responsible for breaking out of the iterator.
        """
        fail_count = 0
        while True:
            try:
                state = self.get_match_state(match_id)
                fail_count = 0
                yield state
            except KeyError:
                fail_count += 1
                if fail_count > 5:
                    logger.warning(f"Match {match_id} not found after 5 polls; stopping stream")
                    break
            except Exception as exc:
                fail_count += 1
                logger.warning(f"stream_match_states poll failed: {exc}")
                if fail_count > 5:
                    break
            time.sleep(poll_interval)

    def provider_name(self) -> str:
        return "EspnProvider"

    def _fetch_events(self) -> List[Dict[str, Any]]:
        """
        Fetch raw events JSON from ESPN API with caching.
        Returns empty list on failure.
        """
        cache_key = "live_events"
        now = time.time()
        if cache_key in self._cache_time and now - self._cache_time[cache_key] < self._cache_ttl:
            return self._cache.get(cache_key, [])

        try:
            url = f"{self._base_url}/competitions?limit=100"
            data = self._fetch_json(url)
            events = data.get("events", [])
            self._cache[cache_key] = events
            self._cache_time[cache_key] = now
            return events
        except Exception as exc:
            logger.warning(f"Failed to fetch events: {exc}")
            return []

    def _fetch_json(self, url: str) -> Dict[str, Any]:
        """
        Fetch and parse JSON from a URL with retries and timeout.
        Raises URLError or ValueError on failure.
        """
        headers = {"User-Agent": "bookie-tennis-provider/1.0"}
        for attempt in range(self._max_retries + 1):
            try:
                req = Request(url, headers=headers)
                with urlopen(req, timeout=self._timeout) as response:
                    body = response.read().decode("utf-8")
                    return json.loads(body)
            except (URLError, HTTPError) as exc:
                if attempt < self._max_retries:
                    time.sleep(0.5 * (attempt + 1))
                else:
                    raise
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON from {url}: {exc}") from exc


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_event_to_match_info(event: Dict[str, Any]) -> Optional[TennisMatchInfo]:
    """
    Convert raw ESPN event dict to TennisMatchInfo.
    Returns None if critical fields are missing.
    """
    try:
        event_id = event.get("id")
        name = event.get("name", "")
        status = event.get("status", {}).get("type", "")
        competitors = event.get("competitors", [])

        if not event_id or not competitors or len(competitors) < 2:
            return None

        comp_a = competitors[0]
        comp_b = competitors[1]
        player_a = comp_a.get("athlete", {}).get("displayName", "Unknown")
        player_b = comp_b.get("athlete", {}).get("displayName", "Unknown")

        if not player_a or not player_b:
            return None

        tournament = _extract_tournament(name)
        tour = _infer_tour(name)
        surface = _infer_surface(tournament)
        status_label = "live" if status and "in_progress" in status.lower() else "scheduled"

        return TennisMatchInfo(
            match_id=event_id,
            player_a=player_a,
            player_b=player_b,
            tournament=tournament,
            tour=tour,
            surface=surface,
            status=status_label,
        )
    except Exception as exc:
        logger.debug(f"Failed to parse event to match info: {exc}")
        return None


def _parse_event_to_state(event: Dict[str, Any], match_id: str) -> Optional[TennisState]:
    """
    Convert raw ESPN event dict to TennisState snapshot.
    Returns None if the event_id doesn't match match_id.
    Tolerates missing score fields (defaults to 0-0-0-0-0-0).
    """
    try:
        event_id = event.get("id")
        if event_id != match_id:
            return None

        competitors = event.get("competitors", [])
        if len(competitors) < 2:
            return None

        comp_a = competitors[0]
        comp_b = competitors[1]
        player_a = comp_a.get("athlete", {}).get("displayName", "A")
        player_b = comp_b.get("athlete", {}).get("displayName", "B")

        # Parse score from competitions array
        competitions = event.get("competitions", [])
        if not competitions:
            competitions = [{}]
        comp = competitions[0]

        # Extract score: typically nested in competitor stats
        sets_a, sets_b = 0, 0
        games_a, games_b = 0, 0
        points_a, points_b = 0, 0
        tiebreak = False

        # Try to extract set/game scores from the score structure
        comp_scores = comp.get("competitors", [])
        if len(comp_scores) >= 2:
            try:
                stats_a = comp_scores[0].get("statistics", {})
                stats_b = comp_scores[1].get("statistics", {})
                sets_a = int(stats_a.get("sets", 0))
                sets_b = int(stats_b.get("sets", 0))
                games_a = int(stats_a.get("games", 0))
                games_b = int(stats_b.get("games", 0))
                if games_a == 6 and games_b == 6:
                    tiebreak = True
            except (ValueError, TypeError):
                pass

        tournament = _extract_tournament(event.get("name", ""))
        tour = _infer_tour(event.get("name", ""))
        surface = _infer_surface(tournament)

        return TennisState(
            match_id=match_id,
            player_a=player_a,
            player_b=player_b,
            tournament=tournament,
            tour=tour,
            surface=surface,
            sets_a=sets_a,
            sets_b=sets_b,
            games_a=games_a,
            games_b=games_b,
            points_a=points_a,
            points_b=points_b,
            server=Server.UNKNOWN,  # ESPN rarely provides server info
            tiebreak=tiebreak,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata={"source": "espn"},
        )
    except Exception as exc:
        logger.debug(f"Failed to parse event to state: {exc}")
        return None


def _extract_tournament(name: str) -> str:
    """
    Extract tournament name from ESPN event title.
    Examples:
      "Djokovic, N. at Alcaraz, C." → "Unknown"
      "Wimbledon 2026" → "Wimbledon 2026"
      "US Open 2026 - Men's Singles" → "US Open 2026"
    """
    if not name:
        return "Unknown"
    # Remove player names (pattern: "Lastname, F." or "Lastname, FirstName")
    name = re.sub(r"[A-Z][a-z]+,\s+[A-Z]\.?.*?\s+at\s+", "", name, flags=re.IGNORECASE)
    # Extract year and tournament
    match = re.search(r"([A-Za-z\s]+)\s+(\d{4})", name)
    if match:
        return f"{match.group(1).strip()} {match.group(2)}"
    # Fallback: first few words
    words = name.split(" - ")[0].split()[:3]
    return " ".join(words) if words else "Unknown"


def _infer_tour(name: str) -> Tour:
    """Infer ATP/WTA/CHALLENGER from event name."""
    name_upper = name.upper()
    if "WTA" in name_upper or "WOMEN" in name_upper:
        return Tour.WTA
    if "ATP" in name_upper or "MEN" in name_upper or "CHALLENGER" in name_upper:
        return Tour.ATP
    # Default heuristic: if "Women's" → WTA, else ATP
    if "women" in name.lower():
        return Tour.WTA
    return Tour.ATP


def _infer_surface(tournament: str) -> Surface:
    """Infer surface from tournament name."""
    name_upper = tournament.upper()
    surfaces = {
        "WIMBLEDON": Surface.GRASS,
        "GRASS": Surface.GRASS,
        "CLAY": Surface.CLAY,
        "ROLAND GARROS": Surface.CLAY,
        "FRENCH OPEN": Surface.CLAY,
        "HARD": Surface.HARD,
        "US OPEN": Surface.HARD,
        "AUSTRALIAN": Surface.HARD,
        "INDOOR": Surface.INDOOR,
    }
    for keyword, surface in surfaces.items():
        if keyword in name_upper:
            return surface
    return Surface.UNKNOWN
