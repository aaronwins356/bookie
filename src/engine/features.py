from __future__ import annotations

from dataclasses import dataclass
from src.models import GameState, MarketState, GamePhase


@dataclass
class FeatureSet:
    """Derived numeric features used by strategies and fair-value models."""

    market_id: str
    game_id: str

    # game features
    score_diff: int
    total_score: int
    clock_seconds: int
    phase: str
    time_pressure: float     # 0 = lots of time left, 1 = very late

    # market features
    mid_price: float
    spread: float
    volume: int
    spread_pct: float        # spread / mid

    # composite
    implied_prob: float      # mid / 100


class FeatureExtractor:
    """Computes a FeatureSet from raw game + market state."""

    def extract(self, game: GameState, market: MarketState) -> FeatureSet:
        clock_max = self._max_clock(game.phase)
        time_pressure = 1.0 - (game.clock_seconds / clock_max) if clock_max > 0 else 1.0

        spread_pct = market.spread / market.mid if market.mid > 0 else 0.0

        return FeatureSet(
            market_id=market.market_id,
            game_id=game.game_id,
            score_diff=game.score_diff,
            total_score=game.total_score,
            clock_seconds=game.clock_seconds,
            phase=game.phase.value,
            time_pressure=max(0.0, min(1.0, time_pressure)),
            mid_price=market.mid,
            spread=market.spread,
            volume=market.volume,
            spread_pct=spread_pct,
            implied_prob=market.mid / 100.0,
        )

    def _max_clock(self, phase: GamePhase) -> int:
        mapping = {
            GamePhase.FIRST_HALF: 1800,
            GamePhase.SECOND_HALF: 1800,
            GamePhase.OVERTIME: 600,
            GamePhase.HALFTIME: 900,
        }
        return mapping.get(phase, 3600)
