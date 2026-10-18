"""Absolute, baseline-free evaluation for gap sequences."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .data import Task, make_array
from .fast_shellsort import benchmark_shellsort_trace
from .sequence import GapSequence, SequenceFamily
from .shellsort import OperationLimitExceeded
from .trace import PassTrace, SortTrace


@dataclass(frozen=True)
class SequenceTaskScore:
    sequence_hash: str
    task_id: str
    comparisons: int
    moves: int
    passes: int
    normalized_comparisons: float
    normalized_moves: float
    trace: SortTrace | None = None
    censored: bool = False

    @property
    def normalized_total(self) -> float:
        return self.normalized_comparisons + self.normalized_moves


@dataclass(frozen=True)
class FamilyScore:
    family_hash: str
    panel_hash: str
    comparisons: int
    moves: int
    passes: int
    task_count: int
    mean_log_normalized_total: float

    @property
    def objectives(self) -> tuple[float, float, float]:
        denominator = max(1, self.task_count)
        return (
            self.comparisons / denominator,
            self.moves / denominator,
            self.passes / denominator,
        )


def panel_hash(tasks: Iterable[Task]) -> str:
    ids = sorted(task.task_id for task in tasks)
    return hashlib.sha256(json.dumps(ids).encode()).hexdigest()


class AbsoluteBenchmark:
    """Evaluate candidates on a common task panel and cache exact counts."""

    def __init__(
        self,
        tasks: Iterable[Task],
        cache_path: Path | None = None,
        max_normalized_operations: float = 50.0,
    ) -> None:
        self.tasks = tuple(tasks)
        if not self.tasks:
            raise ValueError("benchmark requires at least one task")
        self.panel_hash = panel_hash(self.tasks)
        self.cache_path = cache_path
        self.max_normalized_operations = max_normalized_operations

    @staticmethod
    def _key(sequence: GapSequence, task: Task) -> str:
        return f"sequence:{sequence.semantic_hash}:{task.task_id}"

    def _connection(self):
        if self.cache_path is None:
            return None
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.cache_path, timeout=120)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS sequence_cost ("
            "cache_key TEXT PRIMARY KEY, comparisons INTEGER NOT NULL, "
            "moves INTEGER NOT NULL, passes INTEGER NOT NULL)"
        )
        return connection

    def evaluate_sequence(
        self, sequence: GapSequence, task: Task, include_trace: bool = False
    ) -> SequenceTaskScore:
        if sequence.n != task.n:
            raise ValueError("sequence and task n differ")
        cached = None
        connection = self._connection()
        if connection is not None:
            with closing(connection):
                cached = connection.execute(
                    "SELECT comparisons, moves, passes FROM sequence_cost WHERE cache_key=?",
                    (self._key(sequence, task),),
                ).fetchone()
        trace = None
        censored = False
        if cached is None or include_trace:
            values = make_array(task)
            operation_limit = max(1, round(self.max_normalized_operations * task.n * math.log2(task.n + 1)))
            try:
                sorted_values, trace = benchmark_shellsort_trace(
                    values, sequence.gaps, max_operations=operation_limit
                )
                if sorted_values != sorted(values):
                    raise AssertionError("Shellsort returned an incorrect result")
                comparisons, moves, passes = trace.cost.comparisons, trace.cost.moves, len(trace.passes)
            except OperationLimitExceeded:
                # This is a valid but computationally dominated sequence. A
                # deterministic censored target prevents it consuming the run.
                censored = True
                comparisons = operation_limit
                moves = operation_limit
                passes = len(sequence.gaps)
                trace = SortTrace(
                    task.n,
                    sequence.gaps,
                    tuple(
                        PassTrace(gap, comparisons if index == 0 else 0,
                                  moves if index == 0 else 0, 0, 0)
                        for index, gap in enumerate(sequence.gaps)
                    ),
                )
            if cached is None and not censored and self.cache_path is not None:
                with closing(self._connection()) as connection:
                    connection.execute(
                        "INSERT OR IGNORE INTO sequence_cost VALUES (?, ?, ?, ?)",
                        (self._key(sequence, task), comparisons, moves, passes),
                    )
                    connection.commit()
        else:
            comparisons, moves, passes = map(int, cached)
        scale = max(1.0, task.n * math.log2(task.n + 1))
        return SequenceTaskScore(
            sequence.semantic_hash,
            task.task_id,
            int(comparisons),
            int(moves),
            int(passes),
            comparisons / scale,
            moves / scale,
            trace if include_trace else None,
            censored,
        )

    def evaluate_family(
        self, family: SequenceFamily, include_traces: bool = False
    ) -> tuple[FamilyScore, tuple[SequenceTaskScore, ...]]:
        records = tuple(
            self.evaluate_sequence(family.for_n(task.n), task, include_trace=include_traces)
            for task in self.tasks
        )
        score = FamilyScore(
            family.family_hash,
            self.panel_hash,
            sum(x.comparisons for x in records),
            sum(x.moves for x in records),
            sum(x.passes for x in records),
            len(records),
            sum(math.log(x.normalized_total + 1e-9) for x in records) / len(records),
        )
        return score, records

    @staticmethod
    def score_dict(score: FamilyScore) -> dict[str, object]:
        return asdict(score)


class FamilyArchive:
    """A Pareto archive whose records must share one common panel."""

    def __init__(self, expected_panel_hash: str) -> None:
        self.panel_hash = expected_panel_hash
        self._items: dict[str, tuple[SequenceFamily, FamilyScore]] = {}

    @staticmethod
    def dominates(left: FamilyScore, right: FamilyScore) -> bool:
        a, b = left.objectives, right.objectives
        return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))

    def add(self, family: SequenceFamily, score: FamilyScore) -> bool:
        if score.panel_hash != self.panel_hash:
            raise ValueError("cannot compare scores from different task panels")
        if any(self.dominates(item[1], score) for item in self._items.values()):
            return False
        self._items = {
            key: item for key, item in self._items.items() if not self.dominates(score, item[1])
        }
        self._items[family.family_hash] = (family, score)
        return True

    def items(self) -> list[tuple[SequenceFamily, FamilyScore]]:
        return sorted(self._items.values(), key=lambda item: item[1].objectives)
