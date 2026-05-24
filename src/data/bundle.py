from __future__ import annotations

"""
Replay bundle assembly and conversion.

- `build_bundle`     : normalize → validate → align → quality report → bundle
- `save_bundle`/`load_bundle` : dispatch JSON vs JSONL by extension
- `to_engine_ticks`  : convert canonical ticks into engine runtime models
                       (GameState / MarketState) for the replay simulator

Determinism: `created_at` defaults to the latest tick timestamp (data-
derived, not wall-clock) and `bundle_id` is a content hash, so building the
same inputs twice yields an identical bundle.
"""

import hashlib
from pathlib import Path
from typing import List, Optional, Tuple

from src.data.schemas import (
    CanonicalGameEvent, CanonicalMarketSnapshot, CanonicalReplayTick,
    ReplayBundle, DataQualityReport,
)
from src.data.validators import validate_all
from src.data.aligner import align, DEFAULT_MAX_LAG_SECONDS
from src.data.quality import build_quality_report
from src.data import exporters
from src.models import GameState, MarketState, GamePhase


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
def build_bundle(
    events: List[CanonicalGameEvent],
    snaps: List[CanonicalMarketSnapshot],
    max_lag_seconds: float = DEFAULT_MAX_LAG_SECONDS,
    source_metadata: Optional[dict] = None,
    created_at: Optional[str] = None,
) -> ReplayBundle:
    issues = validate_all(events, snaps)
    alignment = align(events, snaps, max_lag_seconds=max_lag_seconds)
    report = build_quality_report(events, snaps, issues, alignment)

    ticks = alignment.ticks
    sport = events[0].sport if events else (snaps[0].source if snaps else "UNKNOWN")
    league = events[0].league if events else "UNKNOWN"
    event_id = events[0].event_id if events else (snaps[0].event_id if snaps else "")

    created = created_at or (ticks[-1].timestamp if ticks else "1970-01-01T00:00:00+00:00")
    bundle_id = _bundle_id(sport, event_id, ticks, created)

    return ReplayBundle(
        bundle_id=bundle_id,
        created_at=created,
        sport=sport,
        league=league,
        event_id=event_id,
        ticks=ticks,
        quality_report=report,
        source_metadata=source_metadata or {},
    )


def _bundle_id(sport: str, event_id: str, ticks: List[CanonicalReplayTick], created: str) -> str:
    h = hashlib.sha256()
    h.update(sport.encode())
    h.update(event_id.encode())
    h.update(created.encode())
    h.update(str(len(ticks)).encode())
    for t in ticks:
        h.update(t.timestamp.encode())
    return f"{sport}-{event_id}-{h.hexdigest()[:10]}"


# ---------------------------------------------------------------------------
# save / load
# ---------------------------------------------------------------------------
def save_bundle(bundle: ReplayBundle, path: str | Path) -> None:
    p = Path(path)
    if p.suffix.lower() == ".jsonl":
        exporters.write_jsonl(bundle, p)
    else:
        exporters.write_json(bundle, p)


def load_bundle(path: str | Path) -> ReplayBundle:
    p = Path(path)
    if p.suffix.lower() == ".jsonl":
        return exporters.read_jsonl(p)
    return exporters.read_json(p)


# ---------------------------------------------------------------------------
# conversion to engine runtime models
# ---------------------------------------------------------------------------
_PERIOD_MAP = {
    "pre": GamePhase.PRE_GAME, "pregame": GamePhase.PRE_GAME, "scheduled": GamePhase.PRE_GAME,
    "1h": GamePhase.FIRST_HALF, "q1": GamePhase.FIRST_HALF, "q2": GamePhase.FIRST_HALF,
    "first_half": GamePhase.FIRST_HALF, "1": GamePhase.FIRST_HALF,
    "ht": GamePhase.HALFTIME, "half": GamePhase.HALFTIME, "halftime": GamePhase.HALFTIME,
    "2h": GamePhase.SECOND_HALF, "q3": GamePhase.SECOND_HALF, "q4": GamePhase.SECOND_HALF,
    "second_half": GamePhase.SECOND_HALF, "2": GamePhase.SECOND_HALF,
    "ot": GamePhase.OVERTIME, "overtime": GamePhase.OVERTIME,
    "ft": GamePhase.FINAL, "final": GamePhase.FINAL, "ended": GamePhase.FINAL,
}


def _phase(period: str, status: str) -> GamePhase:
    s = (status or "").strip().lower()
    if s in ("final", "ended", "complete", "completed"):
        return GamePhase.FINAL
    if s in ("scheduled", "pre", "pregame", "not_started"):
        return GamePhase.PRE_GAME
    return _PERIOD_MAP.get((period or "").strip().lower(), GamePhase.SECOND_HALF)


def tick_to_engine(tick: CanonicalReplayTick) -> Tuple[GameState, MarketState]:
    ge = tick.game_event
    ms = tick.market_snapshot

    game = GameState(
        game_id=ge.event_id,
        sport=ge.sport,
        home_team=ge.home_team,
        away_team=ge.away_team,
        home_score=ge.home_score,
        away_score=ge.away_score,
        phase=_phase(ge.period, ge.status),
        clock_seconds=ge.clock_seconds_remaining,
        possession=ge.possession,
        metadata={"source": "bundle", **tick.metadata},
    )
    market = MarketState(
        market_id=ms.market_id,
        game_id=ms.event_id,
        title=f"{ge.home_team} vs {ge.away_team}",
        yes_ask=ms.yes_ask,
        yes_bid=ms.yes_bid,
        volume=ms.volume,
        open_interest=ms.open_interest,
        metadata={"source": ms.source, "liquidity_score": ms.liquidity_score},
    )
    return game, market


def to_engine_ticks(bundle: ReplayBundle) -> List[Tuple[GameState, List[MarketState]]]:
    out: List[Tuple[GameState, List[MarketState]]] = []
    for tick in bundle.ticks:
        game, market = tick_to_engine(tick)
        out.append((game, [market]))
    return out
