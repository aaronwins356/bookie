from __future__ import annotations

import pytest

from src.models import GamePhase, MarketState
from src.sports.tennis.replay_adapter import (
    extract_tennis_state,
    make_market_state,
    tennis_state_to_game_state,
)
from src.sports.tennis.state import Server, Surface, TennisState, Tour


def _state(**kwargs) -> TennisState:
    defaults = dict(match_id="m1", player_a="Sinner", player_b="Alcaraz", best_of=3)
    return TennisState(**{**defaults, **kwargs})


class TestTennisStateToGameState:
    def test_sport_is_tennis(self):
        gs = tennis_state_to_game_state(_state())
        assert gs.sport == "tennis"

    def test_game_id_is_match_id(self):
        gs = tennis_state_to_game_state(_state(match_id="m99"))
        assert gs.game_id == "m99"

    def test_home_team_is_player_a(self):
        gs = tennis_state_to_game_state(_state())
        assert gs.home_team == "Sinner"

    def test_away_team_is_player_b(self):
        gs = tennis_state_to_game_state(_state())
        assert gs.away_team == "Alcaraz"

    def test_home_score_is_sets_a(self):
        gs = tennis_state_to_game_state(_state(sets_a=2, sets_b=1))
        assert gs.home_score == 2

    def test_away_score_is_sets_b(self):
        gs = tennis_state_to_game_state(_state(sets_a=2, sets_b=1))
        assert gs.away_score == 1

    def test_clock_is_zero(self):
        gs = tennis_state_to_game_state(_state())
        assert gs.clock_seconds == 0

    def test_phase_pre_game_when_no_score(self):
        gs = tennis_state_to_game_state(_state())
        assert gs.phase == GamePhase.PRE_GAME

    def test_phase_final_when_match_over(self):
        gs = tennis_state_to_game_state(_state(sets_a=2, sets_b=0))
        assert gs.phase == GamePhase.FINAL

    def test_phase_in_progress(self):
        gs = tennis_state_to_game_state(_state(sets_a=1, sets_b=0, games_a=3))
        assert gs.phase == GamePhase.FIRST_HALF

    def test_metadata_contains_tennis_state(self):
        gs = tennis_state_to_game_state(_state())
        assert "tennis_state" in gs.metadata

    def test_metadata_surface(self):
        gs = tennis_state_to_game_state(_state(surface=Surface.CLAY))
        assert gs.metadata["surface"] == "clay"

    def test_metadata_tour(self):
        gs = tennis_state_to_game_state(_state(tour=Tour.ATP))
        assert gs.metadata["tour"] == "ATP"

    def test_metadata_server(self):
        gs = tennis_state_to_game_state(_state(server=Server.A))
        assert gs.metadata["server"] == "A"

    def test_score_string_in_down_and_distance(self):
        gs = tennis_state_to_game_state(_state(sets_a=1, games_a=3, points_a=2))
        assert "sets=1-0" in gs.down_and_distance
        assert "games=3-0" in gs.down_and_distance

    def test_possession_is_server(self):
        gs = tennis_state_to_game_state(_state(server=Server.B))
        assert gs.possession == "B"

    def test_possession_none_when_unknown_server(self):
        gs = tennis_state_to_game_state(_state(server=Server.UNKNOWN))
        assert gs.possession is None

    def test_caller_metadata_preserved(self):
        s = _state(metadata={"feed": "sportradar"})
        gs = tennis_state_to_game_state(s)
        assert gs.metadata["feed"] == "sportradar"


class TestExtractTennisState:
    def test_round_trip(self):
        original = _state(
            surface=Surface.GRASS, tour=Tour.WTA, server=Server.B,
            sets_a=1, sets_b=2, games_a=4, games_b=3, points_a=2, points_b=1,
        )
        gs = tennis_state_to_game_state(original)
        recovered = extract_tennis_state(gs)
        assert recovered is not None
        assert recovered.match_id == original.match_id
        assert recovered.surface == Surface.GRASS
        assert recovered.tour == Tour.WTA
        assert recovered.sets_a == 1

    def test_returns_none_when_no_tennis_state(self):
        from src.models import GameState
        gs = GameState(
            game_id="g1", sport="basketball",
            home_team="Lakers", away_team="Celtics",
            home_score=100, away_score=95,
            phase=GamePhase.FINAL, clock_seconds=0,
        )
        assert extract_tennis_state(gs) is None


class TestMakeMarketState:
    def test_mid_is_correct(self):
        ms = make_market_state("MKT-001", "m1", mid=60.0, spread=2.0)
        assert ms.mid == pytest.approx(60.0)

    def test_spread_is_correct(self):
        ms = make_market_state("MKT-001", "m1", mid=60.0, spread=4.0)
        assert ms.spread == pytest.approx(4.0)

    def test_market_id_passes_through(self):
        ms = make_market_state("MKT-XYZ", "m1", mid=50.0)
        assert ms.market_id == "MKT-XYZ"

    def test_game_id_is_match_id(self):
        ms = make_market_state("MKT-001", "m99", mid=50.0)
        assert ms.game_id == "m99"

    def test_is_open_default(self):
        ms = make_market_state("MKT-001", "m1", mid=50.0)
        assert ms.is_open is True
