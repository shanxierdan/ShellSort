"""Exact, resumable cost cache for frozen V3 evaluation."""

from __future__ import annotations

import sqlite3
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .data import COMPACT_ARRAY_GENERATOR, Task, make_array, make_compact_array
from .fast_shellsort import benchmark_shellsort_cost
from .sequence import GapSequence
from .shellsort import OperationLimitExceeded


@dataclass(frozen=True)
class EvaluationCost:
    comparisons: int
    moves: int
    censored: bool = False

    @property
    def total(self) -> int:
        return self.comparisons + self.moves


class EvaluationCostCache:
    """SQLite WAL cache shared by validation and extrapolation workers."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=120)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA busy_timeout=120000")
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS exact_cost_v3 ("
            "cache_key TEXT PRIMARY KEY, sequence_hash TEXT NOT NULL, task_id TEXT NOT NULL, "
            "comparisons INTEGER NOT NULL, moves INTEGER NOT NULL, censored INTEGER NOT NULL)"
        )
        self.connection.commit()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def _key(sequence: GapSequence, task: Task) -> str:
        return f"exact-v3:{sequence.semantic_hash}:{task.task_id}"

    def evaluate(
        self,
        task: Task,
        gaps: Sequence[int],
        max_normalized_operations: float | None = None,
        array_generator: str = "python_v1",
    ) -> EvaluationCost:
        if array_generator not in {"python_v1", COMPACT_ARRAY_GENERATOR}:
            raise ValueError(f"unknown array generator: {array_generator}")
        sequence = GapSequence(task.n, tuple(gaps))
        budget_key = "exact" if max_normalized_operations is None else f"budget-{max_normalized_operations:g}"
        key = f"{self._key(sequence, task)}:{array_generator}:{budget_key}"
        cached = self.connection.execute(
            "SELECT comparisons, moves, censored FROM exact_cost_v3 WHERE cache_key=?", (key,)
        ).fetchone()
        if cached is not None:
            self.hits += 1
            return EvaluationCost(int(cached[0]), int(cached[1]), bool(cached[2]))

        operation_limit = None
        if max_normalized_operations is not None:
            operation_limit = max(
                1, round(max_normalized_operations * task.n * math.log2(task.n + 1))
            )
        try:
            compact = array_generator == COMPACT_ARRAY_GENERATOR
            values = make_compact_array(task) if compact else make_array(task)
            cost = benchmark_shellsort_cost(
                values,
                sequence.gaps,
                max_operations=operation_limit,
                copy_values=not compact,
            )
            result = EvaluationCost(cost.comparisons, cost.moves)
        except OperationLimitExceeded:
            assert operation_limit is not None
            result = EvaluationCost(operation_limit, operation_limit, True)
        self.connection.execute(
            "INSERT OR IGNORE INTO exact_cost_v3 VALUES (?, ?, ?, ?, ?, ?)",
            (
                key, sequence.semantic_hash, task.task_id,
                result.comparisons, result.moves, int(result.censored),
            ),
        )
        self.connection.commit()
        # A concurrent worker may have inserted the same deterministic value.
        self.misses += 1
        return result

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "EvaluationCostCache":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
