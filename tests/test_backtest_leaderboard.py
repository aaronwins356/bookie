import pytest
from src.backtest.config import BacktestConfig
from src.backtest.result import BacktestResult, StrategyMetric, PnLSummary
from src.backtest.leaderboard import build_leaderboard, aggregate_strategies


def _result_with(metrics):
    cfg = BacktestConfig(name="t", seed=1, scenario_name="calm")
    r = BacktestResult(config=cfg, started_at="x", completed_at="y")
    r.strategy_metrics = metrics
    return r


class TestAggregation:
    def test_aggregates_across_runs(self):
        m1 = StrategyMetric("s1", trades=5, fills=5, wins=3, losses=2, total_pnl_cents=100.0, edge_sum=40)
        m2 = StrategyMetric("s1", trades=5, fills=5, wins=2, losses=3, total_pnl_cents=-50.0, edge_sum=30)
        aggs = aggregate_strategies([_result_with([m1]), _result_with([m2])])
        assert aggs["s1"].fills == 10
        assert aggs["s1"].total_pnl == 50.0
        assert aggs["s1"].per_run_pnl == [100.0, -50.0]


class TestRanking:
    def test_balanced_score_beats_raw_pnl(self):
        # huge-pnl but tiny-sample + concentrated vs modest steady performer
        big = StrategyMetric("big_but_fragile", trades=2, fills=2, wins=2, losses=0,
                             total_pnl_cents=5000.0, edge_sum=200.0,
                             regime_pnl={"PANIC_BUYING": 5000.0})
        steady = StrategyMetric("steady", trades=40, fills=40, wins=24, losses=16,
                                total_pnl_cents=400.0, edge_sum=300.0,
                                regime_pnl={"CALM": 200.0, "TRENDING_UP": 200.0})
        rows = build_leaderboard(
            [_result_with([big]), _result_with([steady])],
            robustness_scores={"big_but_fragile": 0.1, "steady": 0.8},
        )
        ranked = [r.strategy_name for r in rows]
        # steady should outrank the fragile high-PnL strategy
        assert ranked.index("steady") < ranked.index("big_but_fragile")

    def test_low_sample_flagged(self):
        m = StrategyMetric("s", trades=3, fills=3, wins=2, losses=1, total_pnl_cents=30.0, edge_sum=10)
        rows = build_leaderboard([_result_with([m])])
        assert any("LOW_SAMPLE" in f for f in rows[0].warning_flags)

    def test_perfect_winrate_flagged(self):
        m = StrategyMetric("s", trades=5, fills=5, wins=5, losses=0, total_pnl_cents=50.0, edge_sum=20)
        rows = build_leaderboard([_result_with([m])])
        assert any("PERFECT_WINRATE" in f for f in rows[0].warning_flags)

    def test_regime_strengths_and_weaknesses(self):
        m = StrategyMetric("s", trades=40, fills=40, wins=20, losses=20, total_pnl_cents=50.0,
                           edge_sum=100, regime_pnl={"CALM": 100.0, "PANIC_SELLING": -50.0})
        rows = build_leaderboard([_result_with([m])])
        row = rows[0]
        assert "CALM" in row.regime_strengths
        assert "PANIC_SELLING" in row.regime_weaknesses

    def test_sorted_descending(self):
        a = StrategyMetric("a", trades=40, fills=40, wins=30, losses=10, total_pnl_cents=300, edge_sum=100)
        b = StrategyMetric("b", trades=40, fills=40, wins=10, losses=30, total_pnl_cents=-300, edge_sum=100)
        rows = build_leaderboard([_result_with([a, b])],
                                 robustness_scores={"a": 0.9, "b": 0.1})
        assert [r.score for r in rows] == sorted([r.score for r in rows], reverse=True)
