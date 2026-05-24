import pytest
from src.engine.risk import RiskManager, RiskConfig
from src.models import OrderIntent, OrderSide


def make_intent(price: float = 55.0, size: int = 10, market_id: str = "m-001") -> OrderIntent:
    return OrderIntent(
        market_id=market_id,
        side=OrderSide.YES,
        price=price,
        size=size,
        strategy_name="test",
        signal_id="sig-001",
    )


class TestRiskManager:
    def test_normal_order_approved(self):
        rm = RiskManager()
        ok, reason = rm.evaluate(make_intent())
        assert ok is True
        assert reason == "approved"

    def test_size_too_large(self):
        rm = RiskManager(RiskConfig(max_order_size=5))
        ok, reason = rm.evaluate(make_intent(size=10))
        assert ok is False
        assert "size" in reason

    def test_price_too_high(self):
        rm = RiskManager(RiskConfig(max_price_cents=80.0))
        ok, reason = rm.evaluate(make_intent(price=85.0))
        assert ok is False
        assert "price" in reason

    def test_price_too_low(self):
        rm = RiskManager(RiskConfig(min_price_cents=15.0))
        ok, reason = rm.evaluate(make_intent(price=5.0))
        assert ok is False

    def test_spread_filter(self):
        rm = RiskManager(RiskConfig(spread_filter=3.0))
        ok, reason = rm.evaluate(make_intent(), spread=8.0)
        assert ok is False
        assert "spread" in reason

    def test_position_limit(self):
        rm = RiskManager(RiskConfig(max_position_per_market=15))
        rm.state.record_fill("m-001", 10)
        ok, reason = rm.evaluate(make_intent(size=10))
        assert ok is False
        assert "position" in reason

    def test_daily_loss_limit(self):
        rm = RiskManager(RiskConfig(max_daily_loss=100.0))
        rm.state.daily_pnl = -150.0
        ok, reason = rm.evaluate(make_intent())
        assert ok is False
        assert "daily loss" in reason
