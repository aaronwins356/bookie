from __future__ import annotations

import pytest

from src.live.orderbook_mapper import OrderbookMapper, RawKalshiBook, _best_bid


class TestRawKalshiBook:
    def test_from_api_response_parses_yes_and_no(self):
        data = {
            "orderbook": {
                "yes": [[60, 10], [59, 5], [58, 20]],
                "no": [[45, 8], [44, 12]],
            }
        }
        book = RawKalshiBook.from_api_response("TICKER", "2025-01-01T00:00:00+00:00", data)
        assert book.ticker == "TICKER"
        assert len(book.yes_bids) == 3
        assert len(book.no_bids) == 2

    def test_yes_bids_sorted_best_first(self):
        data = {"orderbook": {"yes": [[55, 5], [60, 10], [58, 3]], "no": []}}
        book = RawKalshiBook.from_api_response("T", "ts", data)
        prices = [p for p, _ in book.yes_bids]
        assert prices == sorted(prices, reverse=True), "Best bid should be first"
        assert prices[0] == 60

    def test_no_bids_sorted_best_first(self):
        data = {"orderbook": {"yes": [], "no": [[40, 5], [45, 10], [42, 3]]}}
        book = RawKalshiBook.from_api_response("T", "ts", data)
        prices = [p for p, _ in book.no_bids]
        assert prices[0] == 45

    def test_empty_book(self):
        data = {"orderbook": {"yes": [], "no": []}}
        book = RawKalshiBook.from_api_response("T", "ts", data)
        assert book.yes_bids == []
        assert book.no_bids == []

    def test_handles_flat_dict_without_orderbook_key(self):
        data = {"yes": [[50, 10]], "no": [[45, 5]]}
        book = RawKalshiBook.from_api_response("T", "ts", data)
        assert len(book.yes_bids) == 1
        assert len(book.no_bids) == 1


class TestAskDerivation:
    """Core invariant: Kalshi YES/NO asks are derived from opposite-side bids."""

    def _mapper(self):
        return OrderbookMapper()

    def _book(self, yes_bids, no_bids, ticker="TICKER"):
        return RawKalshiBook(
            ticker=ticker,
            timestamp="2025-01-01T00:00:00+00:00",
            yes_bids=yes_bids,
            no_bids=no_bids,
        )

    def test_yes_ask_equals_100_minus_best_no_bid(self):
        """yes_ask = 100 - best_no_bid"""
        book = self._book(yes_bids=[(60, 10)], no_bids=[(35, 5)])
        snap = self._mapper().map_snapshot(book)
        assert snap.yes_ask == pytest.approx(100.0 - 35.0)

    def test_no_ask_equals_100_minus_best_yes_bid(self):
        """no_ask = 100 - best_yes_bid"""
        book = self._book(yes_bids=[(60, 10)], no_bids=[(35, 5)])
        snap = self._mapper().map_snapshot(book)
        assert snap.no_ask == pytest.approx(100.0 - 60.0)

    def test_yes_bid_passthrough(self):
        book = self._book(yes_bids=[(62, 8)], no_bids=[(33, 4)])
        snap = self._mapper().map_snapshot(book)
        assert snap.yes_bid == pytest.approx(62.0)

    def test_no_bid_passthrough(self):
        book = self._book(yes_bids=[(62, 8)], no_bids=[(33, 4)])
        snap = self._mapper().map_snapshot(book)
        assert snap.no_bid == pytest.approx(33.0)

    def test_spread_computation(self):
        """spread = yes_ask - yes_bid"""
        book = self._book(yes_bids=[(60, 10)], no_bids=[(35, 5)])
        snap = self._mapper().map_snapshot(book)
        expected_ask = 100.0 - 35.0   # 65
        expected_bid = 60.0
        assert snap.yes_ask == pytest.approx(expected_ask)
        assert snap.yes_bid == pytest.approx(expected_bid)
        assert snap.spread == pytest.approx(expected_ask - expected_bid)  # 5.0

    def test_empty_no_bids_gives_ask_100(self):
        """When no NO bids exist, yes_ask defaults to 100."""
        book = self._book(yes_bids=[(50, 5)], no_bids=[])
        snap = self._mapper().map_snapshot(book)
        assert snap.yes_ask == pytest.approx(100.0)

    def test_empty_yes_bids_gives_bid_0(self):
        """When no YES bids exist, yes_bid defaults to 0."""
        book = self._book(yes_bids=[], no_bids=[(45, 5)])
        snap = self._mapper().map_snapshot(book)
        assert snap.yes_bid == pytest.approx(0.0)

    def test_fully_empty_book_is_valid(self):
        book = self._book(yes_bids=[], no_bids=[])
        snap = self._mapper().map_snapshot(book)
        assert snap.yes_bid == pytest.approx(0.0)
        assert snap.yes_ask == pytest.approx(100.0)
        assert snap.no_bid == pytest.approx(0.0)
        assert snap.no_ask == pytest.approx(100.0)

    def test_arbitrage_free_condition(self):
        """yes_bid + no_bid should be <= 100 (Kalshi enforces no-arb)."""
        book = self._book(yes_bids=[(55, 10)], no_bids=[(40, 5)])
        snap = self._mapper().map_snapshot(book)
        assert snap.yes_bid + snap.no_bid <= 100.0 + 1e-9

    def test_market_id_preserved(self):
        book = self._book(yes_bids=[(50, 5)], no_bids=[(45, 5)], ticker="MYTEST-TICKER")
        snap = self._mapper().map_snapshot(book)
        assert snap.market_id == "MYTEST-TICKER"

    def test_source_is_kalshi_live(self):
        book = self._book(yes_bids=[(50, 5)], no_bids=[(45, 5)])
        snap = self._mapper().map_snapshot(book)
        assert snap.source == "kalshi_live"

    def test_liquidity_score_range(self):
        book = self._book(
            yes_bids=[(60, 50), (59, 30)],
            no_bids=[(35, 40), (34, 20)],
        )
        snap = self._mapper().map_snapshot(book)
        assert 0.0 <= snap.liquidity_score <= 1.0

    def test_timestamp_preserved(self):
        ts = "2025-05-25T12:00:00+00:00"
        book = RawKalshiBook(ticker="T", timestamp=ts, yes_bids=[(50, 5)], no_bids=[(45, 5)])
        snap = self._mapper().map_snapshot(book)
        assert snap.timestamp == ts


class TestOrderbookMapperOrderbook:
    def test_map_orderbook_derives_asks(self):
        mapper = OrderbookMapper()
        book = RawKalshiBook(
            ticker="T",
            timestamp="ts",
            yes_bids=[(60, 10), (59, 5)],
            no_bids=[(35, 8), (34, 4)],
        )
        ob = mapper.map_orderbook(book)
        assert ob.yes_bids == book.yes_bids
        # yes_asks are derived as 100 - no_bid_price for each no_bid level
        yes_ask_prices = sorted(p for p, _ in ob.yes_asks)
        expected_yes_ask_prices = sorted(100.0 - p for p, _ in book.no_bids)
        assert yes_ask_prices == pytest.approx(expected_yes_ask_prices)

    def test_depth_score_range(self):
        mapper = OrderbookMapper()
        book = RawKalshiBook(
            ticker="T", timestamp="ts",
            yes_bids=[(60, 20)], no_bids=[(35, 15)],
        )
        ob = mapper.map_orderbook(book)
        assert 0.0 <= ob.depth_score <= 1.0
