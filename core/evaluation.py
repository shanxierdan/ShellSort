"""Candidate benchmarking and baseline-normalized scoring."""

from __future__ import annotations

import math
import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable

from .baselines import BASELINES
from .data import Task, make_array
from .generators import GapGenerator, program_id
from .shellsort import OperationLimitExceeded, SortCost, shellsort
from .fast_shellsort import benchmark_shellsort


@dataclass(frozen=True)
class CandidateScore:
    program_id: str
    loss: float
    reward: float
    comparisons: int
    moves: int
    task_count: int
    complexity: tuple[int, int]
    fidelity: str = "full"


class Benchmark:
    def __init__(
        self,
        tasks: Iterable[Task],
        baseline_cache: Path | None = None,
        candidate_budget_ratio: float = 10.0,
    ) -> None:
        self.tasks = tuple(tasks)
        if not self.tasks:
            raise ValueError("benchmark requires at least one task")
        self.baseline_cache = baseline_cache
        self.candidate_budget_ratio = candidate_budget_ratio
        self._baseline_costs = self._compute_baseline_costs()

    @staticmethod
    def _cache_key(task: Task) -> str:
        payload = json.dumps(
            {"version": 1, "n": task.n, "distribution": task.distribution, "seed": task.seed},
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def _cached_baseline(self, task: Task) -> int | None:
        if self.baseline_cache is None:
            return None
        self.baseline_cache.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.baseline_cache, timeout=120)) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS baseline_cost (cache_key TEXT PRIMARY KEY, cost INTEGER NOT NULL)"
            )
            row = connection.execute(
                "SELECT cost FROM baseline_cost WHERE cache_key = ?", (self._cache_key(task),)
            ).fetchone()
            connection.commit()
            return int(row[0]) if row else None

    def _store_baseline(self, task: Task, cost: int) -> None:
        if self.baseline_cache is None:
            return
        with closing(sqlite3.connect(self.baseline_cache, timeout=120)) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS baseline_cost (cache_key TEXT PRIMARY KEY, cost INTEGER NOT NULL)"
            )
            connection.execute(
                "INSERT OR IGNORE INTO baseline_cost(cache_key, cost) VALUES (?, ?)",
                (self._cache_key(task), cost),
            )
            connection.commit()

    def _compute_baseline_costs(self) -> dict[str, int]:
        costs: dict[str, int] = {}
        for task in self.tasks:
            cached = self._cached_baseline(task)
            if cached is not None:
                costs[task.task_id] = cached
                continue
            values = make_array(task)
            best = min(benchmark_shellsort(values, fn(task.n))[1].total for fn in BASELINES.values())
            costs[task.task_id] = max(1, best)
            self._store_baseline(task, costs[task.task_id])
        return costs

    def evaluate(self, generator: GapGenerator) -> CandidateScore:
        losses: list[float] = []
        total = SortCost(0, 0)
        for task in self.tasks:
            values = make_array(task)
            gaps = generator.generate(task.n)
            maximum = max(1, round(self._baseline_costs[task.task_id] * self.candidate_budget_ratio))
            sorted_values, cost = benchmark_shellsort(values, gaps, max_operations=maximum)
            if sorted_values != sorted(values):
                raise AssertionError("Shellsort returned an incorrect result")
            losses.append(math.log((cost.total + 1) / (self._baseline_costs[task.task_id] + 1)))
            total = SortCost(total.comparisons + cost.comparisons, total.moves + cost.moves)
        loss = sum(losses) / len(losses)
        return CandidateScore(
            program_id=program_id(generator),
            loss=loss,
            reward=-loss,
            comparisons=total.comparisons,
            moves=total.moves,
            task_count=len(self.tasks),
            complexity=generator.complexity,
        )


class StagedBenchmark:
    """Promote candidates through increasingly expensive benchmark stages."""

    def __init__(
        self,
        stages: tuple[tuple[str, Benchmark], ...],
        promotion_losses: tuple[float, ...],
    ) -> None:
        if not stages:
            raise ValueError("at least one benchmark stage is required")
        if len(promotion_losses) != len(stages) - 1:
            raise ValueError("one promotion threshold is required between adjacent stages")
        self.stages = stages
        self.promotion_losses = promotion_losses

    def evaluate(self, generator: GapGenerator) -> CandidateScore:
        for index, (name, benchmark) in enumerate(self.stages):
            score = replace(benchmark.evaluate(generator), fidelity=name)
            if index == len(self.stages) - 1 or score.loss > self.promotion_losses[index]:
                return score
        raise AssertionError("unreachable staged evaluation state")
