import pytest
from src.data.schemas import (
    Severity, Verdict, ValidationIssue,
    CanonicalGameEvent, CanonicalMarketSnapshot, CanonicalOrderbookSnapshot,
    CanonicalReplayTick, ReplayBundle, DataQualityReport,
)


def make_game(**kw) -> CanonicalGameEvent:
    base = dict(
        event_id="e1", sport="NFL", league="NFL", home_team="A", away_team="B",
        scheduled_start=None, status="in_progress", period="1H",
        clock_seconds_remaining=900, home_score=0, away_score=0,
        possession="A", timestamp="2024-01-01T00:00:00+00:00",
    )
    base.update(kw)
    return CanonicalGameEvent(**base)


def make_market(**kw) -> CanonicalMarketSnapshot:
    base = dict(
        market_id="m1", event_id="e1", timestamp="2024-01-01T00:00:00+00:00",
        yes_bid=49.0, yes_ask=51.0, no_bid=49.0, no_ask=51.0, last_price=50.0,
        volume=100, open_interest=80, liquidity_score=9.0, source="test",
    )
    base.update(kw)
    return CanonicalMarketSnapshot(**base)


class TestCanonicalModels:
    def test_game_round_trip(self):
        g = make_game()
        assert CanonicalGameEvent.from_dict(g.to_dict()) == g

    def test_market_props_and_round_trip(self):
        m = make_market(yes_bid=40, yes_ask=44)
        assert m.mid == pytest.approx(42.0)
        assert m.spread == pytest.approx(4.0)
        assert CanonicalMarketSnapshot.from_dict(m.to_dict()) == m

    def test_orderbook_round_trip(self):
        ob = CanonicalOrderbookSnapshot(
            market_id="m1", timestamp="2024-01-01T00:00:00+00:00",
            yes_bids=[(49.0, 100)], yes_asks=[(51.0, 80)], depth_score=12.5,
        )
        back = CanonicalOrderbookSnapshot.from_dict(ob.to_dict())
        assert back.yes_bids == [(49.0, 100)]
        assert back.depth_score == 12.5

    def test_replay_tick_round_trip(self):
        tick = CanonicalReplayTick(
            timestamp="2024-01-01T00:00:00+00:00",
            game_event=make_game(), market_snapshot=make_market(),
            metadata={"lag_seconds": 1.5},
        )
        back = CanonicalReplayTick.from_dict(tick.to_dict())
        assert back.metadata["lag_seconds"] == 1.5
        assert back.game_event.event_id == "e1"

    def test_bundle_round_trip(self):
        qr = DataQualityReport(total_game_rows=1, verdict=Verdict.PASS)
        tick = CanonicalReplayTick("2024-01-01T00:00:00+00:00", make_game(), make_market())
        bundle = ReplayBundle(
            bundle_id="b1", created_at="2024-01-01T00:00:00+00:00",
            sport="NFL", league="NFL", event_id="e1", ticks=[tick],
            quality_report=qr, source_metadata={"x": 1},
        )
        back = ReplayBundle.from_dict(bundle.to_dict())
        assert back.bundle_id == "b1"
        assert len(back.ticks) == 1
        assert back.quality_report.verdict == Verdict.PASS


class TestSeverity:
    def test_rank_ordering(self):
        assert Severity.FATAL.rank > Severity.ERROR.rank > Severity.WARNING.rank > Severity.INFO.rank

    def test_issue_round_trip(self):
        iss = ValidationIssue(Severity.ERROR, "CODE", "msg", index=3, suggested_fix="do x")
        assert ValidationIssue.from_dict(iss.to_dict()) == iss
