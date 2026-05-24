import pytest
from src.data.schemas import Severity, Verdict
from src.data.validators import (
    validate_game_events, validate_market_snapshots, validate_cross, validate_all,
)
from src.data.quality import build_quality_report
from src.data.timestamp import parse_timestamp, AmbiguousTimestampError
from tests.test_data_schemas import make_game, make_market


def codes(issues):
    return {i.code for i in issues}


class TestGameValidation:
    def test_missing_event_id_fatal(self):
        issues = validate_game_events([make_game(event_id="")])
        assert "GAME_MISSING_EVENT_ID" in codes(issues)
        assert any(i.severity == Severity.FATAL for i in issues)

    def test_negative_score(self):
        issues = validate_game_events([make_game(home_score=-1)])
        assert "GAME_NEGATIVE_SCORE" in codes(issues)

    def test_out_of_order_timestamps(self):
        a = make_game(timestamp="2024-01-01T00:05:00+00:00")
        b = make_game(timestamp="2024-01-01T00:00:00+00:00")
        assert "GAME_TIMESTAMP_OUT_OF_ORDER" in codes(validate_game_events([a, b]))

    def test_clock_backwards_same_period(self):
        a = make_game(period="2H", clock_seconds_remaining=600, timestamp="2024-01-01T00:00:00+00:00")
        b = make_game(period="2H", clock_seconds_remaining=900, timestamp="2024-01-01T00:01:00+00:00")
        assert "GAME_CLOCK_BACKWARDS" in codes(validate_game_events([a, b]))


class TestMarketValidation:
    def test_negative_price(self):
        assert "MARKET_NEGATIVE_PRICE" in codes(validate_market_snapshots([make_market(yes_bid=-5)]))

    def test_price_out_of_range(self):
        assert "MARKET_PRICE_OUT_OF_RANGE" in codes(validate_market_snapshots([make_market(yes_ask=150)]))

    def test_crossed_yes(self):
        assert "MARKET_YES_CROSSED" in codes(validate_market_snapshots([make_market(yes_bid=60, yes_ask=55)]))

    def test_crossed_no(self):
        assert "MARKET_NO_CROSSED" in codes(validate_market_snapshots([make_market(no_bid=60, no_ask=55)]))

    def test_duplicate_snapshot(self):
        m = make_market()
        assert "MARKET_DUPLICATE_SNAPSHOT" in codes(validate_market_snapshots([m, make_market()]))


class TestCrossValidation:
    def test_market_without_matching_event(self):
        issues = validate_cross([make_game(event_id="e1")], [make_market(event_id="e999")])
        assert "MARKET_NO_MATCHING_EVENT" in codes(issues)

    def test_empty_streams_fatal(self):
        issues = validate_cross([], [])
        assert "NO_GAME_EVENTS" in codes(issues)
        assert "NO_MARKET_SNAPSHOTS" in codes(issues)


class TestQualityVerdict:
    def test_pass_clean(self):
        report = build_quality_report([make_game()], [make_market()], [])
        assert report.verdict == Verdict.PASS

    def test_fail_on_error(self):
        events = [make_game()]
        snaps = [make_market(yes_bid=-1)]
        issues = validate_all(events, snaps)
        report = build_quality_report(events, snaps, issues)
        assert report.verdict == Verdict.FAIL
        assert report.error_count >= 1

    def test_warnings_only(self):
        # zero liquidity is a WARNING, not an error
        events = [make_game()]
        snaps = [make_market(volume=0, open_interest=0)]
        issues = validate_market_snapshots(snaps)
        report = build_quality_report(events, snaps, issues)
        assert report.verdict == Verdict.PASS_WITH_WARNINGS


class TestTimestampParsing:
    def test_iso_with_z(self):
        dt = parse_timestamp("2024-01-01T00:00:00Z")
        assert dt.tzinfo is not None
        assert dt.year == 2024

    def test_unix_seconds(self):
        assert parse_timestamp(1704067200).year == 2024

    def test_unix_millis(self):
        assert parse_timestamp(1704067200000).year == 2024

    def test_naive_strict_rejected(self):
        with pytest.raises(AmbiguousTimestampError):
            parse_timestamp("2024-01-01T00:00:00", strict=True)

    def test_empty_rejected(self):
        with pytest.raises(AmbiguousTimestampError):
            parse_timestamp("")

    def test_garbage_rejected(self):
        with pytest.raises(AmbiguousTimestampError):
            parse_timestamp("not-a-time")
