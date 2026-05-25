from __future__ import annotations

import pytest

from src.sports.tennis.scoring import (
    advantage_holder,
    break_point_count,
    game_score_display,
    game_winner,
    is_break_point,
    is_deuce,
    is_match_point,
    is_set_point,
    match_winner,
    parse_score_string,
    point_label,
    set_winner,
    tiebreak_winner,
)
from src.sports.tennis.state import Server, TennisState


def _state(**kwargs) -> TennisState:
    defaults = dict(match_id="m1", player_a="A", player_b="B", best_of=3)
    return TennisState(**{**defaults, **kwargs})


# ------------------------------------------------------------------ #
# Point labels
# ------------------------------------------------------------------ #

class TestPointLabel:
    def test_love(self):
        assert point_label(0) == "0"

    def test_15(self):
        assert point_label(1) == "15"

    def test_30(self):
        assert point_label(2) == "30"

    def test_40(self):
        assert point_label(3) == "40"

    def test_unknown(self):
        assert point_label(5) == "5"


# ------------------------------------------------------------------ #
# Deuce / advantage
# ------------------------------------------------------------------ #

class TestDeuce:
    def test_deuce_at_40_40(self):
        assert is_deuce(3, 3) is True

    def test_deuce_repeated(self):
        assert is_deuce(5, 5) is True

    def test_not_deuce_30_40(self):
        assert is_deuce(2, 3) is False

    def test_not_deuce_below_40(self):
        assert is_deuce(2, 2) is False


class TestAdvantageHolder:
    def test_adv_a(self):
        assert advantage_holder(4, 3) == "A"

    def test_adv_b(self):
        assert advantage_holder(3, 4) == "B"

    def test_no_adv_at_deuce(self):
        assert advantage_holder(3, 3) is None

    def test_no_adv_early_game(self):
        assert advantage_holder(1, 2) is None


# ------------------------------------------------------------------ #
# Game winner
# ------------------------------------------------------------------ #

class TestGameWinner:
    def test_a_wins_40_love(self):
        assert game_winner(4, 0) == "A"

    def test_b_wins_adv_b(self):
        assert game_winner(3, 5) == "B"

    def test_no_winner_at_deuce(self):
        assert game_winner(3, 3) is None

    def test_no_winner_mid_game(self):
        assert game_winner(2, 1) is None


# ------------------------------------------------------------------ #
# Tiebreak winner
# ------------------------------------------------------------------ #

class TestTiebreakWinner:
    def test_a_wins_7_5(self):
        assert tiebreak_winner(7, 5) == "A"

    def test_b_wins_8_6(self):
        assert tiebreak_winner(6, 8) == "B"

    def test_no_winner_7_6(self):
        assert tiebreak_winner(7, 6) is None

    def test_no_winner_6_6(self):
        assert tiebreak_winner(6, 6) is None


# ------------------------------------------------------------------ #
# Set winner
# ------------------------------------------------------------------ #

class TestSetWinner:
    def test_a_wins_6_3(self):
        assert set_winner(6, 3) == "A"

    def test_b_wins_6_4(self):
        assert set_winner(4, 6) == "B"

    def test_no_winner_5_5(self):
        assert set_winner(5, 5) is None

    def test_a_wins_7_6_tiebreak(self):
        assert set_winner(7, 6) == "A"

    def test_b_wins_7_5(self):
        assert set_winner(5, 7) == "B"

    def test_no_winner_6_6(self):
        assert set_winner(6, 6) is None


# ------------------------------------------------------------------ #
# Match winner
# ------------------------------------------------------------------ #

class TestMatchWinner:
    def test_a_wins_best_of_3(self):
        assert match_winner(2, 0, 3) == "A"

    def test_b_wins_best_of_5(self):
        assert match_winner(1, 3, 5) == "B"

    def test_no_winner_1_1(self):
        assert match_winner(1, 1, 3) is None


# ------------------------------------------------------------------ #
# Break point detection
# ------------------------------------------------------------------ #

class TestBreakPoint:
    def test_bp_30_40_server_a(self):
        s = _state(server=Server.A, points_a=2, points_b=3)
        assert is_break_point(s) is True

    def test_bp_0_40_server_a(self):
        s = _state(server=Server.A, points_a=0, points_b=3)
        assert is_break_point(s) is True

    def test_bp_adv_b_server_a(self):
        s = _state(server=Server.A, points_a=3, points_b=4)
        assert is_break_point(s) is True

    def test_not_bp_deuce(self):
        s = _state(server=Server.A, points_a=3, points_b=3)
        assert is_break_point(s) is False

    def test_not_bp_40_30_server_a(self):
        s = _state(server=Server.A, points_a=3, points_b=2)
        assert is_break_point(s) is False

    def test_not_bp_in_tiebreak(self):
        s = _state(server=Server.A, points_a=0, points_b=3, tiebreak=True)
        assert is_break_point(s) is False

    def test_not_bp_unknown_server(self):
        s = _state(server=Server.UNKNOWN, points_a=0, points_b=3)
        assert is_break_point(s) is False

    def test_bp_server_b_side(self):
        s = _state(server=Server.B, points_a=3, points_b=0)
        assert is_break_point(s) is True


