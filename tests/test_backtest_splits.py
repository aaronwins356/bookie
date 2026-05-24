import pytest
from src.backtest import splits


class TestFractionSplit:
    def test_basic(self):
        s = splits.split_by_fraction(list(range(10)), 0.7)
        assert s.train == [0, 1, 2, 3, 4, 5, 6]
        assert s.test == [7, 8, 9]
        assert set(s.train).isdisjoint(s.test)

    def test_invalid_fraction(self):
        with pytest.raises(ValueError):
            splits.split_by_fraction([1, 2, 3], 0.0)
        with pytest.raises(ValueError):
            splits.split_by_fraction([1, 2, 3], 1.0)

    def test_small_input_keeps_test_nonempty(self):
        s = splits.split_by_fraction([1, 2], 0.9)
        assert s.train and s.test


class TestKeySplit:
    def test_partition_by_key(self):
        items = ["g1", "g2", "g3"]
        keys = ["e1", "e2", "e1"]
        s = splits.split_by_key(items, keys, test_keys=["e2"])
        assert s.test == ["g2"]
        assert s.train == ["g1", "g3"]

    def test_length_mismatch(self):
        with pytest.raises(ValueError):
            splits.split_by_key([1, 2], ["a"], ["a"])


class TestKFold:
    def test_folds_disjoint_and_cover(self):
        items = list(range(9))
        folds = splits.kfold(items, 3)
        assert len(folds) == 3
        for f in folds:
            assert set(f.train).isdisjoint(f.test)
        # every item is a test item exactly once
        all_test = [x for f in folds for x in f.test]
        assert sorted(all_test) == items

    def test_invalid_k(self):
        with pytest.raises(ValueError):
            splits.kfold([1, 2, 3], 1)
        with pytest.raises(ValueError):
            splits.kfold([1, 2], 3)


class TestWalkForward:
    def test_windows(self):
        wins = splits.walk_forward(list(range(7)), train_size=3, test_size=2, step=2)
        assert len(wins) == 2
        assert wins[0].train == [0, 1, 2]
        assert wins[0].test == [3, 4]
        # train never overlaps its own test
        for w in wins:
            assert set(w.train).isdisjoint(w.test)

    def test_no_future_leak(self):
        wins = splits.walk_forward(list(range(6)), train_size=2, test_size=1, step=1)
        for w in wins:
            assert max(w.train) < min(w.test)

    def test_invalid_params(self):
        with pytest.raises(ValueError):
            splits.walk_forward([1, 2, 3], train_size=0)
