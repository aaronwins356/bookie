import pytest
from src.backtest.config import BacktestConfig
from src.backtest.runner import BacktestRunner, run_config


class TestScenarioRun:
    def test_simulated_scenario(self):
        r = run_config(BacktestConfig(name="calm", seed=1, scenario_name="calm"))
        assert r.ticks_processed == 6
        assert len(r.strategy_metrics) == 5
        assert r.regime_metrics
        assert r.config.name == "calm"

    def test_scripted_scenario(self):
        r = run_config(BacktestConfig(name="comeback", seed=1, scenario_name="comeback"))
        assert r.ticks_processed >= 3
        assert isinstance(r.fills, int)

    def test_deterministic(self):
        a = run_config(BacktestConfig(name="p", seed=7, scenario_name="panic"))
        b = run_config(BacktestConfig(name="p", seed=7, scenario_name="panic"))
        assert a.pnl_summary.total_pnl_cents == b.pnl_summary.total_pnl_cents
        assert a.fills == b.fills


class TestBundleRun:
    def test_bundle_source(self):
        r = run_config(BacktestConfig(
            name="b", seed=1, bundle_path="data/examples/replay_bundle.json"))
        assert r.ticks_processed == 6
        assert r.fills >= 1
        assert r.pnl_summary.total_pnl_cents != 0.0

    def test_missing_bundle_is_warning_not_crash(self):
        r = run_config(BacktestConfig(name="bad", seed=1, bundle_path="does/not/exist.json"))
        assert r.ticks_processed == 0
        assert any("failed to load" in w for w in r.warnings)


class TestStrategyToggles:
    def test_disabled_strategy_excluded(self):
        cfg = BacktestConfig(name="x", seed=1, scenario_name="calm",
                             disabled_strategies=["favorite_grinder"])
        r = run_config(cfg)
        names = {m.strategy_name for m in r.strategy_metrics}
        assert "favorite_grinder" not in names
        assert len(names) == 4

    def test_single_strategy(self):
        cfg = BacktestConfig(name="x", seed=1, scenario_name="panic",
                             enabled_strategies=["momentum"])
        r = run_config(cfg)
        assert {m.strategy_name for m in r.strategy_metrics} == {"momentum"}


class TestResultSerialization:
    def test_round_trip(self):
        from src.backtest.result import BacktestResult
        r = run_config(BacktestConfig(name="calm", seed=1, scenario_name="calm"))
        back = BacktestResult.from_dict(r.to_dict())
        assert back.fills == r.fills
        assert back.config.name == r.config.name
        assert len(back.strategy_metrics) == len(r.strategy_metrics)
