from __future__ import annotations

"""
Tennis scoring helpers.

Points in a standard game follow the 0/15/30/40/deuce/advantage system.
This module treats point counts as raw integers (0, 1, 2, 3...) and derives
labels and situational flags from them.

Tiebreak points are also raw integers but follow a simpler win-at-7-with-2-lead
rule. The `tiebreak` flag on TennisState determines which rules apply.

All helpers are pure functions — no state mutation.
"""

from typing import List, Optional, Tuple

from src.sports.tennis.state import Server, TennisState

# ------------------------------------------------------------------ #
# Point label conversion
# ------------------------------------------------------------------ #

_REGULAR_LABELS = {0: "0", 1: "15", 2: "30", 3: "40"}


def point_label(n: int) -> str:
    """Standard display label for a point count (non-deuce context)."""
    return _REGULAR_LABELS.get(n, str(n))


def game_score_display(pts_a: int, pts_b: int, server: str = "UNKNOWN") -> str:
    """
    Human-readable game score like '30-15' or 'Deuce' or 'Adv A'.
    Server is shown first by convention in official scoring.
    """
    if is_deuce(pts_a, pts_b):
        return "Deuce"
    adv = advantage_holder(pts_a, pts_b)
    if adv:
        return f"Adv {adv}"
    if server == "A":
        return f"{point_label(pts_a)}-{point_label(pts_b)}"
    if server == "B":
        return f"{point_label(pts_b)}-{point_label(pts_a)}"
    return f"{point_label(pts_a)}-{point_label(pts_b)}"


# ------------------------------------------------------------------ #
# Deuce / advantage detection
# ------------------------------------------------------------------ #

def is_deuce(pts_a: int, pts_b: int) -> bool:
    """Both players at 40 (or repeated deuce)."""
    return pts_a >= 3 and pts_b >= 3 and pts_a == pts_b


def advantage_holder(pts_a: int, pts_b: int) -> Optional[str]:
    """Returns 'A', 'B', or None if there is no advantage situation."""
    if pts_a >= 3 and pts_b >= 3 and pts_a != pts_b:
        return "A" if pts_a > pts_b else "B"
    return None


# ------------------------------------------------------------------ #
# Game / set / match outcome checks
# ------------------------------------------------------------------ #

def game_winner(pts_a: int, pts_b: int) -> Optional[str]:
    """Returns 'A', 'B', or None if the game is not yet decided."""
    if pts_a >= 4 and pts_a - pts_b >= 2:
        return "A"
    if pts_b >= 4 and pts_b - pts_a >= 2:
        return "B"
    return None


def tiebreak_winner(pts_a: int, pts_b: int) -> Optional[str]:
    """Returns 'A', 'B', or None for tiebreak scoring."""
    if pts_a >= 7 and pts_a - pts_b >= 2:
        return "A"
    if pts_b >= 7 and pts_b - pts_a >= 2:
        return "B"
    return None


def set_winner(games_a: int, games_b: int) -> Optional[str]:
    """
    Returns 'A', 'B', or None.
    Standard set win: 6+ games with 2+ lead, or 7-6 after tiebreak.
    """
    if games_a >= 6 and games_a - games_b >= 2:
        return "A"
    if games_b >= 6 and games_b - games_a >= 2:
        return "B"
    # 7-6 tiebreak conclusion
    if games_a == 7 and games_b == 6:
        return "A"
    if games_b == 7 and games_a == 6:
        return "B"
    return None


def match_winner(sets_a: int, sets_b: int, best_of: int) -> Optional[str]:
    """Returns 'A', 'B', or None."""
    sets_to_win = (best_of + 1) // 2
    if sets_a >= sets_to_win:
        return "A"
    if sets_b >= sets_to_win:
        return "B"
    return None


# ------------------------------------------------------------------ #
# Critical situation flags
# ------------------------------------------------------------------ #

def _can_win_game_next_point(my_pts: int, their_pts: int) -> bool:
    """True if winning the next point wins the current game for the player with my_pts."""
    # 40-xx: at 3, opponent not yet at 3
    if my_pts == 3 and their_pts < 3:
        return True
    # Advantage: both at 3+, I am ahead by 1
    if my_pts > their_pts and my_pts >= 3 and their_pts >= 3:
        return True
    return False


def _can_win_tiebreak_next_point(my_pts: int, their_pts: int) -> bool:
    """True if winning the next tiebreak point wins the tiebreak."""
    # At 6+ with lead of exactly 1 (one more gives 2-lead win)
    if my_pts >= 6 and my_pts - their_pts >= 1:
        return True
    # Already 7+ with 2 lead would already be over; guard for edge cases
    return False


def _would_win_set_by_winning_game(games_me: int, games_them: int) -> bool:
    """True if winning one more game wins the current set."""
    new = games_me + 1
    # Standard 6-x win
    if new >= 6 and new - games_them >= 2:
        return True
    # 7-5
    if new == 7 and games_them == 5:
        return True
    # After tiebreak: the tiebreak game itself (7-6 outcome) is handled
    # by the tiebreak module, not here. But: if games_me==6 and games_them==6
    # winning the tiebreak game gives 7-6.
    if new == 7 and games_them == 6:
        return True
    return False


def _sets_to_win(best_of: int) -> int:
    return (best_of + 1) // 2


