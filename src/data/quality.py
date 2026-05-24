from __future__ import annotations

"""
Data quality reporting. Aggregates validation issues + alignment stats into
a single DataQualityReport with a PASS / PASS_WITH_WARNINGS / FAIL verdict.

Verdict rules:
- any FATAL or ERROR  -> FAIL
- any WARNING (no errors) -> PASS_WITH_WARNINGS
- otherwise -> PASS
"""

from typing import List, Optional

from src.data.schemas import (
    CanonicalGameEvent, CanonicalMarketSnapshot, DataQualityReport,
    Severity, ValidationIssue, Verdict,
)
from src.data.aligner import AlignmentResult
from src.data.timestamp import parse_timestamp, AmbiguousTimestampError

_PRICE_CODES = {
    "MARKET_NEGATIVE_PRICE", "MARKET_PRICE_OUT_OF_RANGE",
    "MARKET_YES_CROSSED", "MARKET_NO_CROSSED", "MARKET_YESNO_INCONSISTENT",
}
_LIQUIDITY_CODES = {"MARKET_NEGATIVE_LIQUIDITY", "MARKET_NO_LIQUIDITY"}


def _verdict(issues: List[ValidationIssue]) -> Verdict:
    has_blocking = any(i.severity in (Severity.ERROR, Severity.FATAL) for i in issues)
    has_warning = any(i.severity == Severity.WARNING for i in issues)
    if has_blocking:
        return Verdict.FAIL
    if has_warning:
        return Verdict.PASS_WITH_WARNINGS
    return Verdict.PASS


def _time_range(events: List[CanonicalGameEvent], snaps: List[CanonicalMarketSnapshot]):
    stamps = []
    for item in list(events) + list(snaps):
        try:
            stamps.append(parse_timestamp(item.timestamp))
        except (AmbiguousTimestampError, ValueError):
            continue
    if not stamps:
        return None, None, 0.0
    stamps.sort()
    max_gap = 0.0
    for a, b in zip(stamps, stamps[1:]):
        max_gap = max(max_gap, (b - a).total_seconds())
    return stamps[0].isoformat(), stamps[-1].isoformat(), max_gap


def build_quality_report(
    events: List[CanonicalGameEvent],
    snaps: List[CanonicalMarketSnapshot],
    issues: List[ValidationIssue],
    alignment: Optional[AlignmentResult] = None,
) -> DataQualityReport:
    start, end, max_gap = _time_range(events, snaps)

    report = DataQualityReport(
        total_game_rows=len(events),
        total_market_rows=len(snaps),
        total_aligned_ticks=len(alignment.ticks) if alignment else 0,
        dropped_rows=alignment.dropped if alignment else 0,
        info_count=sum(1 for i in issues if i.severity == Severity.INFO),
        warning_count=sum(1 for i in issues if i.severity == Severity.WARNING),
        error_count=sum(1 for i in issues if i.severity == Severity.ERROR),
        fatal_count=sum(1 for i in issues if i.severity == Severity.FATAL),
        time_range_start=start,
        time_range_end=end,
        max_timestamp_gap_seconds=round(max_gap, 3),
        stale_market_count=alignment.stale_market if alignment else 0,
        stale_game_count=alignment.stale_game if alignment else 0,
        price_issue_count=sum(1 for i in issues if i.code in _PRICE_CODES),
        liquidity_issue_count=sum(1 for i in issues if i.code in _LIQUIDITY_CODES),
        verdict=_verdict(issues),
        issues=list(issues),
    )
    return report


def format_report(report: DataQualityReport) -> str:
    """Human-readable multi-line summary for the CLI."""
    lines = [
        f"verdict              : {report.verdict.value}",
        f"game rows            : {report.total_game_rows}",
        f"market rows          : {report.total_market_rows}",
        f"aligned ticks        : {report.total_aligned_ticks}",
        f"dropped rows         : {report.dropped_rows}",
        f"time range           : {report.time_range_start} .. {report.time_range_end}",
        f"max timestamp gap    : {report.max_timestamp_gap_seconds}s",
        f"stale market / game  : {report.stale_market_count} / {report.stale_game_count}",
        f"price issues         : {report.price_issue_count}",
        f"liquidity issues     : {report.liquidity_issue_count}",
        f"INFO/WARN/ERR/FATAL  : {report.info_count}/{report.warning_count}/"
        f"{report.error_count}/{report.fatal_count}",
    ]
    return "\n".join(lines)
