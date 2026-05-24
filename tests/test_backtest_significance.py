import pytest
from src.backtest import significance
from src.backtest.significance import bootstrap_ci


class TestBootstrapCI:
    def test_deterministic_with_seed(self):
        xs = [1.0, 2.0, 3.0, -1.0, 5.0, 0.5]
        a = bootstrap_ci(xs, seed=42)
        b = bootstrap_ci(xs, seed=42)
        assert a.low == b.low and a.high == b.high

    def test_low_below_high(self):
        ci = bootstrap_ci([1, 2, 3, 4, 5], seed=1)
        assert ci.low <= ci.mean <= ci.high

    def test_empty(self):
        ci = bootstrap_ci([], seed=1)
        assert ci.n == 0

    def test_crosses_zero(self):
        ci = bootstrap_ci([-5, 5, -4, 4, -3, 3], seed=1)
        assert ci.crosses_zero


class TestWarnings:
    def test_low_sample(self):
        assert significance.warn_low_sample(5) is not None
        assert significance.warn_low_sample(1000) is None

    def test_too_few_events(self):
        assert significance.warn_too_few_events(1) is not None
        assert significance.warn_too_few_events(50) is None

    def test_perfect_winrate(self):
        assert significance.warn_perfect_winrate(1.0, 5) is not None
        assert significance.warn_perfect_winrate(0.6, 50) is None

    def test_high_variance(self):
        noisy = [100, -98, 102, -99, 101, -100]
        assert significance.warn_high_variance(noisy) is not None
        steady = [10, 11, 9, 10, 10, 11]
        assert significance.warn_high_variance(steady) is None

    def test_lagging_mid(self):
        assert significance.warn_lagging_mid(20.0, 0.9) is not None
        assert significance.warn_lagging_mid(3.0, 0.9) is None

    def test_concentration(self):
        assert significance.warn_concentration({"A": 100.0, "B": 1.0}, "REGIME") is not None
        assert significance.warn_concentration({"A": 50.0, "B": 50.0}, "REGIME") is None


class TestResultWarnings:
    def test_evaluate_result_warnings(self):
        from src.backtest.runner import run_config
        from src.backtest.config import BacktestConfig
        r = run_config(BacktestConfig(name="calm", seed=1, scenario_name="calm"))
        warnings = significance.evaluate_result_warnings(r, n_events=1)
        # tiny sample → should at least warn about sample size / events
        assert any("LOW_SAMPLE" in w or "TOO_FEW_EVENTS" in w for w in warnings)
