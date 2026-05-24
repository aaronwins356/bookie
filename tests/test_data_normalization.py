import pytest
from src.data.normalizer import normalize_game_row, normalize_market_row
from src.data.adapters.csv_adapter import read_csv
from src.data.adapters.json_adapter import read_json
from src.data.loaders import load_games, load_markets

EX = "data/examples"


class TestGameNormalization:
    def test_camelcase_aliases(self):
        g = normalize_game_row({
            "eventId": "e1", "homeTeam": "A", "awayTeam": "B",
            "homeScore": "10", "awayScore": "7", "clock": "450",
            "period": "2H", "status": "in_progress", "ts": "2024-01-01T00:00:00Z",
            "sport": "NFL", "league": "NFL",
        })
        assert g.event_id == "e1"
        assert g.home_team == "A" and g.away_team == "B"
        assert g.home_score == 10 and g.away_score == 7
        assert g.clock_seconds_remaining == 450
        assert g.timestamp.endswith("+00:00")

    def test_snake_and_alt_aliases(self):
        g = normalize_game_row({
            "game_id": "e2", "home": "X", "away": "Y",
            "home_score": 3, "away_score": 0, "time_remaining": 1200,
            "created_at": 1704067200,  # unix seconds → 2024-01-01
        })
        assert g.event_id == "e2"
        assert g.home_team == "X"
        assert g.timestamp.startswith("2024-01-01")


class TestMarketNormalization:
    def test_derives_no_side_from_yes(self):
        m = normalize_market_row({
            "market_id": "m1", "event_id": "e1", "ts": "2024-01-01T00:00:00Z",
            "yesBid": 60, "yesAsk": 63, "vol": 200, "oi": 100,
        })
        # no_bid = 100 - yes_ask, no_ask = 100 - yes_bid
        assert m.no_bid == pytest.approx(37.0)
        assert m.no_ask == pytest.approx(40.0)

    def test_liquidity_score_derived_when_missing(self):
        m = normalize_market_row({
            "market_id": "m1", "event_id": "e1", "ts": "2024-01-01T00:00:00Z",
            "bid_yes": 50, "ask_yes": 52, "volume": 100, "oi": 100,
        })
        assert m.liquidity_score > 0

    def test_price_alias_last(self):
        m = normalize_market_row({
            "market_id": "m1", "event_id": "e1", "ts": "2024-01-01T00:00:00Z",
            "yes_bid": 50, "yes_ask": 52, "price": 51,
        })
        assert m.last_price == pytest.approx(51.0)


class TestLoaders:
    def test_csv_and_json_normalize_to_same_games(self):
        g_csv = load_games(f"{EX}/raw_game_sample.csv")
        g_json = load_games(f"{EX}/raw_game_sample.json")
        assert len(g_csv) == len(g_json) == 6
        assert [g.home_score for g in g_csv] == [g.home_score for g in g_json]
        assert [g.timestamp for g in g_csv] == [g.timestamp for g in g_json]

    def test_csv_and_json_normalize_to_same_markets(self):
        m_csv = load_markets(f"{EX}/raw_market_sample.csv")
        m_json = load_markets(f"{EX}/raw_market_sample.json")
        assert len(m_csv) == len(m_json) == 6
        assert [m.yes_bid for m in m_csv] == [m.yes_bid for m in m_json]

    def test_raw_readers(self):
        assert len(read_csv(f"{EX}/raw_game_sample.csv")) == 6
        assert len(read_json(f"{EX}/raw_market_sample.json")) == 6
