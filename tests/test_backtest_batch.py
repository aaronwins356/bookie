import json
import pytest
from pathlib import Path
from src.backtest.config import BacktestConfig
from src.backtest.batch import BatchRunner, export_batch


def _configs():
    return [
        BacktestConfig(name="calm_s1", seed=1, scenario_name="calm"),
        BacktestConfig(name="panic_s1", seed=1, scenario_name="panic"),
    ]


class TestBatchRun:
    def test_runs_all(self):
        batch = BatchRunner(compute_robustness=False).run(_configs(), batch_id="t")
        assert len(batch.results) == 2
        assert batch.leaderboard
        assert batch.aggregate_metrics["n_runs"] == 2

    def test_continues_past_failure(self):
        configs = _configs() + [BacktestConfig(name="bad", seed=1, bundle_path="nope.json")]
        batch = BatchRunner(compute_robustness=False).run(configs, batch_id="t")
        # bad bundle produces an empty result with a warning, batch survives
        assert len(batch.results) == 3
        assert any("failed to load" in w for w in batch.warnings)

    def test_leaderboard_covers_all_strategies(self):
        batch = BatchRunner(compute_robustness=False).run(_configs(), batch_id="t")
        names = {row.strategy_name for row in batch.leaderboard}
        assert len(names) == 5


class TestExport:
    def test_export_files_exist_and_valid(self, tmp_path):
        batch = BatchRunner(compute_robustness=False).run(_configs(), batch_id="t")
        artifacts = export_batch(batch, tmp_path)

        for key in ("batch_result", "leaderboard_csv", "strategy_metrics_csv",
                    "regime_metrics_csv", "warnings_txt"):
            assert Path(artifacts[key]).exists()

        with open(artifacts["batch_result"], encoding="utf-8") as fh:
            data = json.load(fh)
        assert data["batch_id"] == "t"
        assert "leaderboard" in data

        lb = Path(artifacts["leaderboard_csv"]).read_text(encoding="utf-8")
        assert "strategy" in lb.splitlines()[0]

    def test_report_generated(self, tmp_path):
        from src.backtest.report import write_report
        batch = BatchRunner(compute_robustness=False).run(_configs(), batch_id="t")
        paths = write_report(batch, tmp_path)
        text = Path(paths["report_txt"]).read_text(encoding="utf-8")
        assert "RESEARCH REPORT" in text
        assert "not proof of live edge" in text.lower()
