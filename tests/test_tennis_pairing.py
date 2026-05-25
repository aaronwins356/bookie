from __future__ import annotations

import pytest

from src.live.market_discovery import MarketInfo
from src.sports.tennis.match_pairing import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    PairingRejection,
    PairingResult,
    _fuzzy_ratio,
    _normalize_name,
    _normalize_text,
    pair_matches_to_markets,
    score_pair,
)
from src.sports.tennis.provider_base import TennisMatchInfo
from src.sports.tennis.state import Surface, Tour


def _match(
    player_a="Djokovic N.",
    player_b="Alcaraz C.",
    tournament="Wimbledon 2026",
    tour=Tour.ATP,
    match_id="M001",
) -> TennisMatchInfo:
    return TennisMatchInfo(
        match_id=match_id,
        player_a=player_a,
        player_b=player_b,
        tournament=tournament,
        tour=tour,
    )


def _market(
    ticker="KXATP-WIM26-SF001",
    title="Djokovic to win vs Alcaraz - Wimbledon SF",
    series_ticker="KXATP",
    event_ticker="KXATP-WIM26-SF",
    status="open",
) -> MarketInfo:
    return MarketInfo(
        ticker=ticker,
        title=title,
        status=status,
        event_ticker=event_ticker,
        series_ticker=series_ticker,
        yes_bid=48.0,
        yes_ask=52.0,
        volume=1000,
    )


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

class TestNormalizeName:
    def test_lowercase(self):
        assert _normalize_name("DJOKOVIC") == "djokovic"

    def test_removes_accents(self):
        # ó → o, é → e
        assert _normalize_name("Djokovic Novák") == "djokovic novak"

    def test_removes_punctuation(self):
        assert "." not in _normalize_name("Djokovic N.")

    def test_collapses_spaces(self):
        assert "  " not in _normalize_name("a  b")


class TestFuzzyRatio:
    def test_identical_strings(self):
        assert _fuzzy_ratio("djokovic", "djokovic") == pytest.approx(1.0)

    def test_empty_string(self):
        assert _fuzzy_ratio("", "djokovic") == 0.0

    def test_completely_different(self):
        assert _fuzzy_ratio("djokovic", "zzzzz") < 0.3

    def test_partial_match(self):
        r = _fuzzy_ratio("djokovic", "djokovics")
        assert r > 0.80


# ---------------------------------------------------------------------------
# score_pair
# ---------------------------------------------------------------------------

class TestScorePair:
    def test_returns_pairing_result(self):
        r = score_pair(_match(), _market())
        assert isinstance(r, PairingResult)

    def test_confidence_in_range(self):
        r = score_pair(_match(), _market())
        assert 0.0 <= r.confidence <= 1.0

    def test_high_confidence_for_matching_pair(self):
        # Players clearly in title, ATP in series, Wimbledon keyword
        r = score_pair(_match(), _market())
        assert r.confidence >= 0.50

    def test_low_confidence_for_wrong_sport(self):
        market = _market(
            ticker="KXBTC-001",
            title="Bitcoin price above 50k",
            series_ticker="KXBTC",
            event_ticker="KXBTC-001",
        )
        r = score_pair(_match(), market)
        assert r.confidence < 0.40

    def test_reasons_is_list(self):
        r = score_pair(_match(), _market())
        assert isinstance(r.reasons, list)
        assert len(r.reasons) == 3  # player, tournament, tour

    def test_accepted_property_above_threshold(self):
        r = score_pair(_match(), _market())
        assert r.accepted == (r.confidence >= DEFAULT_CONFIDENCE_THRESHOLD)

    def test_match_and_market_stored(self):
        m = _match()
        mkt = _market()
        r = score_pair(m, mkt)
        assert r.match is m
        assert r.market is mkt

    def test_wta_series_matches_wta_tour(self):
        wta_match = _match(
            player_a="Swiatek I.", player_b="Sabalenka A.",
            tournament="Roland Garros 2026", tour=Tour.WTA,
        )
        wta_market = _market(
            ticker="KXWTA-RG26-F001",
            title="Swiatek vs Sabalenka Roland Garros Final",
            series_ticker="KXWTA",
            event_ticker="KXWTA-RG26-F",
        )
        r = score_pair(wta_match, wta_market)
        assert r.confidence >= 0.50

    def test_atp_series_rejects_wta_match(self):
        wta_match = _match(
            player_a="Swiatek I.", player_b="Sabalenka A.",
            tournament="Roland Garros 2026", tour=Tour.WTA,
        )
        atp_market = _market(
            ticker="KXATP-USO26-001",
            title="Djokovic vs Sinner US Open",
            series_ticker="KXATP",
            event_ticker="KXATP-USO26",
        )
        r = score_pair(wta_match, atp_market)
        # Player names won't match, tour won't match → low confidence
        assert r.confidence < 0.55

    def test_str_representation(self):
        r = score_pair(_match(), _market())
        s = str(r)
        assert "ACCEPTED" in s or "REJECTED" in s


# ---------------------------------------------------------------------------
# pair_matches_to_markets
# ---------------------------------------------------------------------------