class TestBreakPointCount:
    def test_0_40_is_3(self):
        s = _state(server=Server.A, points_a=0, points_b=3)
        assert break_point_count(s) == 3

    def test_15_40_is_2(self):
        s = _state(server=Server.A, points_a=1, points_b=3)
        assert break_point_count(s) == 2

    def test_30_40_is_1(self):
        s = _state(server=Server.A, points_a=2, points_b=3)
        assert break_point_count(s) == 1

    def test_adv_b_is_1(self):
        s = _state(server=Server.A, points_a=3, points_b=4)
        assert break_point_count(s) == 1

    def test_no_bp_returns_0(self):
        s = _state(server=Server.A, points_a=3, points_b=2)
        assert break_point_count(s) == 0


# ------------------------------------------------------------------ #
# Set point detection
# ------------------------------------------------------------------ #

class TestSetPoint:
    def test_set_point_5_3_serving_40_30(self):
        # A serving, A leads 5-3 in games, A at 40-30 → A wins game → wins set
        s = _state(server=Server.A, games_a=5, games_b=3, points_a=3, points_b=2)
        assert is_set_point(s) is True

    def test_set_point_tiebreak_one_from_win(self):
        s = _state(server=Server.A, games_a=6, games_b=6, tiebreak=True,
                   points_a=6, points_b=4)
        assert is_set_point(s) is True

    def test_not_set_point_early_game(self):
        s = _state(server=Server.A, games_a=2, games_b=1, points_a=1, points_b=0)
        assert is_set_point(s) is False


# ------------------------------------------------------------------ #
# Match point detection
# ------------------------------------------------------------------ #

class TestMatchPoint:
    def test_match_point_leading_sets(self):
        # A one set from match, serving 5-3, at 40-30
        s = _state(
            best_of=3, sets_a=1, sets_b=0,
            server=Server.A, games_a=5, games_b=3,
            points_a=3, points_b=2,
        )
        assert is_match_point(s) is True

    def test_not_match_point_needs_more_sets(self):
        # A at 0 sets, server, 5-3, 40-30 — winning the set doesn't win match
        s = _state(
            best_of=3, sets_a=0, sets_b=0,
            server=Server.A, games_a=5, games_b=3,
            points_a=3, points_b=2,
        )
        assert is_match_point(s) is False

    def test_match_point_tiebreak(self):
        s = _state(
            best_of=3, sets_a=1, sets_b=0,
            games_a=6, games_b=6, tiebreak=True,
            points_a=6, points_b=4,
        )
        assert is_match_point(s) is True


# ------------------------------------------------------------------ #
# Score string parsing
# ------------------------------------------------------------------ #

class TestParseScoreString:
    def test_full_score(self):
        r = parse_score_string("6-4 3-2 30-15")
        assert r[0] == 1   # sets_a
        assert r[1] == 0   # sets_b
        assert r[2] == 3   # games_a
        assert r[3] == 2   # games_b
        assert r[4] == 2   # pts_a (30→2)
        assert r[5] == 1   # pts_b (15→1)

    def test_match_over(self):
        r = parse_score_string("6-4 6-3")
        assert r[0] == 2   # sets_a
        assert r[1] == 0   # sets_b

    def test_game_score_only(self):
        r = parse_score_string("40-30")
        assert r[4] == 3
        assert r[5] == 2

    def test_love_parsed(self):
        r = parse_score_string("6-4 0-0 love-15")
        assert r[4] == 0
        assert r[5] == 1

    def test_empty_string_returns_zeros(self):
        r = parse_score_string("")
        assert r == (0, 0, 0, 0, 0, 0)


# ------------------------------------------------------------------ #
# game_score_display
# ------------------------------------------------------------------ #

class TestGameScoreDisplay:
    def test_deuce_display(self):
        assert game_score_display(3, 3) == "Deuce"

    def test_advantage_display(self):
        assert game_score_display(4, 3) == "Adv A"

    def test_normal_server_a(self):
        assert game_score_display(2, 1, server="A") == "30-15"

    def test_normal_server_b(self):
        # Server B shows their score first
        assert game_score_display(1, 2, server="B") == "30-15"
