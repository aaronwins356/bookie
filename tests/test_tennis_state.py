from __future__ import annotations

import pytest

from src.sports.tennis.state import Server, Surface, TennisState, Tour


def _state(**kwargs) -> TennisState:
    defaults = dict(match_id="m1", player_a="Djokovic", player_b="Nadal")
    return TennisState(**{**defaults, **kwargs})


class TestTennisStateDefaults:
    def test_default_best_of(self):
        s = _state()
        assert s.best_of == 3

    def test_default_surface(self):
        assert _state().surface == Surface.UNKNOWN

    def test_default_server(self):
        assert _state().server == Server.UNKNOWN

    def test_default_scores_zero(self):
        s = _state()
        assert s.sets_a == s.sets_b == s.games_a == s.games_b == s.points_a == s.points_b == 0

    def test_default_tour(self):
        assert _state().tour == Tour.UNKNOWN


class TestDerivedProperties:
    def test_sets_to_win_best_of_3(self):
        assert _state(best_of=3).sets_to_win == 2

    def test_sets_to_win_best_of_5(self):
        assert _state(best_of=5).sets_to_win == 3

    def test_set_lead_positive(self):
        assert _state(sets_a=1, sets_b=0).set_lead == 1

    def test_set_lead_negative(self):
        assert _state(sets_a=0, sets_b=2).set_lead == -2

    def test_set_lead_zero(self):
        assert _state(sets_a=1, sets_b=1).set_lead == 0

    def test_game_lead(self):
        assert _state(games_a=4, games_b=2).game_lead == 2

    def test_point_lead(self):
        assert _state(points_a=1, points_b=3).point_lead == -2

    def test_match_over_by_sets(self):
        s = _state(best_of=3, sets_a=2, sets_b=0)
        assert s.match_over is True

    def test_match_not_over(self):
        s = _state(best_of=3, sets_a=1, sets_b=0)
        assert s.match_over is False

    def test_match_over_by_retirement(self):
        s = _state(retired=True)
        assert s.match_over is True

    def test_is_final_set_best_of_3(self):
        s = _state(best_of=3, sets_a=1, sets_b=1)
        assert s.is_final_set is True

    def test_not_final_set(self):
        s = _state(best_of=3, sets_a=1, sets_b=0)
        assert s.is_final_set is False

    def test_is_final_set_best_of_5(self):
        s = _state(best_of=5, sets_a=2, sets_b=2)
        assert s.is_final_set is True


class TestSerialisation:
    def test_round_trip(self):
        s = _state(
            best_of=5,
            surface=Surface.GRASS,
            tour=Tour.ATP,
            server=Server.A,
            sets_a=2, sets_b=1,
            games_a=5, games_b=3,
            points_a=2, points_b=1,
            tiebreak=False,
            tournament="Wimbledon",
            timestamp="2026-07-05T14:00:00Z",
            metadata={"source": "test"},
        )
        d = s.to_dict()
        s2 = TennisState.from_dict(d)
        assert s2.match_id == s.match_id
        assert s2.surface == Surface.GRASS
        assert s2.tour == Tour.ATP
        assert s2.server == Server.A
        assert s2.sets_a == 2
        assert s2.games_b == 3
        assert s2.tournament == "Wimbledon"
        assert s2.metadata["source"] == "test"

    def test_to_dict_contains_expected_keys(self):
        d = _state().to_dict()
        for key in ("match_id", "player_a", "player_b", "sets_a", "sets_b",
                    "games_a", "games_b", "points_a", "points_b",
                    "server", "tiebreak", "surface", "tour"):
            assert key in d

    def test_from_dict_missing_optional_fields(self):
        d = {"match_id": "m2", "player_a": "Sinner", "player_b": "Alcaraz"}
        s = TennisState.from_dict(d)
        assert s.match_id == "m2"
        assert s.best_of == 3
        assert s.server == Server.UNKNOWN
