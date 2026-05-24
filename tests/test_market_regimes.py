import pytest
from src.simulation.market_regime import MarketRegime, RegimeInputs, RegimeClassifier


def base_inputs(**overrides) -> RegimeInputs:
    defaults = dict(
        spread=2.0, odds_velocity=0.0, liquidity_depth=600,
        volatility=1.0, time_remaining=1500, score_diff=3,
        order_flow_imbalance=0.0, mid_price=55.0,
    )
    defaults.update(overrides)
    return RegimeInputs(**defaults)


class TestRegimeClassifier:
    def setup_method(self):
        self.clf = RegimeClassifier()

    def test_liquidity_collapse(self):
        r = self.clf.classify(base_inputs(liquidity_depth=50, spread=10.0))
        assert r == MarketRegime.LIQUIDITY_COLLAPSE

    def test_endgame_chaos(self):
        r = self.clf.classify(base_inputs(time_remaining=60, volatility=5.0, score_diff=3))
        assert r == MarketRegime.ENDGAME_CHAOS

    def test_dead_market(self):
        r = self.clf.classify(base_inputs(volatility=0.2, odds_velocity=0.0))
        assert r == MarketRegime.DEAD_MARKET

    def test_panic_buying(self):
        r = self.clf.classify(base_inputs(odds_velocity=0.2, order_flow_imbalance=0.8))
        assert r == MarketRegime.PANIC_BUYING

    def test_panic_selling(self):
        r = self.clf.classify(base_inputs(odds_velocity=-0.2, order_flow_imbalance=-0.8))
        assert r == MarketRegime.PANIC_SELLING

    def test_favorite_euphoria(self):
        r = self.clf.classify(base_inputs(mid_price=85.0, score_diff=14, odds_velocity=0.02))
        assert r == MarketRegime.FAVORITE_EUPHORIA

    def test_trending_up(self):
        r = self.clf.classify(base_inputs(odds_velocity=0.1, order_flow_imbalance=0.2))
        assert r == MarketRegime.TRENDING_UP

    def test_trending_down(self):
        r = self.clf.classify(base_inputs(odds_velocity=-0.1, order_flow_imbalance=-0.2))
        assert r == MarketRegime.TRENDING_DOWN

    def test_calm_default(self):
        r = self.clf.classify(base_inputs())
        assert r == MarketRegime.CALM

    def test_all_regimes_reachable_are_enum(self):
        r = self.clf.classify(base_inputs())
        assert isinstance(r, MarketRegime)
