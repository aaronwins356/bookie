import pytest
from src.models import OrderSide
from src.analytics.pnl import PnLTracker, Trade
from src.analytics.drawdown import DrawdownTracker
from src.analytics.exposure import ExposureTracker
from src.analytics.expectancy import ExpectancyCalculator
from src.analytics.correlation import CorrelationAnalyzer
from src.analytics.strategy_metrics import StrategyMetrics
from src.analytics.performance import PerformanceAnalyzer


class TestPnLTracker:
    def test_open_and_mark_unrealized(self):
        t = PnLTracker()
        t.record(Trade("m", "s", OrderSide.YES, price=50.0, size=10))
        # bought 10 YES @ 50; mark at 60 → +100
        assert t.unrealized({"m": 60.0}) == pytest.approx(100.0)

    def test_realize_on_close(self):
        t = PnLTracker()
        t.record(Trade("m", "s", OrderSide.YES, price=50.0, size=10))
        # selling YES = buying NO. NO @ 40 → YES-equiv 60. Closes long @ profit.
        t.record(Trade("m", "s", OrderSide.NO, price=40.0, size=10))
        assert t.realized_total == pytest.approx(100.0)
        assert t.positions["m"].net_contracts == 0

    def test_slippage_loss_tracked(self):
        t = PnLTracker()
        t.record(Trade("m", "s", OrderSide.YES, price=52.0, size=10), requested_price=50.0)
        assert t.slippage_loss == pytest.approx(20.0)


class TestDrawdown:
    def test_max_drawdown(self):
        d = DrawdownTracker()
        for eq in [0, 100, 60, 120, 40]:
            d.update(eq)
        assert d.max_drawdown == pytest.approx(80.0)   # 120 → 40


class TestExposure:
    def test_aggregation_and_concentration(self):
        e = ExposureTracker()
        e.add("m1", "s1", OrderSide.YES, 50.0, 10)
        e.add("m2", "s2", OrderSide.NO, 50.0, 10)
        assert e.total() == pytest.approx(10.0)
        assert 0.0 <= e.concentration() <= 1.0
        hm = e.heatmap()
        assert "by_market" in hm and "by_strategy" in hm


class TestExpectancy:
    def test_expectancy_positive(self):
        e = ExpectancyCalculator()
        for p in [10, 20, -5, 30, -10]:
            e.record(p)
        assert e.win_rate() == pytest.approx(0.6)
        assert e.expectancy() != 0.0


class TestCorrelation:
    def test_perfect_correlation(self):
        c = CorrelationAnalyzer()
        for v in [1, 2, 3, 4]:
            c.record("a", v)
            c.record("b", v * 2)
        assert c.pearson("a", "b") == pytest.approx(1.0, abs=1e-6)

    def test_negative_correlation(self):
        c = CorrelationAnalyzer()
        for v in [1, 2, 3, 4]:
            c.record("a", v)
            c.record("b", -v)
        assert c.pearson("a", "b") == pytest.approx(-1.0, abs=1e-6)


class TestStrategyMetrics:
    def test_attribution(self):
        m = StrategyMetrics()
        m.record("s1", 50.0, edge=5.0)
        m.record("s1", -20.0, edge=3.0)
        attr = m.attributions["s1"]
        assert attr.trades == 2
        assert attr.realized_pnl == pytest.approx(30.0)
        assert attr.win_rate == pytest.approx(0.5)


class TestPerformanceAnalyzer:
    def test_sharpe_like_and_report(self):
        p = PerformanceAnalyzer()
        for eq in [0, 10, 20, 15, 30]:
            p.record_equity(eq)
        report = p.build_report(realized=30, unrealized=0, fees=1, slippage_loss=2, n_trades=5)
        assert report.total_pnl == pytest.approx(29.0)
        assert report.max_drawdown >= 0.0
        assert isinstance(report.as_dict(), dict)
