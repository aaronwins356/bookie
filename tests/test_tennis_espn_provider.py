from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from src.sports.tennis.espn_provider import (
    EspnProvider,
    _extract_tournament,
    _infer_surface,
    _infer_tour,
    _parse_event_to_match_info,
    _parse_event_to_state,
)
from src.sports.tennis.state import Surface, Tour


# ---------------------------------------------------------------------------
# Mock ESPN responses
# ---------------------------------------------------------------------------

def _mock_response(data: dict) -> MagicMock:
    """Create a mock HTTP response."""
    body = json.dumps(data).encode("utf-8")
    mock = MagicMock()
    mock.__enter__.return_value.read.return_value = body
    return mock


def _mock_event(
    event_id: str = "E123",
    player_a: str = "Djokovic N.",
    player_b: str = "Alcaraz C.",
    name: str = "Wimbledon 2026 - Men's Singles",
    status: str = "in_progress",
    sets_a: int = 0,
    sets_b: int = 0,
    games_a: int = 0,
    games_b: int = 0,
) -> dict:
    """Create a mock ESPN event dict."""
    return {
        "id": event_id,
        "name": name,
        "status": {"type": status},
        "competitors": [
            {
                "athlete": {"displayName": player_a},
                "statistics": {"sets": sets_a, "games": games_a},
            },
            {
                "athlete": {"displayName": player_b},
                "statistics": {"sets": sets_b, "games": games_b},
            },
        ],
        "competitions": [
            {
                "competitors": [
                    {"score": sets_a, "statistics": {"sets": sets_a, "games": games_a}},
                    {"score": sets_b, "statistics": {"sets": sets_b, "games": games_b}},
                ],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Tests: parsing helpers
# ---------------------------------------------------------------------------

class TestInferTour:
    def test_wta_from_women(self):
        assert _infer_tour("Women's Singles") == Tour.WTA

    def test_wta_from_wta_tag(self):
        assert _infer_tour("WTA Tour - Wimbledon") == Tour.WTA

    def test_atp_from_men(self):
        assert _infer_tour("Men's Singles") == Tour.ATP

    def test_atp_from_atp_tag(self):
        assert _infer_tour("ATP Tour - US Open") == Tour.ATP

    def test_challenger(self):
        assert _infer_tour("ATP Challenger") == Tour.ATP

    def test_default_to_atp(self):
        assert _infer_tour("Some Event 2026") == Tour.ATP


class TestInferSurface:
    def test_grass_wimbledon(self):
        assert _infer_surface("Wimbledon 2026") == Surface.GRASS

    def test_grass_direct(self):
        assert _infer_surface("Grass Court Championship") == Surface.GRASS

    def test_clay_roland_garros(self):
        assert _infer_surface("Roland Garros 2026") == Surface.CLAY

    def test_clay_french_open(self):
        assert _infer_surface("French Open 2026") == Surface.CLAY

    def test_hard_us_open(self):
        assert _infer_surface("US Open 2026") == Surface.HARD

    def test_hard_australian(self):
        assert _infer_surface("Australian Open 2026") == Surface.HARD

    def test_indoor(self):
        assert _infer_surface("Indoor Championship") == Surface.INDOOR

    def test_unknown(self):
        assert _infer_surface("Some Tournament") == Surface.UNKNOWN


class TestExtractTournament:
    def test_wimbledon(self):
        name = "Wimbledon 2026"
        assert _extract_tournament(name) == "Wimbledon 2026"

    def test_us_open(self):
        name = "US Open 2026 - Men's Singles"
        assert "US" in _extract_tournament(name) and "2026" in _extract_tournament(name)

    def test_empty_string(self):
        assert _extract_tournament("") == "Unknown"

    def test_removes_player_names(self):
        name = "Djokovic, N. at Alcaraz, C. - Wimbledon 2026"
        tournament = _extract_tournament(name)
        assert "Djokovic" not in tournament
        assert "Alcaraz" not in tournament


class TestParseEventToMatchInfo:
    def test_valid_event(self):
        event = _mock_event()
        info = _parse_event_to_match_info(event)
        assert info is not None
        assert info.player_a == "Djokovic N."
        assert info.player_b == "Alcaraz C."

    def test_missing_event_id(self):
        event = _mock_event()
        event.pop("id")
        assert _parse_event_to_match_info(event) is None

    def test_missing_competitors(self):
        event = _mock_event()
        event["competitors"] = []
        assert _parse_event_to_match_info(event) is None

    def test_missing_athlete_name_defaults_to_unknown(self):
        # Parser defaults to "Unknown" rather than failing
        event = _mock_event()
        event["competitors"][0]["athlete"] = {}
        info = _parse_event_to_match_info(event)
        assert info is not None
        assert info.player_a == "Unknown"

    def test_tour_inference(self):
        event = _mock_event(name="WTA Tour - Roland Garros")
        info = _parse_event_to_match_info(event)
        assert info.tour == Tour.WTA

    def test_surface_inference(self):
        event = _mock_event(name="Wimbledon 2026")
        info = _parse_event_to_match_info(event)
        assert info.surface == Surface.GRASS

    def test_status_inference(self):
        event = _mock_event(status="in_progress")
        info = _parse_event_to_match_info(event)
        assert "live" in info.status.lower()


class TestParseEventToState:
    def test_valid_event(self):
        event = _mock_event(event_id="E123")
        state = _parse_event_to_state(event, "E123")
        assert state is not None
        assert state.match_id == "E123"
        assert state.player_a == "Djokovic N."

    def test_wrong_match_id(self):
        event = _mock_event(event_id="E123")
        assert _parse_event_to_state(event, "E999") is None

    def test_missing_competitors(self):
        event = _mock_event()
        event["competitors"] = []
        assert _parse_event_to_state(event, event["id"]) is None

    def test_score_extraction(self):
        event = _mock_event(event_id="E123", sets_a=1, sets_b=0, games_a=3, games_b=2)
        state = _parse_event_to_state(event, "E123")
        assert state.sets_a == 1
        assert state.games_a == 3

    def test_tiebreak_detection_6_6(self):
        event = _mock_event(event_id="E123", games_a=6, games_b=6)
        state = _parse_event_to_state(event, "E123")
        assert state.tiebreak is True

    def test_no_tiebreak_normal_game(self):
        event = _mock_event(event_id="E123", games_a=3, games_b=2)
        state = _parse_event_to_state(event, "E123")
        assert state.tiebreak is False

    def test_defaults_missing_scores(self):
        # Minimal event with no score data
        event = {
            "id": "E123",
            "competitors": [
                {"athlete": {"displayName": "A"}},
                {"athlete": {"displayName": "B"}},
            ],
            "competitions": [{}],
        }
        state = _parse_event_to_state(event, "E123")
        assert state.sets_a == 0
        assert state.sets_b == 0


# ---------------------------------------------------------------------------
# Tests: EspnProvider
# ---------------------------------------------------------------------------

class TestEspnProviderInit:
    def test_creates_provider(self):
        p = EspnProvider()
        assert p is not None

    def test_custom_timeout(self):
        p = EspnProvider(timeout=20.0)
        assert p._timeout == 20.0

    def test_provider_name(self):
        assert EspnProvider().provider_name() == "EspnProvider"


class TestEspnProviderListLiveMatches:
    @patch("src.sports.tennis.espn_provider.urlopen")
    def test_returns_empty_on_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Network error")
        p = EspnProvider()
        matches = p.list_live_matches()
        assert matches == []

    @patch("src.sports.tennis.espn_provider.urlopen")
    def test_returns_matches(self, mock_urlopen):
        event = _mock_event()
        response_data = {"events": [event]}
        mock_urlopen.return_value = _mock_response(response_data)

        p = EspnProvider()
        matches = p.list_live_matches()
        assert len(matches) >= 1
        assert matches[0].player_a == "Djokovic N."

    @patch("src.sports.tennis.espn_provider.urlopen")
    def test_handles_empty_events(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response({"events": []})
        p = EspnProvider()
        matches = p.list_live_matches()
        assert matches == []

    @patch("src.sports.tennis.espn_provider.urlopen")
    def test_filters_invalid_events(self, mock_urlopen):
        # Mix of valid and invalid events
        events = [
            _mock_event(event_id="E1"),
            {"id": "E2"},  # missing competitors
            _mock_event(event_id="E3"),
        ]
        mock_urlopen.return_value = _mock_response({"events": events})
        p = EspnProvider()
        matches = p.list_live_matches()
        assert len(matches) == 2  # E2 filtered out


class TestEspnProviderGetMatchState:
    @patch("src.sports.tennis.espn_provider.urlopen")
    def test_returns_state_for_valid_match(self, mock_urlopen):
        event = _mock_event(event_id="E123", sets_a=1, sets_b=0)
        mock_urlopen.return_value = _mock_response({"events": [event]})

        p = EspnProvider()
        state = p.get_match_state("E123")
        assert state.match_id == "E123"
        assert state.sets_a == 1

    @patch("src.sports.tennis.espn_provider.urlopen")
    def test_raises_keyerror_for_unknown_match(self, mock_urlopen):
        event = _mock_event(event_id="E123")
        mock_urlopen.return_value = _mock_response({"events": [event]})

        p = EspnProvider()
        with pytest.raises(KeyError):
            p.get_match_state("E999")


class TestEspnProviderStreamMatchStates:
    @patch("src.sports.tennis.espn_provider.urlopen")
    def test_yields_states(self, mock_urlopen):
        event = _mock_event(event_id="E123")
        mock_urlopen.return_value = _mock_response({"events": [event]})

        p = EspnProvider()
        states = []
        for state in p.stream_match_states("E123", poll_interval=0.01):
            states.append(state)
            if len(states) >= 2:
                break

        assert len(states) >= 2

    @patch("src.sports.tennis.espn_provider.urlopen")
    def test_stops_on_repeated_not_found(self, mock_urlopen):
        # After 5 failed lookups, stream should stop
        mock_urlopen.return_value = _mock_response({"events": []})

        p = EspnProvider()
        states = list(p.stream_match_states("E999", poll_interval=0.001))
        assert len(states) == 0  # Never found


class TestEspnProviderCaching:
    @patch("src.sports.tennis.espn_provider.urlopen")
    def test_caches_events(self, mock_urlopen):
        event = _mock_event(event_id="E123")
        mock_urlopen.return_value = _mock_response({"events": [event]})

        p = EspnProvider(timeout=1.0)
        p.list_live_matches()
        p.list_live_matches()

        # Should only have called urlopen once (cached)
        assert mock_urlopen.call_count == 1

    @patch("src.sports.tennis.espn_provider.urlopen")
    def test_cache_expires(self, mock_urlopen):
        event = _mock_event(event_id="E123")
        mock_urlopen.return_value = _mock_response({"events": [event]})

        p = EspnProvider()
        p._cache_ttl = 0.01  # very short TTL
        p.list_live_matches()
        import time
        time.sleep(0.02)
        p.list_live_matches()

        # Should have called urlopen twice (cache expired)
        assert mock_urlopen.call_count == 2
