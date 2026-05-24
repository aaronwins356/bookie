from __future__ import annotations

"""
Train/test and walk-forward split utilities for replay bundles.

The purpose is honesty, not convenience: never tune on the same games used
to evaluate. These helpers operate on lists of bundle paths (or in-memory
bundles) and produce disjoint train/test partitions. They are pure and
deterministic, so the logic is testable even with tiny sample data.
"""

from dataclasses import dataclass
from typing import Generic, List, Sequence, Tuple, TypeVar

T = TypeVar("T")


@dataclass
class Split(Generic[T]):
    train: List[T]
    test: List[T]


def split_by_fraction(items: Sequence[T], train_fraction: float = 0.7) -> Split[T]:
    """First `train_fraction` go to train (time-ordered if caller pre-sorts)."""
    if not 0.0 < train_fraction < 1.0:
        raise ValueError("train_fraction must be in (0, 1)")
    n = len(items)
    cut = max(1, int(round(n * train_fraction))) if n > 1 else n
    cut = min(cut, n - 1) if n > 1 else n
    return Split(train=list(items[:cut]), test=list(items[cut:]))


def split_by_key(items: Sequence[T], keys: Sequence[str], test_keys: Sequence[str]) -> Split[T]:
    """Partition by an explicit key per item (e.g. event_id)."""
    if len(items) != len(keys):
        raise ValueError("items and keys must be the same length")
    test_set = set(test_keys)
    train, test = [], []
    for item, key in zip(items, keys):
        (test if key in test_set else train).append(item)
    return Split(train=train, test=test)


def kfold(items: Sequence[T], k: int) -> List[Split[T]]:
    """k disjoint folds; each fold is the test set once, rest is train."""
    if k < 2:
        raise ValueError("k must be >= 2")
    n = len(items)
    if k > n:
        raise ValueError(f"k={k} > number of items={n}")
    folds: List[List[T]] = [[] for _ in range(k)]
    for i, item in enumerate(items):
        folds[i % k].append(item)
    splits: List[Split[T]] = []
    for i in range(k):
        test = folds[i]
        train = [x for j, f in enumerate(folds) if j != i for x in f]
        splits.append(Split(train=train, test=test))
    return splits


def walk_forward(items: Sequence[T], train_size: int, test_size: int = 1, step: int = 1) -> List[Split[T]]:
    """
    Expanding-origin walk-forward windows: train on a leading block, test on
    the next `test_size` items, then advance by `step`. Train never includes
    future data relative to its test window.
    """
    if train_size < 1 or test_size < 1 or step < 1:
        raise ValueError("train_size, test_size, step must all be >= 1")
    n = len(items)
    windows: List[Split[T]] = []
    start = 0
    while start + train_size + test_size <= n:
        train = list(items[start:start + train_size])
        test = list(items[start + train_size:start + train_size + test_size])
        windows.append(Split(train=train, test=test))
        start += step
    return windows
