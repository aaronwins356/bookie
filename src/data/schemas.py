from __future__ import annotations

"""
Canonical data models for the ingestion pipeline.

These are the normalized, validated internal representations that raw
CSV/JSON files are converted into. They are deliberately separate from the
engine runtime models (`src.models.GameState` / `MarketState`): the
canonical models carry richer provenance (timestamps, source, league) and
are the on-disk replay-bundle format. Conversion to engine models happens
at replay time (see `bundle.to_engine_ticks`).

All models are plain dataclasses with explicit `to_dict` / `from_dict` so
serialization is deterministic and stable across Python versions.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Validation / quality enums + records
# ---------------------------------------------------------------------------
class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"

    @property
    def rank(self) -> int:
        return {"INFO": 0, "WARNING": 1, "ERROR": 2, "FATAL": 3}[self.value]


class Verdict(str, Enum):
    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    FAIL = "FAIL"


@dataclass
class ValidationIssue:
    severity: Severity
    code: str
    message: str
    index: Optional[int] = None          # row index in source
    timestamp: Optional[str] = None      # ISO timestamp if relevant
    suggested_fix: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "index": self.index,
            "timestamp": self.timestamp,
            "suggested_fix": self.suggested_fix,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ValidationIssue":
        return cls(
            severity=Severity(d["severity"]),
            code=d["code"],
            message=d["message"],
            index=d.get("index"),
            timestamp=d.get("timestamp"),
            suggested_fix=d.get("suggested_fix"),
        )


# ---------------------------------------------------------------------------
# Canonical models
# ---------------------------------------------------------------------------
@dataclass
class CanonicalGameEvent:
    event_id: str
    sport: str
    league: str
    home_team: str
    away_team: str
    scheduled_start: Optional[str]   # ISO UTC
    status: str                      # raw status string (e.g. "in_progress")
    period: str                      # raw period string (e.g. "2H", "OT")
    clock_seconds_remaining: int
    home_score: int
    away_score: int
    possession: Optional[str]
    timestamp: str                   # ISO UTC — observation time

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CanonicalGameEvent":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__})  # type: ignore[arg-type]


@dataclass
class CanonicalMarketSnapshot:
    market_id: str
    event_id: str
    timestamp: str                   # ISO UTC
    yes_bid: float
    yes_ask: float
    no_bid: float
    no_ask: float
    last_price: Optional[float]
    volume: int
    open_interest: int
    liquidity_score: float
    source: str

    @property
    def mid(self) -> float:
        return (self.yes_bid + self.yes_ask) / 2.0

    @property
    def spread(self) -> float:
        return self.yes_ask - self.yes_bid

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CanonicalMarketSnapshot":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__})  # type: ignore[arg-type]


@dataclass
class CanonicalOrderbookSnapshot:
    market_id: str
    timestamp: str
    yes_bids: List[Tuple[float, int]] = field(default_factory=list)
    yes_asks: List[Tuple[float, int]] = field(default_factory=list)
    no_bids: List[Tuple[float, int]] = field(default_factory=list)
    no_asks: List[Tuple[float, int]] = field(default_factory=list)
    depth_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "market_id": self.market_id,
            "timestamp": self.timestamp,
            "yes_bids": [list(x) for x in self.yes_bids],
            "yes_asks": [list(x) for x in self.yes_asks],
            "no_bids": [list(x) for x in self.no_bids],
            "no_asks": [list(x) for x in self.no_asks],
            "depth_score": self.depth_score,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CanonicalOrderbookSnapshot":
        def pairs(key: str) -> List[Tuple[float, int]]:
            return [(float(p), int(q)) for p, q in d.get(key, [])]
        return cls(
            market_id=d["market_id"],
            timestamp=d["timestamp"],
            yes_bids=pairs("yes_bids"),
            yes_asks=pairs("yes_asks"),
            no_bids=pairs("no_bids"),
            no_asks=pairs("no_asks"),
            depth_score=d.get("depth_score", 0.0),
        )


@dataclass
class CanonicalReplayTick:
    timestamp: str
    game_event: CanonicalGameEvent
    market_snapshot: CanonicalMarketSnapshot
    orderbook_snapshot: Optional[CanonicalOrderbookSnapshot] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "game_event": self.game_event.to_dict(),
            "market_snapshot": self.market_snapshot.to_dict(),
            "orderbook_snapshot": self.orderbook_snapshot.to_dict() if self.orderbook_snapshot else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CanonicalReplayTick":
        ob = d.get("orderbook_snapshot")
        return cls(
            timestamp=d["timestamp"],
            game_event=CanonicalGameEvent.from_dict(d["game_event"]),
            market_snapshot=CanonicalMarketSnapshot.from_dict(d["market_snapshot"]),
            orderbook_snapshot=CanonicalOrderbookSnapshot.from_dict(ob) if ob else None,
            metadata=d.get("metadata", {}),
        )


@dataclass
class DataQualityReport:
    total_game_rows: int = 0
    total_market_rows: int = 0
    total_aligned_ticks: int = 0
    dropped_rows: int = 0
    warning_count: int = 0
    error_count: int = 0
    fatal_count: int = 0
    info_count: int = 0
    time_range_start: Optional[str] = None
    time_range_end: Optional[str] = None
    max_timestamp_gap_seconds: float = 0.0
    stale_market_count: int = 0
    stale_game_count: int = 0
    price_issue_count: int = 0
    liquidity_issue_count: int = 0
    verdict: Verdict = Verdict.PASS
    issues: List[ValidationIssue] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["verdict"] = self.verdict.value
        d["issues"] = [i.to_dict() for i in self.issues]
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DataQualityReport":
        issues = [ValidationIssue.from_dict(i) for i in d.get("issues", [])]
        kwargs = {k: d.get(k) for k in cls.__dataclass_fields__ if k not in ("verdict", "issues")}
        return cls(verdict=Verdict(d.get("verdict", "PASS")), issues=issues, **kwargs)  # type: ignore[arg-type]


@dataclass
class ReplayBundle:
    bundle_id: str
    created_at: str
    sport: str
    league: str
    event_id: str
    ticks: List[CanonicalReplayTick] = field(default_factory=list)
    quality_report: Optional[DataQualityReport] = None
    source_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "created_at": self.created_at,
            "sport": self.sport,
            "league": self.league,
            "event_id": self.event_id,
            "ticks": [t.to_dict() for t in self.ticks],
            "quality_report": self.quality_report.to_dict() if self.quality_report else None,
            "source_metadata": self.source_metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ReplayBundle":
        qr = d.get("quality_report")
        return cls(
            bundle_id=d["bundle_id"],
            created_at=d["created_at"],
            sport=d["sport"],
            league=d["league"],
            event_id=d["event_id"],
            ticks=[CanonicalReplayTick.from_dict(t) for t in d.get("ticks", [])],
            quality_report=DataQualityReport.from_dict(qr) if qr else None,
            source_metadata=d.get("source_metadata", {}),
        )
