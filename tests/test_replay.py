import pytest
from src.replay.sample_data_loader import SampleDataLoader
from src.replay.simulator import build_loop, run


class TestSampleDataLoader:
    def test_comeback_has_ticks(self):
        loader = SampleDataLoader()
        ticks = loader.load_nfl_comeback()
        assert len(ticks) >= 3
        for game, markets in ticks:
            assert game.game_id
            assert len(markets) >= 1

    def test_blowout_has_ticks(self):
        loader = SampleDataLoader()
        ticks = loader.load_blowout()
        assert len(ticks) >= 2


class TestSimulator:
    def test_loop_processes_ticks(self):
        loader = SampleDataLoader()
        ticks = loader.load_nfl_comeback()
        loop = build_loop()

        for game, markets in ticks:
            signals, results = loop.tick(game, markets)
            assert isinstance(signals, list)
            assert isinstance(results, list)

    def test_run_comeback_no_error(self, capsys):
        run(scenario="comeback")
        captured = capsys.readouterr()
        assert "GAME STATE" in captured.out
        assert "MARKET STATE" in captured.out
        assert "SIGNALS" in captured.out

    def test_run_blowout_no_error(self, capsys):
        run(scenario="blowout")
        captured = capsys.readouterr()
        assert "Replay complete" in captured.out
