import pytest
from src.simulation.slippage import SlippageModel
from src.simulation.volatility import VolatilityRegime


class TestSlippageModel:
    def test_buy_slips_up(self):
        m = SlippageModel()
        r = m.estimate(50.0, size=10, available_depth=1000, regime=VolatilityRegime.CALM, is_buy=True)
        assert r.realized_price >= r.requested_price
        assert r.slippage_cents >= 0

    def test_sell_slips_down(self):
        m = SlippageModel()
        r = m.estimate(50.0, size=10, available_depth=1000, regime=VolatilityRegime.CALM, is_buy=False)
        assert r.realized_price <= r.requested_price

    def test_panic_worse_than_calm(self):
        m = SlippageModel()
        calm = m.estimate(50.0, 50, 500, VolatilityRegime.CALM)
        panic = m.estimate(50.0, 50, 500, VolatilityRegime.PANIC)
        assert panic.slippage_cents > calm.slippage_cents

    def test_size_sensitivity(self):
        m = SlippageModel()
        small = m.estimate(50.0, 10, 500, VolatilityRegime.CALM)
        large = m.estimate(50.0, 400, 500, VolatilityRegime.CALM)
        assert large.size_penalty > small.size_penalty

    def test_price_clamped(self):
        m = SlippageModel(impact_coeff=100.0)
        r = m.estimate(99.0, 1000, 1, VolatilityRegime.CHAOTIC_ENDGAME, is_buy=True)
        assert 0.0 <= r.realized_price <= 100.0
