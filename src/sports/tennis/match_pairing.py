from __future__ import annotations

"""
Fuzzy matching of tennis score-feed matches to Kalshi market titles.

Problem: Kalshi market titles look like:
  "Djokovic to win vs Alcaraz - Wimbledon Men's QF"
  "KXATP-WIM26-SF001"

Score-feed match info has:
  player_a="Djokovic N.", player_b="Alcaraz C.", tournament="Wimbledon 2026"

This module computes a confidence score (0.0–1.0) for each
(TennisMatchInfo, KalshiMarket) candidate pair and returns the best match
above a configurable rejection threshold (default 0.55).

No API calls are made here — all inputs are plain Python objects.
"""

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Optional, Tuple

from src.live.market_discovery import MarketInfo
from src.sports.tennis.provider_base import TennisMatchInfo


# ---------------------------------------------------------------------------
# Public threshold
# ---------------------------------------------------------------------------

DEFAULT_CONFIDENCE_THRESHOLD = 0.55


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class PairingResult:
    match: TennisMatchInfo
    market: MarketInfo
    confidence: float
    reasons: List[str]

    @property
    def accepted(self) -> bool:
        return self.confidence >= DEFAULT_CONFIDENCE_THRESHOLD

    def __str__(self) -> str:
        status = "ACCEPTED" if self.accepted else "REJECTED"
        return (
            f"[{status} {self.confidence:.2f}] "
            f"{self.match.display_name} ↔ {self.market.ticker}\n"
            f"  " + "\n  ".join(self.reasons)
        )


