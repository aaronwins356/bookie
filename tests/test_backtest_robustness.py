import pytest
from src.backtest.config import BacktestConfig
from src.backtest import robustness


class TestRobustness:
    def test_report_shape(self):
        cfg = BacktestConfig(name="calm", seed=1, scenario_name="calm")
        rep = robustness.run_robustness(cfg, seeds=[1, 2])
        assert 0.0 <= rep.score <= 1.0
        assert "worse_slippage" in rep.perturbation_pnls
        assert "higher_latency" in rep.perturbation_pnls
        assert "higher_fees" in rep.perturbation_pnls
        assert len(rep.seed_pnls) == 2

    def test_deterministic(self):
        cfg = BacktestConfig(name="panic", seed=3, scenario_name="panic")
        a = robustness.run_robustness(cfg, seeds=[3, 4])
        b = robustness.run_robustness(cfg, seeds=[3, 4])
        assert a.score == b.score
        assert a.perturbation_pnls == b.perturbation_pnls

    def test_strategy_robustness_isolated(self):
        cfg = BacktestConfig(name="calm", seed=1, scenario_name="calm")
        rep = robustness.strategy_robustness("favorite_grinder", cfg)
        assert 0.0 <= rep.score <= 1.0

    def test_to_dict(self):
        cfg = BacktestConfig(name="calm", seed=1, scenario_name="calm")
        d = robustness.run_robustness(cfg, seeds=[1]).to_dict()
        assert "score" in d and "perturbation_pnls" in d and "flags" in d
