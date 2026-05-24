from __future__ import annotations

"""
High-level loaders. Thin convenience wrappers over the generic adapters so
callers can load + normalize games/markets in one call regardless of file
format.
"""

from pathlib import Path
from typing import List, Tuple

from src.data.adapters.generic_sports_adapter import load_games as _load_games
from src.data.adapters.generic_market_adapter import load_markets as _load_markets
from src.data.schemas import CanonicalGameEvent, CanonicalMarketSnapshot


def load_games(path: str | Path) -> List[CanonicalGameEvent]:
    return _load_games(path)


def load_markets(path: str | Path) -> List[CanonicalMarketSnapshot]:
    return _load_markets(path)


def load_pair(
    game_path: str | Path,
    market_path: str | Path,
) -> Tuple[List[CanonicalGameEvent], List[CanonicalMarketSnapshot]]:
    return load_games(game_path), load_markets(market_path)