@dataclass
class PairingRejection:
    match: TennisMatchInfo
    reason: str
    best_confidence: float


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def pair_matches_to_markets(
    matches: List[TennisMatchInfo],
    markets: List[MarketInfo],
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> Tuple[List[PairingResult], List[PairingRejection]]:
    """
    For each match, find the best-scoring Kalshi market and return it
    if confidence ≥ threshold.

    Returns (accepted, rejected) lists.
    One match maps to at most one market; one market can only be claimed once.
    """
    accepted: List[PairingResult] = []
    rejected: List[PairingRejection] = []
    claimed_tickers: set[str] = set()

    for match in matches:
        best: Optional[PairingResult] = None

        for market in markets:
            if market.ticker in claimed_tickers:
                continue
            result = score_pair(match, market)
            if best is None or result.confidence > best.confidence:
                best = result

        if best is None:
            rejected.append(PairingRejection(
                match=match,
                reason="no markets available",
                best_confidence=0.0,
            ))
        elif best.confidence < threshold:
            rejected.append(PairingRejection(
                match=match,
                reason=f"best confidence {best.confidence:.2f} below threshold {threshold:.2f}",
                best_confidence=best.confidence,
            ))
        else:
            accepted.append(best)
            claimed_tickers.add(best.market.ticker)

    return accepted, rejected


def score_pair(match: TennisMatchInfo, market: MarketInfo) -> PairingResult:
    """
    Compute a confidence score for one (match, market) pair.
    Score is a weighted average of sub-scores:
      - player name match (weight 0.50)
      - tournament match  (weight 0.30)
      - tour/series match (weight 0.20)
    """
    reasons: List[str] = []

    player_score, player_reason = _player_score(match, market)
    reasons.append(player_reason)

    tourney_score, tourney_reason = _tournament_score(match, market)
    reasons.append(tourney_reason)

    tour_score, tour_reason = _tour_score(match, market)
    reasons.append(tour_reason)

    confidence = (
        player_score * 0.50
        + tourney_score * 0.30
        + tour_score * 0.20
    )
    confidence = round(min(1.0, max(0.0, confidence)), 4)

    return PairingResult(
        match=match,
        market=market,
        confidence=confidence,
        reasons=reasons,
    )


# ---------------------------------------------------------------------------
# Sub-scorers
# ---------------------------------------------------------------------------

def _player_score(match: TennisMatchInfo, market: MarketInfo) -> Tuple[float, str]:
    """
    Check how well player A and player B appear in the market title/ticker.

    Strategy: extract player name tokens from the market title, then compare
    each against normalised versions of player_a and player_b. Take the best
    similarity found for each player and average them.
    """
    title_tokens = _extract_name_tokens(market.title)
    ticker_tokens = _extract_name_tokens(market.series_ticker + " " + market.event_ticker)
    all_tokens = title_tokens + ticker_tokens

    a_norm = _normalize_name(match.player_a)
    b_norm = _normalize_name(match.player_b)

    a_score = _best_token_match(a_norm, all_tokens)
    b_score = _best_token_match(b_norm, all_tokens)

    combined = (a_score + b_score) / 2.0
    reason = (
        f"player_score={combined:.2f} "
        f"(A={a_score:.2f} '{match.player_a}', B={b_score:.2f} '{match.player_b}') "
        f"in title='{market.title[:60]}'"
    )
    return combined, reason


def _tournament_score(match: TennisMatchInfo, market: MarketInfo) -> Tuple[float, str]:
    """
    Score tournament name similarity.
    Also matches common abbreviations (WIM→Wimbledon, USO→US Open, RG→Roland Garros, AO→Australian Open).
    """
    t_norm = _normalize_text(match.tournament)
    target = _normalize_text(market.title + " " + market.series_ticker + " " + market.event_ticker)

    # Direct substring / abbreviation check first
    abbrev_score = _tournament_abbrev_score(match.tournament, target)

    # Fuzzy similarity on tournament name tokens
    t_tokens = t_norm.split()
    fuzzy = max(
        (_fuzzy_ratio(tok, target) for tok in t_tokens),
        default=0.0,
    )

    score = max(abbrev_score, fuzzy)
    reason = f"tournament_score={score:.2f} '{match.tournament}' vs '{market.title[:50]}'"
    return score, reason


def _tour_score(match: TennisMatchInfo, market: MarketInfo) -> Tuple[float, str]:
    """
    Check if the tour (ATP/WTA) is consistent with the market series ticker.
    """
    tour_val = match.tour.value.upper()
    ticker_up = market.series_ticker.upper()
    title_up = market.title.upper()

    if tour_val in ticker_up or tour_val in title_up:
        return 1.0, f"tour_score=1.0 ({tour_val} found in ticker/title)"
    if tour_val == "UNKNOWN":
        return 0.5, "tour_score=0.5 (tour unknown)"
    return 0.0, f"tour_score=0.0 ({tour_val} not in ticker/title)"


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

_GRAND_SLAM_ABBREVS = {
    "WIM": "wimbledon",
    "USO": "us open",
    "RG": "roland garros",
    "AO": "australian open",
    "FROPEN": "french open",
}


def _tournament_abbrev_score(tournament: str, target_norm: str) -> float:
    t_up = tournament.upper()
    for abbrev, full in _GRAND_SLAM_ABBREVS.items():
        if abbrev in t_up or full in _normalize_text(tournament):
            if abbrev in target_norm.upper() or full in target_norm:
                return 0.90
    return 0.0


def _normalize_name(name: str) -> str:
    """
    Normalize a player name for matching:
    - Remove accents / diacritics
    - Lowercase
    - Remove punctuation except spaces
    - Handle "Surname I." → "surname i"
    """
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(c for c in nfkd if not unicodedata.combining(c))
    lower = ascii_name.lower()
    cleaned = re.sub(r"[^a-z0-9 ]", " ", lower)
    return " ".join(cleaned.split())


def _normalize_text(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_text.lower()


def _extract_name_tokens(text: str) -> List[str]:
    """
    Split text into candidate surname tokens (length ≥ 3).
    Drops common stop-words that appear in market titles.
    """
    _STOP = {"to", "win", "vs", "match", "winner", "semi", "final", "quarter",
             "open", "the", "and", "in", "at", "on", "of", "for", "men",
             "women", "singles", "doubles", "atp", "wta"}
    norm = _normalize_name(text)
    tokens = [t for t in norm.split() if len(t) >= 3 and t not in _STOP]
    return tokens


def _best_token_match(name_norm: str, tokens: List[str]) -> float:
    """
    Best similarity between name_norm and any single token in tokens.
    Also checks if the whole name appears as a substring.
    """
    if not tokens:
        return 0.0
    # Check full name as substring match in concatenated tokens
    tokens_str = " ".join(tokens)
    if name_norm in tokens_str:
        return 1.0
    # Token-by-token fuzzy match
    best = 0.0
    for tok in tokens:
        r = _fuzzy_ratio(name_norm, tok)
        if r > best:
            best = r
        # Also match last-name prefix: "djokovic" matches "djokovic n"
        for part in name_norm.split():
            r2 = _fuzzy_ratio(part, tok)
            if r2 > best:
                best = r2
    return best


def _fuzzy_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()