class TestPairMatchesToMarkets:
    def _good_matches_and_markets(self):
        matches = [
            _match(match_id="M001"),
            _match(player_a="Sinner J.", player_b="Zverev A.",
                   tournament="US Open 2026", tour=Tour.ATP, match_id="M002"),
        ]
        markets = [
            _market(ticker="KXATP-WIM26-SF001",
                    title="Djokovic to win vs Alcaraz - Wimbledon SF",
                    series_ticker="KXATP", event_ticker="KXATP-WIM26-SF"),
            _market(ticker="KXATP-USO26-QF001",
                    title="Sinner vs Zverev US Open QF",
                    series_ticker="KXATP", event_ticker="KXATP-USO26-QF"),
        ]
        return matches, markets

    def test_returns_two_lists(self):
        matches, markets = self._good_matches_and_markets()
        accepted, rejected = pair_matches_to_markets(matches, markets)
        assert isinstance(accepted, list)
        assert isinstance(rejected, list)

    def test_total_equals_input_matches(self):
        matches, markets = self._good_matches_and_markets()
        accepted, rejected = pair_matches_to_markets(matches, markets)
        assert len(accepted) + len(rejected) == len(matches)

    def test_one_market_not_claimed_twice(self):
        # Two matches, one market — only one can be accepted
        matches = [_match(match_id="M001"), _match(match_id="M002")]
        markets = [_market(ticker="KXATP-WIM26-SF001")]
        accepted, rejected = pair_matches_to_markets(matches, markets)
        tickers = [p.market.ticker for p in accepted]
        assert len(tickers) == len(set(tickers))

    def test_empty_markets_all_rejected(self):
        matches = [_match()]
        accepted, rejected = pair_matches_to_markets(matches, [])
        assert len(accepted) == 0
        assert len(rejected) == 1

    def test_empty_matches_returns_empty(self):
        accepted, rejected = pair_matches_to_markets([], [_market()])
        assert accepted == []
        assert rejected == []

    def test_low_confidence_pair_rejected(self):
        unrelated_match = _match(
            player_a="RandomPlayer X.", player_b="OtherPlayer Y.",
            tournament="Unknown Tournament", tour=Tour.UNKNOWN,
        )
        unrelated_market = _market(
            ticker="KXBTC-001",
            title="Bitcoin above 50k",
            series_ticker="KXBTC",
            event_ticker="KXBTC-001",
        )
        accepted, rejected = pair_matches_to_markets(
            [unrelated_match], [unrelated_market]
        )
        assert len(rejected) >= 1

    def test_custom_threshold_zero_accepts_all(self):
        # threshold=0.0 → all pairs accepted (even low confidence)
        matches = [_match()]
        markets = [_market()]
        accepted, rejected = pair_matches_to_markets(matches, markets, threshold=0.0)
        assert len(accepted) == 1

    def test_custom_threshold_one_rejects_all(self):
        # threshold=1.0 → no pair is perfect
        matches = [_match()]
        markets = [_market()]
        accepted, rejected = pair_matches_to_markets(matches, markets, threshold=1.0)
        assert len(rejected) == 1

    def test_rejection_has_best_confidence(self):
        unrelated_match = _match(
            player_a="NoOneKnown Z.", player_b="SomeOther Q.",
            tournament="Mystery Cup", tour=Tour.UNKNOWN,
        )
        _, rejected = pair_matches_to_markets([unrelated_match], [_market()], threshold=1.0)
        assert rejected[0].best_confidence >= 0.0

    def test_rejection_has_reason(self):
        _, rejected = pair_matches_to_markets([_match()], [], threshold=0.55)
        assert rejected[0].reason  # non-empty string

    def test_accepted_results_have_confidence_above_threshold(self):
        matches, markets = self._good_matches_and_markets()
        accepted, _ = pair_matches_to_markets(matches, markets, threshold=0.0)
        for p in accepted:
            assert p.confidence >= 0.0

    def test_mock_provider_matches_mock_markets(self):
        """End-to-end: mock provider matches → mock market titles pair up."""
        from src.sports.tennis.mock_provider import MockProvider
        from src.live.market_discovery import MarketInfo

        provider = MockProvider()
        matches = provider.list_live_matches()
        markets = [
            MarketInfo(
                ticker="KXATP-WIM26-SF001",
                title="Djokovic to win vs Alcaraz Wimbledon SF",
                status="open",
                event_ticker="KXATP-WIM26-SF",
                series_ticker="KXATP",
                yes_bid=48.0, yes_ask=52.0, volume=1200,
            ),
            MarketInfo(
                ticker="KXATP-USO26-QF002",
                title="Sinner vs Zverev US Open Men QF",
                status="open",
                event_ticker="KXATP-USO26-QF",
                series_ticker="KXATP",
                yes_bid=55.0, yes_ask=59.0, volume=800,
            ),
            MarketInfo(
                ticker="KXWTA-RG26-F001",
                title="Swiatek vs Sabalenka Roland Garros Women Final",
                status="open",
                event_ticker="KXWTA-RG26-F",
                series_ticker="KXWTA",
                yes_bid=44.0, yes_ask=48.0, volume=2100,
            ),
        ]
        accepted, rejected = pair_matches_to_markets(matches, markets)
        # At least one pair should be accepted given matching names + tours
        assert len(accepted) >= 1
