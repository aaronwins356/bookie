from __future__ import annotations

import pytest

from src.sports.tennis.mock_provider import MockProvider, _advance_one_point
from src.sports.tennis.provider_base import TennisMatchInfo, TennisScoreProvider
from src.sports.tennis.state import Server, Surface, TennisState, Tour


class TestTennisScoreProviderInterface:
    def test_mock_is_subclass(self):
        assert issubclass(MockProvider, TennisScoreProvider)

    def test_provider_name(self):
        assert MockProvider().provider_name() == "MockProvider"


class TestListLiveMatches:
    def test_returns_list(self):
        p = MockProvider()
        matches = p.list_live_matches()
        assert isinstance(matches, list)

    def test_returns_three_by_default(self):
        p = MockProvider()
        assert len(p.list_live_matches()) == 3

    def test_all_are_match_info(self):
        p = MockProvider()
        for m in p.list_live_matches():
            assert isinstance(m, TennisMatchInfo)

    def test_match_ids_unique(self):
        p = MockProvider()
        ids = [m.match_id for m in p.list_live_matches()]
        assert len(ids) == len(set(ids))

    def test_all_have_player_names(self):
        p = MockProvider()
        for m in p.list_live_matches():
            assert m.player_a and m.player_b

    def test_all_have_tournament(self):
        p = MockProvider()
        for m in p.list_live_matches():
            assert m.tournament

    def test_custom_matches(self):
        custom = [TennisMatchInfo(
            match_id="X1", player_a="A", player_b="B",
            tournament="Test Open", tour=Tour.ATP,
        )]
        p = MockProvider(matches=custom)
        assert len(p.list_live_matches()) == 1
        assert p.list_live_matches()[0].match_id == "X1"


class TestGetMatchState:
    def test_returns_tennis_state(self):
        p = MockProvider()
        state = p.get_match_state("MOCK-001")
        assert isinstance(state, TennisState)

    def test_match_id_preserved(self):
        p = MockProvider()
        assert p.get_match_state("MOCK-001").match_id == "MOCK-001"

    def test_unknown_match_raises(self):
        p = MockProvider()
        with pytest.raises(KeyError):
            p.get_match_state("NONEXISTENT")

    def test_state_advances_on_repeated_calls(self):
        p = MockProvider()
        s1 = p.get_match_state("MOCK-001")
        s2 = p.get_match_state("MOCK-001")
        # Second call should advance by one point
        assert s2.points_a >= s1.points_a

    def test_returns_copy_not_reference(self):
        p = MockProvider()
        s1 = p.get_match_state("MOCK-001")
        s1.points_a = 99
        s2 = p.get_match_state("MOCK-001")
        assert s2.points_a != 99

    def test_all_three_matches_accessible(self):
        p = MockProvider()
        for mid in ["MOCK-001", "MOCK-002", "MOCK-003"]:
            state = p.get_match_state(mid)
            assert state.match_id == mid

    def test_mock_001_is_break_point(self):
        p = MockProvider()
        state = p.get_match_state("MOCK-001")
        # MOCK-001: A serving, 0-40 → break point
        assert state.server == Server.A
        assert state.points_b == 3
        assert state.points_a == 0

    def test_mock_003_is_tiebreak(self):
        p = MockProvider()
        state = p.get_match_state("MOCK-003")
        assert state.tiebreak is True


class TestStreamMatchStates:
    def test_yields_states(self):
        p = MockProvider(stream_ticks=3)
        states = list(p.stream_match_states("MOCK-001"))
        assert len(states) == 3

    def test_yields_tennis_states(self):
        p = MockProvider(stream_ticks=2)
        for state in p.stream_match_states("MOCK-001"):
            assert isinstance(state, TennisState)

    def test_states_advance(self):
        p = MockProvider(stream_ticks=3)
        states = list(p.stream_match_states("MOCK-001"))
        # Points should increase across ticks
        pts = [s.points_a for s in states]
        assert pts == sorted(pts)

    def test_custom_tick_count(self):
        p = MockProvider(stream_ticks=7)
        count = sum(1 for _ in p.stream_match_states("MOCK-003"))
        assert count == 7


class TestAdvanceOnePoint:
    def test_points_a_increases(self):
        p = MockProvider()
        s = p.get_match_state("MOCK-001")
        s2 = _advance_one_point(s)
        assert s2.points_a == s.points_a + 1

    def test_capped_at_7(self):
        p = MockProvider()
        s = p.get_match_state("MOCK-001")
        from src.sports.tennis.mock_provider import _advance_one_point
        import copy
        s_copy = TennisState.from_dict(s.to_dict())
        s_copy.points_a = 7
        s2 = _advance_one_point(s_copy)
        assert s2.points_a <= 7

    def test_does_not_mutate_input(self):
        p = MockProvider()
        s = p.get_match_state("MOCK-001")
        original_pts = s.points_a
        _advance_one_point(s)
        assert s.points_a == original_pts


class TestMatchInfoDisplayName:
    def test_display_name_format(self):
        m = TennisMatchInfo(
            match_id="X1", player_a="Djokovic", player_b="Alcaraz",
            tournament="Wimbledon", tour=Tour.ATP,
        )
        assert "Djokovic" in m.display_name
        assert "Alcaraz" in m.display_name
        assert "Wimbledon" in m.display_name
