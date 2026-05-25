from __future__ import annotations

"""
TennisState — canonical snapshot of a live tennis match.

Designed for use with Kalshi match-winner markets and any sports data feed
that provides point-by-point or game-by-game state.

Key differences from generic GameState:
- No clock. Tennis is played to a score, not a time limit.
- Hierarchical score: sets → games → points (with deuce/advantage rules).
- Server matters: serve is a fundamental strategic asymmetry.
- Match format matters: best-of-3 vs best-of-5 changes end-of-match pressure.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class Tour(str, Enum):
    ATP = "ATP"
    WTA = "WTA"
    CHALLENGER = "CHALLENGER"
    ITF = "ITF"
    UNKNOWN = "UNKNOWN"


class Surface(str, Enum):
    HARD = "hard"
    CLAY = "clay"
    GRASS = "grass"
    INDOOR = "indoor"
    UNKNOWN = "unknown"


class Server(str, Enum):
    A = "A"
    B = "B"
    UNKNOWN = "UNKNOWN"


@dataclass
class TennisState:
    """
    Full snapshot of a tennis match at a point in time.

    Points are stored as raw integers (0=love, 1=15, 2=30, 3=40).
    In tiebreaks, points are also raw integers (0, 1, 2, ...).
    The `tiebreak` flag distinguishes which scoring system applies.

    `sets_a` / `sets_b` count completed sets won.
    `games_a` / `games_b` count games won in the *current* set.
    `points_a` / `points_b` count points won in the *current* game.
    """

    match_id: str
    player_a: str
    player_b: str

    # Match context
    tournament: Optional[str] = None
    tour: Tour = Tour.UNKNOWN
    surface: Surface = Surface.UNKNOWN
    best_of: int = 3                    # 3 or 5

    # Score
    current_set: int = 1                # 1-based set number
    sets_a: int = 0
    sets_b: int = 0
    games_a: int = 0                    # games in current set
    games_b: int = 0
    points_a: int = 0                   # points in current game
    points_b: int = 0

    # Serve
    server: Server = Server.UNKNOWN

    # Situation flags
    tiebreak: bool = False
    retired: bool = False               # one player retired (match over)
    suspended: bool = False             # rain / medical / other

    # Observation time
    timestamp: Optional[str] = None

    # Extra provenance from sports feeds
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Derived convenience properties
    # ------------------------------------------------------------------ #

    @property
    def sets_to_win(self) -> int:
        return (self.best_of + 1) // 2

    @property
    def set_lead(self) -> int:
        """Positive = A leads, negative = B leads."""
        return self.sets_a - self.sets_b

    @property
    def game_lead(self) -> int:
        """Positive = A leads in current set."""
        return self.games_a - self.games_b

    @property
    def point_lead(self) -> int:
        """Positive = A leads in current game."""
        return self.points_a - self.points_b

    @property
    def match_over(self) -> bool:
        return (
            self.retired
            or self.sets_a >= self.sets_to_win
            or self.sets_b >= self.sets_to_win
        )

    @property
    def is_final_set(self) -> bool:
        """True if both players have won (best_of-1)//2 sets."""
        sets_needed = (self.best_of + 1) // 2
        return self.sets_a == sets_needed - 1 and self.sets_b == sets_needed - 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "match_id": self.match_id,
            "player_a": self.player_a,
            "player_b": self.player_b,
            "tournament": self.tournament,
            "tour": self.tour.value,
            "surface": self.surface.value,
            "best_of": self.best_of,
            "current_set": self.current_set,
            "sets_a": self.sets_a,
            "sets_b": self.sets_b,
            "games_a": self.games_a,
            "games_b": self.games_b,
            "points_a": self.points_a,
            "points_b": self.points_b,
            "server": self.server.value,
            "tiebreak": self.tiebreak,
            "retired": self.retired,
            "suspended": self.suspended,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TennisState":
        return cls(
            match_id=d.get("match_id", ""),
            player_a=d.get("player_a", ""),
            player_b=d.get("player_b", ""),
            tournament=d.get("tournament"),
            tour=Tour(d.get("tour", "UNKNOWN")),
            surface=Surface(d.get("surface", "unknown")),
            best_of=d.get("best_of", 3),
            current_set=d.get("current_set", 1),
            sets_a=d.get("sets_a", 0),
            sets_b=d.get("sets_b", 0),
            games_a=d.get("games_a", 0),
            games_b=d.get("games_b", 0),
            points_a=d.get("points_a", 0),
            points_b=d.get("points_b", 0),
            server=Server(d.get("server", "UNKNOWN")),
            tiebreak=d.get("tiebreak", False),
            retired=d.get("retired", False),
            suspended=d.get("suspended", False),
            timestamp=d.get("timestamp"),
            metadata=d.get("metadata", {}),
        )
