import pytest
from src.simulation.fill_engine import FillEngine
from src.simulation.orderbook import OrderBook, PriceLevel
from src.simulation.volatility import VolatilityRegime
from src.models import OrderIntent, OrderSide, OrderStatus


def make_intent(size: int = 10, price: float = 55.0) -> OrderIntent:
    return OrderIntent(
        market_id="m-1", side=OrderSide.YES, price=price, size=size,
        strategy_name="test", signal_id="s-1",
    )


class TestFillEngine:
    def test_full_fill(self):
        fe = FillEngine()
        book = OrderBook("m-1")
        book.set_levels(bids=[PriceLevel(54, 100)], asks=[PriceLevel(55, 100)])
        res = fe.fill(make_intent(10), book, VolatilityRegime.CALM)
        assert res.status == OrderStatus.FILLED
        assert res.filled_size == 10

    def test_partial_fill_when_thin(self):
        fe = FillEngine()
        book = OrderBook("m-1")
        book.set_levels(bids=[PriceLevel(54, 5)], asks=[PriceLevel(55, 5)])
        res = fe.fill(make_intent(50), book, VolatilityRegime.CALM)
        assert res.filled_size == 5
        assert "PARTIAL" in res.message

    def test_rejected_when_no_liquidity(self):
        fe = FillEngine()
        book = OrderBook("m-1")
        book.set_levels(bids=[], asks=[])
        res = fe.fill(make_intent(10), book, VolatilityRegime.CALM)
        assert res.status == OrderStatus.REJECTED

    def test_submit_uses_internal_book(self):
        fe = FillEngine()
        fe.current_regime = VolatilityRegime.CALM
        res = fe.submit(make_intent(5))
        assert res.status == OrderStatus.FILLED
        assert res.filled_price is not None

    def test_panic_regime_increases_slippage(self):
        fe = FillEngine()
        book_calm = OrderBook("m-1")
        book_calm.set_levels(bids=[PriceLevel(54, 100)], asks=[PriceLevel(55, 100)])
        calm = fe.fill(make_intent(20), book_calm, VolatilityRegime.CALM)

        book_panic = OrderBook("m-1")
        book_panic.set_levels(bids=[PriceLevel(54, 100)], asks=[PriceLevel(55, 100)])
        panic = fe.fill(make_intent(20), book_panic, VolatilityRegime.PANIC)
        # panic fill price should be further from the 55 ask than calm
        assert abs(panic.filled_price - 55.0) > abs(calm.filled_price - 55.0)
