from __future__ import annotations

"""
Tennis replay adapter — bridges TennisState to the generic backtest pipeline.

The existing backtest engine operates on (GameState, MarketState) pairs.
This adapter converts a TennisState to a GameState so the pipeline can
replay tennis matches without any engine changes.

Mapping conventions:
- sport          → "tennis"
- home_team      → player_a
- away_team      → player_b
- home_score     → sets_a
- away_score     → sets_b
- phase          → inferred from match state (PRE_GAME / FIRST_HALF / FINAL)
- clock_seconds  → 0 (tennis has no clock)
- metadata       → includes full TennisState as "tennis_state" dict

The MarketState is passed through unchanged when already constructed.
If only TennisState is available, a synthetic MarketState can be built
from a market mid and ticker via make_market_state().
"""

from src.models import GamePhase, GameState, MarketState
from src.sports.tennis.state import TennisState


def tennis_state_to_game_state(state: TennisState) -> GameState:
    """
    Convert a TennisState snapshot to the generic GameState the backtest
    engine understands.

    The full TennisState dict is stored in metadata["tennis_state"] so
    downstream analysis can reconstruct exact match context.
    """
    phase = _infer_phase(state)

    metadata = dict(state.metadata)  # copy caller's metadata
    metadata["tennis_state"] = state.to_dict()
    metadata["sport"] = "tennis"
    metadata["surface"] = state.surface.value
    metadata["tour"] = state.tour.value
    metadata["server"] = state.server.value
    metadata["tiebreak"] = state.tiebreak
    metadata["best_of"] = state.best_of

    return GameState(
        game_id=state.match_id,
        sport="tennis",
        home_team=state.player_a,
        away_team=state.player_b,
        home_score=state.sets_a,
        away_score=state.sets_b,
        phase=phase,
        clock_seconds=0,
        possession=state.server.value if state.server.value != "UNKNOWN" else None,
        down_and_distance=_score_string(state),
        metadata=metadata,
    )


def make_market_state(
    market_id: str,
    match_id: str,
    mid: float,
    spread: float = 2.0,
    volume: int = 0,
    open_interest: int = 0,
    title: str = "",
    is_open: bool = True,
) -> MarketState:
    """
    Build a MarketState for a tennis market when only the mid price is known.

    Half the spread is added/subtracted from mid to approximate bid/ask.
    """
    half = spread / 2.0
    return MarketState(
        market_id=market_id,
        game_id=match_id,
        title=title,
        yes_ask=mid + half,
        yes_bid=mid - half,
        volume=volume,
        open_interest=open_interest,
        is_open=is_open,
    )


def extract_tennis_state(game_state: GameState) -> TennisState | None:
    """
    Reverse the conversion: pull a TennisState back out of a GameState's
    metadata["tennis_state"]. Returns None if the dict is absent or invalid.
    """
    ts_dict = game_state.metadata.get("tennis_state")
    if not ts_dict:
        return None
    try:
        return TennisState.from_dict(ts_dict)
    except Exception:
        return None


# ------------------------------------------------------------------ #
# Private helpers
# ------------------------------------------------------------------ #

def _infer_phase(state: TennisState) -> GamePhase:
    if state.match_over:
        return GamePhase.FINAL
    if state.sets_a == 0 and state.sets_b == 0 and state.games_a == 0 and state.games_b == 0:
        return GamePhase.PRE_GAME
    return GamePhase.FIRST_HALF  # generic "in progress" for tennis


def _score_string(state: TennisState) -> str:
    """Compact score for down_and_distance field."""
    return (
        f"sets={state.sets_a}-{state.sets_b} "
        f"games={state.games_a}-{state.games_b} "
        f"pts={state.points_a}-{state.points_b}"
    )
