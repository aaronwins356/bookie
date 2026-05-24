import pytest
from src.simulation.orderbook import OrderBook, PriceLevel
from src.models import OrderSide


def make_book() -> OrderBook:
    book = OrderBook(market_id="m-1")
    book.set_levels(
        bids=[PriceLevel(49, 100), PriceLevel(48, 200)],
        asks=[PriceLevel(51, 80), PriceLevel(52, 150)],
    )
    return book


class TestOrderBook:
    def test_top_of_book(self):
        book = make_book()
        assert book.best_bid == 49
        assert book.best_ask == 51
        assert book.mid == 50.0
        assert book.spread == 2.0

    def test_levels_sorted(self):
        book = OrderBook("m")
        book.set_levels(
            bids=[PriceLevel(48, 10), PriceLevel(49, 10)],
            asks=[PriceLevel(52, 10), PriceLevel(51, 10)],
        )
        assert book.yes_bids[0].price == 49   # descending
        assert book.yes_asks[0].price == 51   # ascending

    def test_depth(self):
        book = make_book()
        assert book.depth(OrderSide.YES, levels=2) == 230   # asks 80+150
        assert book.depth(OrderSide.NO, levels=2) == 300    # bids 100+200

    def test_consume_yes_walks_asks(self):
        book = make_book()
        fills = book.consume(OrderSide.YES, 100)
        # 80 @ 51, then 20 @ 52
        assert fills == [(51, 80), (52, 20)]
        assert book.best_ask == 52
        assert book.yes_asks[0].size == 130

    def test_consume_exhausts_liquidity(self):
        book = make_book()
        fills = book.consume(OrderSide.YES, 1000)
        filled = sum(q for _, q in fills)
        assert filled == 230               # only 230 available
        assert book.available(OrderSide.YES) == 0

    def test_consume_no_reports_no_equivalent_price(self):
        book = make_book()
        fills = book.consume(OrderSide.NO, 50)
        # buying NO consumes YES bid at 49 → NO price = 100 - 49 = 51
        assert fills[0][0] == pytest.approx(51.0)
        assert fills[0][1] == 50
