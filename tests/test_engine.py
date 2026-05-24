import pytest
from src.models import GameState, MarketState, GamePhase
from src.engine.features import FeatureExtractor
from src.engine.fair_value import FairValueModel
from src.engine.router import Router
from src.models import SignalDirection, Signal, Regime


def make_game(diff: int = 7, clock: int = 600, phase: GamePhase = GamePhase.SECOND_HALF) -> GameState:
    return GameState(
        game_id="test-001",
        sport="NFL",
        home_team="Home",
        away_team="Away",
        home_score=10 + diff,
        away_score=10,
        phase=phase,
        clock_seconds=clock,
    )


def make_market(mid: float = 55.0, spread: float = 4.0) -> MarketState:
    half = spread / 2.0
    return MarketState(
        market_id="test-001-win",
        game_id="test-001",
        title="Test Market",
        yes_ask=mid + half,
        yes_bid=mid - half,
        volume=300,
        open_interest=50,
    )


class TestFeatureExtractor:
    def test_basic_extraction(self):
        fe = FeatureExtractor()
        game = make_game(diff=7, clock=600)
        market = make_market(mid=60.0)
        fs = fe.extract(game, market)

        assert fs.score_diff == 7
        assert fs.clock_seconds == 600
        assert fs.mid_price == pytest.approx(60.0)
        assert 0.0 <= fs.time_pressure <= 1.0
        assert fs.implied_prob == pytest.approx(0.60)

    def test_time_pressure_halftime(self):
        fe = FeatureExtractor()
        game = make_game(clock=0, phase=GamePhase.HALFTIME)
        market = make_market()
        fs = fe.extract(game, market)
        assert fs.time_pressure == pytest.approx(1.0)


class TestFairValueModel:
    def test_home_leading_priced_up(self):
        fv = FairValueModel()

        class Feat:
            score_diff = 14
            time_pressure = 0.8

        prob = fv.estimate(Feat())
        assert prob > 80.0

    def test_tied_near_50(self):
        fv = FairValueModel()

        class Feat:
            score_diff = 0
            time_pressure = 0.5

        prob = fv.estimate(Feat())
        assert 45.0 < prob < 55.0


class TestRouter:
    def _make_signal(self, direction: SignalDirection, edge: float, confidence: float = 0.7) -> Signal:
        return Signal(
            strategy_name="test",
            market_id="m-001",
            direction=direction,
            confidence=confidence,
            fair_value=60.0,
            current_price=55.0,
            edge=edge,
            regime=Regime.TRENDING,
        )

    def test_buy_signal_routes_to_yes(self):
        router = Router()
        sig = self._make_signal(SignalDirection.BUY, edge=5.0)
        intent = router.route(sig)
        assert intent is not None
        from src.models import OrderSide
        assert intent.side == OrderSide.YES
        assert intent.size >= 1

    def test_hold_signal_returns_none(self):
        router = Router()
        sig = self._make_signal(SignalDirection.HOLD, edge=0.0, confidence=0.0)
        assert router.route(sig) is None

    def test_small_edge_not_routed(self):
        router = Router()
        sig = self._make_signal(SignalDirection.BUY, edge=1.0, confidence=0.3)
        assert router.route(sig) is None
