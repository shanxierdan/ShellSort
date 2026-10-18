"""Proof-compatible finite-prefix tuning for the frozen geometric sequence.

The asymptotic geometric tail is immutable.  A tune candidate may only replace
a fixed number of its smallest positive gaps, which is a finite modification
and therefore leaves the proved asymptotic exponent unchanged.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from fractions import Fraction
from functools import lru_cache
from typing import Iterable

from .data import COMPACT_ARRAY_GENERATOR, Task
from .evaluation import EvaluationCostCache
from .shellsort import validate_gaps

ARTIFACT_SCHEMA_VERSION = 1
SOURCE_PROGRAM_HASH = (
    "f8e20407ede6a625fff7e6fb2c9f093bb026fc0ea8ddd87cea821525891e731c"
)

# Exact symbolic normalization recorded in docs/proof.md.
ALPHA_NUMERATOR = 420_574_650_882_923
ALPHA_DENOMINATOR = 7_668_945_023_518_835
RATIO_NUMERATOR = 582_942_583_375_009
RATIO_DENOMINATOR = 250_000_000_000_000
DEFAULT_PREFIX_TERMS = 8


@lru_cache(maxsize=256)
def geometric_gaps_below(n: int) -> tuple[int, ...]:
    """Return the exact positive symbolic gaps below ``n`` in ascending order."""
    if n <= 1:
        return ()
    value = Fraction(ALPHA_NUMERATOR, ALPHA_DENOMINATOR)
    ratio = Fraction(RATIO_NUMERATOR, RATIO_DENOMINATOR)
    values: list[int] = []
    # The ratio is greater than one, so reaching n proves all later gaps exceed n.
    for _ in range(512):
        gap = value.numerator // value.denominator
        if gap >= n:
            break
        if gap >= 1 and (not values or gap != values[-1]):
            values.append(gap)
        value *= ratio
    else:  # pragma: no cover - unreachable for any physically representable n
        raise RuntimeError("gap generation exhausted its symbolic fuel")
    return tuple(values)


def base_prefix(prefix_terms: int = DEFAULT_PREFIX_TERMS) -> tuple[int, ...]:
    if prefix_terms < 2:
        raise ValueError("tuning needs at least two finite-prefix terms")
    values = geometric_gaps_below(10**100)
    if len(values) <= prefix_terms:
        raise RuntimeError("failed to materialize the frozen geometric prefix")
    return values[:prefix_terms]


@dataclass(frozen=True)
class TunedCandidate:
    """One finite-prefix replacement with the exact frozen geometric tail."""

    prefix: tuple[int, ...]
    prefix_terms: int = DEFAULT_PREFIX_TERMS

    def __post_init__(self) -> None:
        if self.prefix_terms < 2:
            raise ValueError("prefix_terms must be at least two")
        if len(self.prefix) != self.prefix_terms:
            raise ValueError("prefix length does not match prefix_terms")
        if self.prefix[0] != 1:
            raise ValueError("a tuned prefix must start with gap 1")
        if any(left >= right for left, right in zip(self.prefix, self.prefix[1:])):
            raise ValueError("a tuned prefix must be strictly increasing")
        tail_boundary = geometric_gaps_below(10**100)[self.prefix_terms]
        if self.prefix[-1] >= tail_boundary:
            raise ValueError("tuned prefix overlaps the immutable geometric tail")

    @classmethod
    def base(cls, prefix_terms: int = DEFAULT_PREFIX_TERMS) -> "TunedCandidate":
        return cls(base_prefix(prefix_terms), prefix_terms)

    @property
    def candidate_hash(self) -> str:
        encoded = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @property
    def proof_compatibility(self) -> str:
        return "finite_prefix_only_exact_geometric_tail"

    def generate(self, n: int) -> tuple[int, ...]:
        if n <= 1:
            return ()
        geometric = geometric_gaps_below(n)
        tail = geometric[self.prefix_terms :]
        values = tuple(sorted({*self.prefix, *tail, 1}, reverse=True))
        return validate_gaps(tuple(value for value in values if value < n), n)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "type": "finite_prefix",
            "source_program_hash": SOURCE_PROGRAM_HASH,
            "prefix": list(self.prefix),
            "prefix_terms": self.prefix_terms,
            "tail": {
                "alpha_numerator": ALPHA_NUMERATOR,
                "alpha_denominator": ALPHA_DENOMINATOR,
                "ratio_numerator": RATIO_NUMERATOR,
                "ratio_denominator": RATIO_DENOMINATOR,
            },
            "proof_compatibility": self.proof_compatibility,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "TunedCandidate":
        if payload.get("schema_version") != ARTIFACT_SCHEMA_VERSION:
            raise ValueError("unsupported candidate schema")
        if payload.get("type") != "finite_prefix":
            raise ValueError("unsupported candidate type")
        if payload.get("source_program_hash") != SOURCE_PROGRAM_HASH:
            raise ValueError("candidate does not derive from the frozen source program")
        expected_tail = TunedCandidate.base(int(payload["prefix_terms"])).to_dict()["tail"]
        if payload.get("tail") != expected_tail:
            raise ValueError("candidate changes the proof-critical geometric tail")
        return cls(tuple(int(value) for value in payload["prefix"]), int(payload["prefix_terms"]))


@dataclass(frozen=True)
class TuneScore:
    candidate_hash: str
    panel_hash: str
    comparisons: int
    moves: int
    task_count: int
    censored_tasks: int
    mean_log_normalized_total: float

    @property
    def total(self) -> int:
        return self.comparisons + self.moves

    @property
    def selection_key(self) -> tuple[int, float, int, str]:
        return (
            self.censored_tasks,
            self.mean_log_normalized_total,
            self.total,
            self.candidate_hash,
        )


def panel_hash(tasks: Iterable[Task]) -> str:
    task_ids = sorted(task.task_id for task in tasks)
    encoded = json.dumps(task_ids, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def evaluate_candidate(
    candidate: TunedCandidate,
    tasks: tuple[Task, ...],
    cache: EvaluationCostCache,
    *,
    array_generator: str = COMPACT_ARRAY_GENERATOR,
    max_normalized_operations: float = 50.0,
) -> TuneScore:
    comparisons = moves = censored = 0
    log_cost = 0.0
    for task in tasks:
        result = cache.evaluate(
            task,
            candidate.generate(task.n),
            max_normalized_operations=max_normalized_operations,
            array_generator=array_generator,
        )
        comparisons += result.comparisons
        moves += result.moves
        censored += int(result.censored)
        scale = max(1.0, task.n * math.log2(task.n + 1))
        log_cost += math.log((result.total / scale) + 1e-12)
    return TuneScore(
        candidate.candidate_hash,
        panel_hash(tasks),
        comparisons,
        moves,
        len(tasks),
        censored,
        log_cost / len(tasks),
    )


@dataclass(frozen=True)
class TuningConfig:
    population_size: int = 20
    elite_parents: int = 5
    children_per_parent: int = 3
    random_fraction: float = 0.25
    initial_jitter: float = 0.18
    minimum_jitter: float = 0.015


class PrefixTuner:
    """Small, resumable evolutionary optimizer over a proof-safe integer prefix."""

    def __init__(
        self,
        tasks: tuple[Task, ...],
        cache: EvaluationCostCache,
        seed: int,
        prefix_terms: int = DEFAULT_PREFIX_TERMS,
        config: TuningConfig | None = None,
    ) -> None:
        if not tasks:
            raise ValueError("tuning needs a non-empty task panel")
        self.tasks = tasks
        self.cache = cache
        self.rng = random.Random(seed)
        self.prefix_terms = prefix_terms
        self.config = config or TuningConfig()
        self.candidates: dict[str, TunedCandidate] = {}
        self.scores: dict[str, TuneScore] = {}
        self.population: list[str] = []
        self.iteration = 0

    def _jitter(self) -> float:
        return max(
            self.config.minimum_jitter,
            self.config.initial_jitter * (0.88 ** self.iteration),
        )

    def _mutate(self, parent: TunedCandidate, jitter: float | None = None) -> TunedCandidate:
        scale = self._jitter() if jitter is None else jitter
        values = list(parent.prefix)
        index = self.rng.randrange(1, len(values))
        lower = values[index - 1] + 1
        if index + 1 < len(values):
            upper = values[index + 1] - 1
        else:
            upper = geometric_gaps_below(10**100)[parent.prefix_terms] - 1
        radius = max(1, round(values[index] * scale))
        delta = self.rng.randint(-radius, radius)
        if delta == 0:
            delta = self.rng.choice((-1, 1))
        values[index] = min(upper, max(lower, values[index] + delta))
        return TunedCandidate(tuple(values), parent.prefix_terms)

    def _random_local(self) -> TunedCandidate:
        candidate = TunedCandidate.base(self.prefix_terms)
        for _ in range(self.rng.randint(1, max(2, self.prefix_terms - 1))):
            candidate = self._mutate(candidate, self.config.initial_jitter)
        return candidate

    def _evaluate(self, candidate: TunedCandidate) -> None:
        candidate_hash = candidate.candidate_hash
        if candidate_hash in self.scores:
            return
        self.candidates[candidate_hash] = candidate
        self.scores[candidate_hash] = evaluate_candidate(
            candidate, self.tasks, self.cache
        )

    def initialize(self) -> None:
        if self.population:
            return
        proposals = {TunedCandidate.base(self.prefix_terms)}
        attempts = 0
        while len(proposals) < self.config.population_size and attempts < 1000:
            attempts += 1
            proposals.add(self._random_local())
        for candidate in proposals:
            self._evaluate(candidate)
        self.population = [
            score.candidate_hash
            for score in sorted(self.scores.values(), key=lambda item: item.selection_key)
        ][: self.config.population_size]

    def step(self) -> dict[str, object]:
        self.initialize()
        ordered = sorted(self.population, key=lambda key: self.scores[key].selection_key)
        parents = ordered[: self.config.elite_parents]
        proposals = {self.candidates[key] for key in parents}
        for key in parents:
            parent = self.candidates[key]
            for _ in range(self.config.children_per_parent):
                proposals.add(self._mutate(parent))
        random_count = max(1, round(self.config.population_size * self.config.random_fraction))
        for _ in range(random_count):
            proposals.add(self._random_local())
        for candidate in proposals:
            self._evaluate(candidate)
        self.population = [
            score.candidate_hash
            for score in sorted(self.scores.values(), key=lambda item: item.selection_key)
        ][: self.config.population_size]
        self.iteration += 1
        best = self.best_score
        return {
            "iteration": self.iteration,
            "evaluated_candidates": len(self.scores),
            "population_size": len(self.population),
            "jitter": self._jitter(),
            "best_candidate_hash": best.candidate_hash,
            "best_prefix": list(self.best_candidate.prefix),
            "best_mean_log_normalized_total": best.mean_log_normalized_total,
            "best_comparisons": best.comparisons,
            "best_moves": best.moves,
            "best_censored_tasks": best.censored_tasks,
        }

    @property
    def best_score(self) -> TuneScore:
        if not self.scores:
            raise RuntimeError("tuning has not been initialized")
        return min(self.scores.values(), key=lambda item: item.selection_key)

    @property
    def best_candidate(self) -> TunedCandidate:
        return self.candidates[self.best_score.candidate_hash]

    def candidate_items(self, limit: int | None = None) -> list[tuple[TunedCandidate, TuneScore]]:
        scores = sorted(self.scores.values(), key=lambda item: item.selection_key)
        if limit is not None:
            scores = scores[:limit]
        return [(self.candidates[score.candidate_hash], score) for score in scores]

    def state_dict(self) -> dict[str, object]:
        return {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "iteration": self.iteration,
            "prefix_terms": self.prefix_terms,
            "panel_hash": panel_hash(self.tasks),
            "search_config": asdict(self.config),
            "rng_state": self.rng.getstate(),
            "population": self.population,
            "candidates": {
                key: candidate.to_dict() for key, candidate in self.candidates.items()
            },
            "scores": {key: asdict(score) for key, score in self.scores.items()},
        }

    def load_state_dict(self, payload: dict[str, object]) -> None:
        if payload.get("schema_version") != ARTIFACT_SCHEMA_VERSION:
            raise ValueError("unsupported tuning checkpoint schema")
        if payload.get("panel_hash") != panel_hash(self.tasks):
            raise ValueError("tuning checkpoint task panel differs from this run")
        if int(payload["prefix_terms"]) != self.prefix_terms:
            raise ValueError("tuning checkpoint prefix width differs from this run")
        if payload.get("search_config") != asdict(self.config):
            raise ValueError("tuning checkpoint search configuration differs from this run")

        def tuples(value):
            if isinstance(value, list):
                return tuple(tuples(item) for item in value)
            return value

        self.iteration = int(payload["iteration"])
        self.rng.setstate(tuples(payload["rng_state"]))
        self.candidates = {
            key: TunedCandidate.from_dict(item)
            for key, item in payload["candidates"].items()
        }
        self.scores = {
            key: TuneScore(**item) for key, item in payload["scores"].items()
        }
        self.population = [str(key) for key in payload["population"]]
        if any(key not in self.candidates or key not in self.scores for key in self.population):
            raise ValueError("tuning checkpoint population is incomplete")
