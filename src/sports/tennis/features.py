from __future__ import annotations

"""
Tennis feature extractor.

Produces TennisFeatureSet from a (TennisState, MarketState) pair.
All features are normalized to [-1, 1] or [0, 1] ranges where possible
so strategies can compare them without knowing raw units.
"""

from dataclasses import dataclass
from typing import Optional

from src.models import MarketState
from src.sports.tennis.scoring import (
    advantage_holder,
    break_point_count,
    is_break_point,
    is_deuce,
    is_match_point,
    is_set_point,
)
from src.sports.tennis.state import Server, Surface, TennisState


@dataclass
class TennisFeatureSet:
    """
    Normalized features for tennis strategy evaluation.

    Why this is not a generic FeatureSet:
    - No clock_seconds (tennis has no clock).
    - score_diff is meaningless; set/game/point position each matters differently.
    - Server identity is a first-class strategic factor.
    - Critical pressure situations (break point, set point, match point) need
      their own boolean flags — market overreaction to these is the core edge.
    """

    market_id: str
    match_id: str

    # ---- Score position ------------------------------------------ #
    set_lead: int             # A's sets - B's sets (signed)
    game_lead: int            # A's games - B's games in current set (signed)
    point_lead: int           # A's points - B's points in current game (signed)

    # ---- Pressure flags ------------------------------------------ #
    point_pressure: float     # 0-1: how important is the current point
    server_advantage: float   # +1 = server strongly favored, -1 = returner
    return_pressure: float    # 0-1: pressure on the returner this game
    break_point: bool
    break_points_count: int   # 1, 2, or 3 break points the returner holds
    set_point: bool
    match_point: bool
    tiebreak: bool
    deuce: bool
    advantage_player: Optional[str]  # 'A', 'B', or None

    # ---- Momentum ------------------------------------------------- #
    momentum_proxy: float     # -1 (B momentum) to +1 (A momentum)
    comeback_pressure: float  # 0-1: how much the trailing player needs to respond
    favorite_pressure: float  # 0-1: pressure on the player leading sets
    underdog_pressure: float  # 0-1: urgency for the player trailing sets

    # ---- Market --------------------------------------------------- #
    market_mid: float
    market_spread: float
    liquidity_score: float
    implied_probability: float      # mid / 100 (for player A)
    market_overreaction_score: float  # |implied_prob - fair_prob estimate|

    # ---- Surface -------------------------------------------------- #
    surface_serve_bonus: float  # grass > hard > clay for server advantage