def is_break_point(state: TennisState) -> bool:
    """
    True if the returner (non-server) can win the current game by winning the next point.
    False in tiebreaks (no breaks in tiebreaks).
    """
    if state.tiebreak:
        return False
    if state.server == Server.UNKNOWN:
        return False
    if state.server == Server.A:
        # A is serving; break point = B can win game next point
        return _can_win_game_next_point(state.points_b, state.points_a)
    else:
        # B is serving; break point = A can win game next point
        return _can_win_game_next_point(state.points_a, state.points_b)


def break_point_count(state: TennisState) -> int:
    """
    Number of break points the returner holds (1, 2, or 3 at 0-40/15-40/30-40).
    0 if no break point.
    """
    if not is_break_point(state):
        return 0
    if state.server == Server.A:
        sv, rt = state.points_a, state.points_b
    else:
        sv, rt = state.points_b, state.points_a
    # Deuce advantage = 1; 30-40 = 1; 15-40 = 2; 0-40 = 3
    if sv >= 3 and rt >= 3:
        return 1  # advantage
    return 3 - sv  # 0-40: 3, 15-40: 2, 30-40: 1


def is_set_point(state: TennisState) -> bool:
    """
    True if winning the next point would win the current set for either player.
    In tiebreaks: if one player is one tiebreak point from winning.
    """
    if state.tiebreak:
        if _can_win_tiebreak_next_point(state.points_a, state.points_b):
            return True
        if _can_win_tiebreak_next_point(state.points_b, state.points_a):
            return True
        return False

    # Regular game: player wins next point → wins game → wins set?
    if _can_win_game_next_point(state.points_a, state.points_b):
        if _would_win_set_by_winning_game(state.games_a, state.games_b):
            return True
    if _can_win_game_next_point(state.points_b, state.points_a):
        if _would_win_set_by_winning_game(state.games_b, state.games_a):
            return True
    return False


def is_match_point(state: TennisState) -> bool:
    """
    True if winning the next point would win the match for either player.
    A match point is a set point AND winning that set wins the match.
    """
    if not is_set_point(state):
        return False
    stw = _sets_to_win(state.best_of)

    # Would A winning the set win the match?
    if state.sets_a + 1 >= stw:
        if state.tiebreak:
            if _can_win_tiebreak_next_point(state.points_a, state.points_b):
                return True
        elif _can_win_game_next_point(state.points_a, state.points_b):
            if _would_win_set_by_winning_game(state.games_a, state.games_b):
                return True

    # Would B winning the set win the match?
    if state.sets_b + 1 >= stw:
        if state.tiebreak:
            if _can_win_tiebreak_next_point(state.points_b, state.points_a):
                return True
        elif _can_win_game_next_point(state.points_b, state.points_a):
            if _would_win_set_by_winning_game(state.games_b, state.games_a):
                return True

    return False


# ------------------------------------------------------------------ #
# Score string parsing
# ------------------------------------------------------------------ #

def parse_score_string(score: str) -> Tuple[int, int, int, int, int, int]:
    """
    Parse messy score strings like '6-4 3-2 30-15' into
    (sets_a, sets_b, games_a, games_b, points_a, points_b).

    Handles:
    - '6-4 3-2 30-15'  → 1 set done, in 2nd set, in game
    - '6-4 6-3'        → match over (2 sets done)
    - '40-30'          → single game score (no set info)
    - '6-4 7-6'        → tiebreak set
    - '6-4 6-3 2-1'    → third set in progress

    Returns (sets_a, sets_b, games_a, games_b, raw_pts_a, raw_pts_b).
    Game/point values are 0 if not present.
    """
    parts = score.strip().split()
    sets_a = sets_b = 0
    games_a = games_b = 0
    pts_a = pts_b = 0

    _POINT_MAP = {"0": 0, "love": 0, "15": 1, "30": 2, "40": 3, "ad": 4, "a": 4}

    set_scores: List[Tuple[int, int]] = []
    game_score: Optional[Tuple[str, str]] = None

    for part in parts:
        if "-" not in part:
            continue
        left, _, right = part.partition("-")
        left, right = left.strip().lower(), right.strip().lower()

        # Is this a point score? (contains non-digit chars or is "40" type)
        left_is_point = left in _POINT_MAP
        right_is_point = right in _POINT_MAP

        if left_is_point or right_is_point:
            game_score = (left, right)
        else:
            # It's a game/set score
            try:
                l_int, r_int = int(left), int(right)
                if l_int <= 7 and r_int <= 7:
                    set_scores.append((l_int, r_int))
            except ValueError:
                pass

    # Determine completed sets vs current set
    if set_scores:
        # Last score that looks like an in-progress set (not a won set)
        def is_set_complete(g_a: int, g_b: int) -> bool:
            return set_winner(g_a, g_b) is not None

        completed = []
        current: Optional[Tuple[int, int]] = None
        for gs in set_scores:
            if is_set_complete(*gs):
                w = set_winner(*gs)
                if w == "A":
                    sets_a += 1
                else:
                    sets_b += 1
                completed.append(gs)
            else:
                current = gs
        if current is not None:
            games_a, games_b = current
        elif completed:
            # All sets completed, last one is the current games
            last = set_scores[-1]
            games_a, games_b = last  # show as-is

    # Parse point score
    if game_score:
        l_raw, r_raw = game_score
        pts_a = _POINT_MAP.get(l_raw, 0)
        pts_b = _POINT_MAP.get(r_raw, 0)

    return sets_a, sets_b, games_a, games_b, pts_a, pts_b
