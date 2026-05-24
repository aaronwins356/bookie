import json
import pytest
from pathlib import Path
from src.backtest import cli


class TestRunCommand:
    def test_run_scenario_writes_result(self, tmp_path, capsys):
        out = str(tmp_path / "calm")
        rc = cli.main(["run", "--scenario", "calm", "--seed", "1", "--out", out])
        assert rc == 0
        assert "BACKTEST RUN" in capsys.readouterr().out
        result_path = Path(out) / "result.json"
        assert result_path.exists()
        data = json.loads(result_path.read_text(encoding="utf-8"))
        assert data["config"]["scenario_name"] == "calm"

    def test_run_bundle(self, tmp_path, capsys):
        out = str(tmp_path / "bundle")
        rc = cli.main(["run", "--bundle", "data/examples/replay_bundle.json", "--out", out])
        assert rc == 0
        assert (Path(out) / "result.json").exists()

    def test_run_requires_source(self, capsys):
        rc = cli.main(["run", "--seed", "1"])
        assert rc == 2


class TestBatchCommand:
    def test_batch_scenarios(self, tmp_path, capsys):
        out = str(tmp_path / "batch")
        rc = cli.main(["batch", "--scenarios", "calm", "panic", "--seeds", "1", "2",
                       "--out", out, "--no-robustness"])
        assert rc == 0
        out_txt = capsys.readouterr().out
        assert "BATCH BACKTEST" in out_txt
        assert "LEADERBOARD" in out_txt
        for fname in ("batch_result.json", "leaderboard.csv", "strategy_metrics.csv",
                      "regime_metrics.csv", "warnings.txt", "report.txt", "report.json"):
            assert (Path(out) / fname).exists()

    def test_batch_bundle_dir(self, tmp_path, capsys):
        out = str(tmp_path / "bbatch")
        rc = cli.main(["batch", "--bundle-dir", "data/examples", "--out", out, "--no-robustness"])
        assert rc == 0
        assert (Path(out) / "batch_result.json").exists()


class TestLeaderboardAndInspect:
    def test_leaderboard_command(self, tmp_path, capsys):
        out = str(tmp_path / "batch")
        cli.main(["batch", "--scenarios", "calm", "--seeds", "1", "--out", out, "--no-robustness"])
        capsys.readouterr()
        rc = cli.main(["leaderboard", "--results", out])
        assert rc == 0
        assert "LEADERBOARD" in capsys.readouterr().out

    def test_inspect_command(self, tmp_path, capsys):
        out = str(tmp_path / "calm")
        cli.main(["run", "--scenario", "calm", "--seed", "1", "--out", out])
        capsys.readouterr()
        rc = cli.main(["inspect", "--result", str(Path(out) / "result.json")])
        assert rc == 0
        assert "INSPECT RESULT" in capsys.readouterr().out

    def test_leaderboard_missing_dir(self, tmp_path, capsys):
        rc = cli.main(["leaderboard", "--results", str(tmp_path / "nope")])
        assert rc == 2
