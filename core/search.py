"""Evaluation cache, Pareto archive and a reproducible random-search baseline."""

from __future__ import annotations

import hashlib
import random
from dataclasses import asdict
from typing import Callable, Iterable

from .dsl import Expr
from .evaluation import Benchmark, CandidateScore
from .generators import GapGenerator


class SemanticCache:
    def __init__(self, probe_sizes: tuple[int, ...] = (32, 64, 128, 256, 512)) -> None:
        self.probe_sizes = probe_sizes
        self._scores: dict[str, CandidateScore] = {}

    def fingerprint(self, generator: GapGenerator) -> str:
        outputs = tuple(generator.generate(n) for n in self.probe_sizes)
        return hashlib.sha256(repr(outputs).encode()).hexdigest()

    def get(self, generator: GapGenerator) -> CandidateScore | None:
        return self._scores.get(self.fingerprint(generator))

    def put(self, generator: GapGenerator, score: CandidateScore) -> None:
        self._scores[self.fingerprint(generator)] = score

    def __len__(self) -> int:
        return len(self._scores)


class ParetoArchive:
    """Minimizes performance loss, AST size and AST depth."""

    def __init__(self) -> None:
        self._items: dict[str, CandidateScore] = {}

    @staticmethod
    def _objectives(score: CandidateScore) -> tuple[float, int, int]:
        return score.loss, score.complexity[0], score.complexity[1]

    @classmethod
    def _dominates(cls, left: CandidateScore, right: CandidateScore) -> bool:
        a, b = cls._objectives(left), cls._objectives(right)
        return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))

    def add(self, score: CandidateScore) -> bool:
        if any(self._dominates(item, score) for item in self._items.values()):
            return False
        self._items = {
            key: item for key, item in self._items.items() if not self._dominates(score, item)
        }
        self._items[score.program_id] = score
        return True

    def records(self) -> list[dict[str, object]]:
        ordered = sorted(self._items.values(), key=self._objectives)
        return [asdict(item) for item in ordered]


def random_expression(rng: random.Random, variables: tuple[str, ...], depth: int) -> Expr:
    if depth <= 1 or rng.random() < 0.35:
        if rng.random() < 0.65:
            return Expr.variable(rng.choice(variables))
        return Expr.constant(rng.choice((0.5, 1, 2, 3, 4)))
    op = rng.choice(("add", "sub", "mul", "div", "min", "max", "floor", "sqrt", "log"))
    arity = 1 if op in {"floor", "sqrt", "log"} else 2
    return Expr(op, tuple(random_expression(rng, variables, depth - 1) for _ in range(arity)))


def random_search(
    factory: Callable[[random.Random], GapGenerator],
    benchmark: Benchmark,
    budget: int,
    seed: int,
) -> tuple[ParetoArchive, int]:
    rng = random.Random(seed)
    cache = SemanticCache()
    archive = ParetoArchive()
    evaluations = 0
    for _ in range(budget):
        generator = factory(rng)
        try:
            score = cache.get(generator)
            if score is None:
                score = benchmark.evaluate(generator)
                cache.put(generator, score)
                evaluations += 1
            archive.add(score)
        except (ArithmeticError, OverflowError, ValueError):
            continue
    return archive, evaluations

