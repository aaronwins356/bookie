"""
Data ingestion + canonical replay-schema pipeline (Phase 3).

Flow: raw CSV/JSON  ->  normalize  ->  validate  ->  align  ->  quality
report  ->  ReplayBundle  ->  (replay simulator).

Local files only — no live APIs, no secrets. The pipeline's job is to make
bad data obvious and prevent it from silently creating fake edge.
"""

from src.data.schemas import (
    Severity, Verdict, ValidationIssue,
    CanonicalGameEvent, CanonicalMarketSnapshot, CanonicalOrderbookSnapshot,
    CanonicalReplayTick, ReplayBundle, DataQualityReport,
)
from src.data.bundle import build_bundle, save_bundle, load_bundle, to_engine_ticks

__all__ = [
    "Severity", "Verdict", "ValidationIssue",
    "CanonicalGameEvent", "CanonicalMarketSnapshot", "CanonicalOrderbookSnapshot",
    "CanonicalReplayTick", "ReplayBundle", "DataQualityReport",
    "build_bundle", "save_bundle", "load_bundle", "to_engine_ticks",
]
