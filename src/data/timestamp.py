from __future__ import annotations

"""
Timestamp parsing / normalization utilities.

Goal: turn the messy timestamp formats real data arrives in (ISO strings,
unix seconds, unix milliseconds) into timezone-aware UTC datetimes, and
reject genuinely ambiguous input rather than guessing silently.
"""

from datetime import datetime, timezone
from typing import Optional, Union

Number = Union[int, float]

# Plausible epoch-second bounds (2001-09-09 .. 2286-11-20) used to
# disambiguate seconds vs milliseconds for numeric input.
_SEC_MIN = 1_000_000_000          # ~2001 in seconds
_SEC_MAX = 9_999_999_999          # ~2286 in seconds
_MS_MIN = 1_000_000_000_000       # ~2001 in milliseconds
_MS_MAX = 9_999_999_999_999       # ~2286 in milliseconds


class AmbiguousTimestampError(ValueError):
    """Raised when a timestamp cannot be confidently interpreted."""


def parse_timestamp(value: object, *, strict: bool = False) -> datetime:
    """
    Parse a timestamp into a timezone-aware UTC datetime.

    Accepts:
    - datetime (returned normalized to UTC)
    - ISO-8601 strings (with or without offset; naive is assumed UTC unless strict)
    - numeric / numeric-string unix seconds or milliseconds

    `strict=True` rejects naive ISO strings (no timezone) as ambiguous.
    """
    if isinstance(value, datetime):
        return _to_utc(value, strict=strict)

    if value is None or (isinstance(value, str) and not value.strip()):
        raise AmbiguousTimestampError("empty/missing timestamp")

    # Numeric (epoch) — int/float or a pure-digit string.
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _from_epoch(float(value))

    if isinstance(value, str):
        s = value.strip()
        if _is_numeric(s):
            return _from_epoch(float(s))
        return _from_iso(s, strict=strict)

    raise AmbiguousTimestampError(f"unsupported timestamp type: {type(value).__name__}")


def to_iso(dt: datetime) -> str:
    """Canonical ISO-8601 string in UTC (e.g. 2024-01-01T12:00:00+00:00)."""
    return _to_utc(dt).isoformat()


def to_unix_ms(dt: datetime) -> int:
    return int(_to_utc(dt).timestamp() * 1000)


def to_unix_seconds(dt: datetime) -> float:
    return _to_utc(dt).timestamp()


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------
def _to_utc(dt: datetime, *, strict: bool = False) -> datetime:
    if dt.tzinfo is None:
        if strict:
            raise AmbiguousTimestampError("naive datetime without timezone")
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _is_numeric(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def _from_epoch(num: float) -> datetime:
    n = abs(num)
    if _MS_MIN <= n <= _MS_MAX:
        return datetime.fromtimestamp(num / 1000.0, tz=timezone.utc)
    if _SEC_MIN <= n <= _SEC_MAX:
        return datetime.fromtimestamp(num, tz=timezone.utc)
    # Out of plausible range — ambiguous.
    raise AmbiguousTimestampError(f"epoch value out of plausible range: {num}")


def _from_iso(s: str, *, strict: bool = False) -> datetime:
    # Support trailing "Z" (Python <3.11 fromisoformat didn't).
    candidate = s.replace("Z", "+00:00") if s.endswith("Z") else s
    try:
        dt = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise AmbiguousTimestampError(f"unparseable ISO timestamp: {s!r}") from exc
    return _to_utc(dt, strict=strict)