class TennisFeatureExtractor:

    # Surface-specific serve advantage estimates (empirical rough values).
    # Positive = server wins more points on this surface.
    _SURFACE_SERVE_BONUS = {
        Surface.GRASS: 0.12,
        Surface.HARD: 0.06,
        Surface.INDOOR: 0.08,
        Surface.CLAY: 0.03,
        Surface.UNKNOWN: 0.06,
    }

    def extract(self, state: TennisState, market: MarketState) -> TennisFeatureSet:
        bp = is_break_point(state)
        sp = is_set_point(state)
        mp = is_match_point(state)
        bp_count = break_point_count(state)
        deuce = is_deuce(state.points_a, state.points_b)
        adv = advantage_holder(state.points_a, state.points_b)

        point_pressure = self._point_pressure(state, bp, sp, mp)
        server_adv = self._server_advantage(state, bp)
        return_pressure = self._return_pressure(state, bp, bp_count)
        momentum = self._momentum(state)
        comeback = self._comeback_pressure(state)
        fav_pressure = self._favorite_pressure(state)
        underdog_pressure = self._underdog_pressure(state)
        surface_bonus = self._SURFACE_SERVE_BONUS.get(state.surface, 0.06)

        mid = market.mid
        spread = market.spread
        liq = self._liquidity_score(spread, market.volume)
        implied = mid / 100.0

        # Rough fair prob for overreaction score (uses only set/game lead)
        rough_fair = self._rough_fair_prob(state)
        overreaction = min(1.0, abs(implied - rough_fair) / 0.20) if rough_fair is not None else 0.0

        return TennisFeatureSet(
            market_id=market.market_id,
            match_id=state.match_id,
            set_lead=state.set_lead,
            game_lead=state.game_lead,
            point_lead=state.point_lead,
            point_pressure=point_pressure,
            server_advantage=server_adv,
            return_pressure=return_pressure,
            break_point=bp,
            break_points_count=bp_count,
            set_point=sp,
            match_point=mp,
            tiebreak=state.tiebreak,
            deuce=deuce,
            advantage_player=adv,
            momentum_proxy=momentum,
            comeback_pressure=comeback,
            favorite_pressure=fav_pressure,
            underdog_pressure=underdog_pressure,
            market_mid=mid,
            market_spread=spread,
            liquidity_score=liq,
            implied_probability=implied,
            market_overreaction_score=overreaction,
            surface_serve_bonus=surface_bonus,
        )

    def _point_pressure(
        self, state: TennisState, bp: bool, sp: bool, mp: bool
    ) -> float:
        """How important is this point. 0 = routine, 1 = match deciding."""
        if mp:
            return 1.0
        if sp:
            return 0.85
        if bp:
            return 0.70
        if state.tiebreak:
            # Pressure rises as tiebreak progresses
            total = state.points_a + state.points_b
            return min(0.9, 0.4 + total * 0.04)
        if is_deuce(state.points_a, state.points_b):
            return 0.55
        # Routine point
        return 0.10 + 0.05 * (state.points_a + state.points_b)

    def _server_advantage(self, state: TennisState, bp: bool) -> float:
        """
        +1.0 = strong server advantage. -1.0 = returner dominates.
        At break point, shifts strongly negative for the server.
        """
        if state.server == Server.UNKNOWN:
            return 0.0
        base = 0.30  # typical server advantage on neutral surface
        surface_bonus = self._SURFACE_SERVE_BONUS.get(state.surface, 0.06)
        adv = base + surface_bonus
        if bp:
            adv -= 0.50  # break point heavily favors returner situationally
        if state.tiebreak:
            adv *= 0.5   # serve advantage diminished in tiebreak
        return max(-1.0, min(1.0, adv))

    def _return_pressure(self, state: TennisState, bp: bool, bp_count: int) -> float:
        """0-1: how much pressure the returner has on this game."""
        if bp:
            return min(1.0, 0.6 + bp_count * 0.13)
        if is_deuce(state.points_a, state.points_b):
            return 0.5
        if state.server == Server.A:
            # B is returning; how close is B to a break?
            return min(0.5, state.points_b * 0.12)
        elif state.server == Server.B:
            return min(0.5, state.points_a * 0.12)
        return 0.0

    def _momentum(self, state: TennisState) -> float:
        """
        -1 (B momentum) to +1 (A momentum).
        Simple proxy: set lead weighted more than game lead.
        """
        return max(-1.0, min(1.0, state.set_lead * 0.5 + state.game_lead * 0.1))

    def _comeback_pressure(self, state: TennisState) -> float:
        """0-1: urgency for the trailing player."""
        stw = state.sets_to_win
        a_needs = stw - state.sets_a
        b_needs = stw - state.sets_b
        if a_needs < b_needs:
            # A is ahead; B needs more sets
            deficit = b_needs - a_needs
            return min(1.0, deficit * 0.4 + state.game_lead * 0.05)
        elif b_needs < a_needs:
            deficit = a_needs - b_needs
            return min(1.0, deficit * 0.4 - state.game_lead * 0.05)
        return 0.1

    def _favorite_pressure(self, state: TennisState) -> float:
        """Pressure on the set leader to close out."""
        leader_sets = max(state.sets_a, state.sets_b)
        stw = state.sets_to_win
        if leader_sets == stw - 1:
            # One set from winning — high pressure to close
            return 0.7 + (max(state.games_a, state.games_b) / 12.0) * 0.2
        if leader_sets > 0:
            return 0.3
        return 0.0

    def _underdog_pressure(self, state: TennisState) -> float:
        """Urgency for the set-trailing player."""
        trailing = min(state.sets_a, state.sets_b)
        leading = max(state.sets_a, state.sets_b)
        if leading > trailing:
            deficit = leading - trailing
            return min(1.0, deficit * 0.35)
        return 0.0

    def _liquidity_score(self, spread: float, volume: int) -> float:
        spread_score = max(0.0, 1.0 - spread / 20.0)
        vol_score = min(1.0, volume / 500.0)
        return round((spread_score + vol_score) / 2.0, 3)

    def _rough_fair_prob(self, state: TennisState) -> Optional[float]:
        """
        Very rough fair-probability estimate for computing overreaction score.
        Uses only sets/games; fine detail handled in fair_value.py.
        """
        stw = state.sets_to_win
        sets_a, sets_b = state.sets_a, state.sets_b
        # Base from sets
        if sets_a == stw - 1 and sets_b == stw - 1:
            base = 0.5 + state.game_lead * 0.04
        elif sets_a > sets_b:
            base = 0.55 + (sets_a - sets_b) * 0.15
        elif sets_b > sets_a:
            base = 0.45 - (sets_b - sets_a) * 0.15
        else:
            base = 0.5 + state.game_lead * 0.03
        return max(0.02, min(0.98, base))
