import pytest
from src.simulation.queue_model import QueueModel


class TestQueueModel:
    def test_empty_level_fills_immediately(self):
        q = QueueModel(seed=1)
        pos = q.position(level_size=0, our_size=10)
        assert pos.fill_probability == 1.0

    def test_deep_queue_low_probability(self):
        q = QueueModel(seed=1)
        shallow = q.position(level_size=10, our_size=10)
        deep = q.position(level_size=1000, our_size=10)
        assert deep.fill_probability < shallow.fill_probability

    def test_probability_in_range(self):
        q = QueueModel(seed=1)
        for size in (0, 5, 50, 500):
            p = q.position(level_size=size, our_size=10).fill_probability
            assert 0.0 <= p <= 1.0

    def test_did_fill_deterministic(self):
        a = QueueModel(seed=7)
        b = QueueModel(seed=7)
        pos_a = a.position(50, 10)
        pos_b = b.position(50, 10)
        assert a.did_fill(pos_a) == b.did_fill(pos_b)
