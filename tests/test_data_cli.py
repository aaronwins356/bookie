import pytest
from src.data import cli
from src.replay.simulator import run

EX = "data/examples"


class TestValidateCommand:
    def test_validate_pass(self, capsys):
        rc = cli.main(["validate", "--game", f"{EX}/raw_game_sample.csv",
                       "--market", f"{EX}/raw_market_sample.csv"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "VALIDATION REPORT" in out
        assert "PASS" in out

    def test_validate_json_inputs(self, capsys):
        rc = cli.main(["validate", "--game", f"{EX}/raw_game_sample.json",
                       "--market", f"{EX}/raw_market_sample.json"])
        assert rc == 0


class TestBuildAndInspect:
    def test_build_then_inspect(self, capsys, tmp_path):
        out_path = str(tmp_path / "bundle.json")
        rc = cli.main(["build-bundle", "--game", f"{EX}/raw_game_sample.csv",
                       "--market", f"{EX}/raw_market_sample.csv", "--out", out_path])
        assert rc == 0
        assert "BUILD BUNDLE" in capsys.readouterr().out

        rc2 = cli.main(["inspect-bundle", "--bundle", out_path])
        out = capsys.readouterr().out
        assert rc2 == 0
        assert "INSPECT BUNDLE" in out
        assert "ticks       : 6" in out

    def test_build_jsonl(self, tmp_path):
        out_path = str(tmp_path / "bundle.jsonl")
        rc = cli.main(["build-bundle", "--game", f"{EX}/raw_game_sample.csv",
                       "--market", f"{EX}/raw_market_sample.csv", "--out", out_path])
        assert rc == 0
        rc2 = cli.main(["inspect-bundle", "--bundle", out_path])
        assert rc2 == 0


class TestReplayFromBundle:
    def test_simulator_runs_from_bundle(self, capsys, tmp_path):
        out_path = str(tmp_path / "bundle.json")
        cli.main(["build-bundle", "--game", f"{EX}/raw_game_sample.csv",
                  "--market", f"{EX}/raw_market_sample.csv", "--out", out_path])
        capsys.readouterr()  # clear

        run(bundle=out_path)
        out = capsys.readouterr().out
        assert "HISTORICAL REPLAY" in out
        assert "ANALYTICS" in out
        assert "Historical replay complete" in out
        assert "NOT proof of live edge" in out
