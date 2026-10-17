"""Deterministic benchmark task generation from compact manifests."""

from __future__ import annotations

import random
from math import isqrt
from dataclasses import dataclass

try:
    import numpy as np
    from numba import njit

    @njit(cache=True)
    def _apply_swaps(values, left, right):
        for index in range(len(left)):
            i = left[index]
            j = right[index]
            temporary = values[i]
            values[i] = values[j]
            values[j] = temporary

    @njit(cache=True)
    def _fill_shuffled_blocks(values, order, block, n):
        cursor = 0
        for block_index in order:
            start = block_index * block
            stop = min(start + block, n)
            for value in range(start, stop):
                values[cursor] = value
                cursor += 1

    COMPACT_ARRAYS_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised by minimal installations
    np = None
    COMPACT_ARRAYS_AVAILABLE = False


COMPACT_ARRAY_GENERATOR = "numpy_pcg64_v1"


@dataclass(frozen=True)
class Task:
    n: int
    distribution: str
    seed: int

    @property
    def task_id(self) -> str:
        return f"n{self.n}-{self.distribution}-s{self.seed}"


def make_array(task: Task) -> list[int]:
    rng = random.Random(task.seed)
    n = task.n
    if n < 0:
        raise ValueError("n must be non-negative")
    if task.distribution == "random":
        values = list(range(n))
        rng.shuffle(values)
        return values
    if task.distribution == "reversed":
        return list(range(n - 1, -1, -1))
    if task.distribution == "nearly_sorted":
        values = list(range(n))
        for _ in range(max(1, n // 20)):
            if n > 1:
                left, right = rng.randrange(n), rng.randrange(n)
                values[left], values[right] = values[right], values[left]
        return values
    if task.distribution == "duplicates":
        cardinality = max(1, int(n**0.5))
        return [rng.randrange(cardinality) for _ in range(n)]
    if task.distribution == "blocks":
        block = max(1, int(n**0.5))
        chunks = [list(range(start, min(start + block, n))) for start in range(0, n, block)]
        rng.shuffle(chunks)
        return [value for chunk in chunks for value in chunk]
    raise ValueError(f"unknown distribution: {task.distribution}")


def make_compact_array(task: Task):
    """Build a deterministic int64 benchmark array without Python-int storage.

    This generator is versioned separately from make_array. Large frozen
    evaluations use NumPy PCG64 so an n-element input occupies approximately
    8n bytes rather than a multi-gigabyte Python object graph.
    """
    if not COMPACT_ARRAYS_AVAILABLE:
        raise RuntimeError("compact arrays require numpy and numba")
    n = task.n
    if n < 0:
        raise ValueError("n must be non-negative")
    rng = np.random.Generator(np.random.PCG64(task.seed))
    if task.distribution == "random":
        return rng.permutation(n).astype(np.int64, copy=False)
    if task.distribution == "reversed":
        return np.arange(n - 1, -1, -1, dtype=np.int64)
    if task.distribution == "nearly_sorted":
        values = np.arange(n, dtype=np.int64)
        if n > 1:
            remaining = max(1, n // 20)
            # Bound temporary index storage while preserving sequential swaps.
            while remaining:
                count = min(remaining, 1_000_000)
                left = rng.integers(0, n, size=count, dtype=np.int64)
                right = rng.integers(0, n, size=count, dtype=np.int64)
                _apply_swaps(values, left, right)
                remaining -= count
        return values
    if task.distribution == "duplicates":
        cardinality = max(1, isqrt(n))
        return rng.integers(0, cardinality, size=n, dtype=np.int64)
    if task.distribution == "blocks":
        block = max(1, isqrt(n))
        block_count = (n + block - 1) // block
        order = rng.permutation(block_count).astype(np.int64, copy=False)
        values = np.empty(n, dtype=np.int64)
        _fill_shuffled_blocks(values, order, block, n)
        return values
    raise ValueError(f"unknown distribution: {task.distribution}")
