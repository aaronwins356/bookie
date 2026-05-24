import pytest
from src.data.loaders import load_games, load_markets
from src.data.bundle import build_bundle, save_bundle, load_bundle, to_engine_ticks
from src.data.schemas import Verdict
from src.models import GamePhase, GameState, MarketState

EX = "data/examples"


@pytest.fixture
def sample_bundle():
    games = load_games(f"{EX}/raw_game_sample.csv")
    markets = load_markets(f"{EX}/raw_market_sample.csv")
    return build_bundle(games, markets)


class TestBundleBuild:
    def test_build_clean_pass(self, sample_bundle):
        assert sample_bundle.quality_report.verdict == Verdict.PASS
        assert len(sample_bundle.ticks) == 6
        assert sample_bundle.event_id == "nfl-2024-key"

    def test_deterministic_bundle_id(self):
        games = load_games(f"{EX}/raw_game_sample.csv")
        markets = load_markets(f"{EX}/raw_market_sample.csv")
        a = build_bundle(games, markets)
        b = build_bundle(games, markets)
        assert a.bundle_id == b.bundle_id
        assert a.created_at == b.created_at


class TestBundleRoundTrip:
    def test_json_round_trip(self, sample_bundle, tmp_path):
        p = tmp_path / "bundle.json"
        save_bundle(sample_bundle, p)
        loaded = load_bundle(p)
        assert loaded.bundle_id == sample_bundle.bundle_id
        assert len(loaded.ticks) == len(sample_bundle.ticks)
        assert loaded.quality_report.verdict == sample_bundle.quality_report.verdict

    def test_jsonl_round_trip(self, sample_bundle, tmp_path):
        p = tmp_path / "bundle.jsonl"
        save_bundle(sample_bundle, p)
        loaded = load_bundle(p)
        assert loaded.bundle_id == sample_bundle.bundle_id
        assert len(loaded.ticks) == len(sample_bundle.ticks)

    def test_json_byte_identical_reexport(self, sample_bundle, tmp_path):
        p1, p2 = tmp_path / "a.json", tmp_path / "b.json"
        save_bundle(sample_bundle, p1)
        save_bundle(load_bundle(p1), p2)
        assert p1.read_text() == p2.read_text()


class TestEngineConversion:
    def test_to_engine_ticks(self, sample_bundle):
        ticks = to_engine_ticks(sample_bundle)
        assert len(ticks) == 6
        game, markets = ticks[0]
        assert isinstance(game, GameState)
        assert isinstance(markets[0], MarketState)
        assert game.game_id == "nfl-2024-key"

    def test_final_phase_mapped(self, sample_bundle):
        ticks = to_engine_ticks(sample_bundle)
        last_game, _ = ticks[-1]
        assert last_game.phase == GamePhase.FINAL

    def test_market_prices_preserved(self, sample_bundle):
        ticks = to_engine_ticks(sample_bundle)
        _, markets = ticks[0]
        assert markets[0].yes_bid == 49.0
        assert markets[0].yes_ask == 51.0
