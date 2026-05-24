import pytest
from src.simulation.latency import LatencyModel


class TestLatencyModel:
    def test_deterministic_with_seed(self):
        a = LatencyModel(seed=5)
        b = LatencyModel(seed=5)
        assert a.quote_latency_ms() == b.quote_latency_ms()

    def test_latency_non_negative(self):
        m = LatencyModel(base_ms=10, jitter_ms=100, seed=1)
        for _ in range(50):
            assert m.quote_latency_ms() >= 0.0
            assert m.fill_latency_ms() >= 0.0

    def test_fill_slower_than_quote_on_average(self):
        m = LatencyModel(base_ms=100, jitter_ms=0, seed=2)
        # with zero jitter, fill = base*1.5 > quote = base
        assert m.fill_latency_ms() > m.quote_latency_ms()

    def test_stale_detection(self):
        m = LatencyModel(base_ms=50, jitter_ms=0, seed=3)
        assert m.is_snapshot_stale(age_ms=1000) is True
        assert m.is_snapshot_stale(age_ms=1) is False
