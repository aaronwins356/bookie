import pytest
from src.data.aligner import align
from tests.test_data_schemas import make_game, make_market


def g(ts, **kw):
    return make_game(timestamp=ts, **kw)


def m(ts, **kw):
    return make_market(timestamp=ts, **kw)


class TestAlignment:
    def test_basic_alignment(self):
        events = [g("2024-01-01T00:00:00+00:00"), g("2024-01-01T00:01:00+00:00")]
        snaps = [m("2024-01-01T00:00:05+00:00"), m("2024-01-01T00:01:03+00:00")]
        res = align(events, snaps, max_lag_seconds=60)
        assert len(res.ticks) == 2
        # nearest game attached
        assert res.ticks[0].game_event.timestamp == "2024-01-01T00:00:00+00:00"

    def test_lag_recorded_in_metadata(self):
        events = [g("2024-01-01T00:00:00+00:00")]
        snaps = [m("2024-01-01T00:00:05+00:00")]
        res = align(events, snaps, max_lag_seconds=60)
        assert res.ticks[0].metadata["lag_seconds"] == pytest.approx(5.0)

    def test_drop_beyond_max_lag(self):
        events = [g("2024-01-01T00:00:00+00:00")]
        snaps = [m("2024-01-01T01:00:00+00:00")]   # 1h away
        res = align(events, snaps, max_lag_seconds=60)
        assert len(res.ticks) == 0
        assert res.dropped == 1

    def test_deterministic_ordering(self):
        events = [g("2024-01-01T00:00:00+00:00"), g("2024-01-01T00:02:00+00:00")]
        snaps = [
            m("2024-01-01T00:02:02+00:00"),
            m("2024-01-01T00:00:02+00:00"),
        ]
        res = align(events, snaps, max_lag_seconds=60)
        stamps = [t.timestamp for t in res.ticks]
        assert stamps == sorted(stamps)

    def test_stale_market_on_feed_gap(self):
        events = [g("2024-01-01T00:00:00+00:00"), g("2024-01-01T00:05:00+00:00")]
        snaps = [
            m("2024-01-01T00:00:01+00:00"),
            m("2024-01-01T00:05:01+00:00"),   # ~300s gap → stale market
        ]
        res = align(events, snaps, max_lag_seconds=60)
        assert res.stale_market >= 1
