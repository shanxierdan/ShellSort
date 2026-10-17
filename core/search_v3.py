"""V3 population search over complete executable generator programs."""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass

import torch

from model.program_model_v3 import GeneratorProgramNet
from model.training_v2 import V2Sample
from model.training_v3 import V3ReplayBuffer, V3Sample, collate_v3

from .evaluation_v2 import AbsoluteBenchmark, FamilyScore, SequenceTaskScore
from .program_v3 import GeneratorProgram, MUTATION_KINDS, mutate_program, random_program
from .sequence import GapSequence, SequenceFamily
from .data import make_array
from .trace import deletion_counterfactuals


@dataclass(frozen=True)
class SearchV3Config:
    population_size: int = 32
    elite_parents: int = 8
    children_per_parent: int = 5
    random_fraction: float = 0.30
    complexity_weight: float = 0.001
    novelty_weight: float = 0.02


@dataclass(frozen=True)
class SearchV3Iteration:
    iteration: int
    evaluated_programs: int
    replay_size: int
    archive_size: int
    best_log_normalized_total: float
    best_program_size: int


class ProgramArchive:
    def __init__(self, panel_hash: str) -> None:
        self.panel_hash = panel_hash
        self._items: dict[str, tuple[GeneratorProgram, SequenceFamily, FamilyScore]] = {}

    @staticmethod
    def _objectives(program: GeneratorProgram, score: FamilyScore) -> tuple[float, float, float, int]:
        return (*score.objectives, program.complexity[0])

    @classmethod
    def _dominates(cls, left, right) -> bool:
        a, b = cls._objectives(left[0], left[2]), cls._objectives(right[0], right[2])
        return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))

    def add(self, program: GeneratorProgram, family: SequenceFamily, score: FamilyScore) -> bool:
        if score.panel_hash != self.panel_hash:
            raise ValueError("cannot compare V3 candidates from different panels")
        item = (program, family, score)
        if any(self._dominates(existing, item) for existing in self._items.values()):
            return False
        self._items = {key: value for key, value in self._items.items() if not self._dominates(item, value)}
        self._items[program.program_hash] = item
        return True

    def items(self):
        return sorted(self._items.values(), key=lambda x: self._objectives(x[0], x[2]))


class ProgramSearchV3:
    def __init__(
        self,
        model: GeneratorProgramNet,
        benchmark: AbsoluteBenchmark,
        sizes: tuple[int, ...],
        device: torch.device,
        seed: int = 0,
        config: SearchV3Config | None = None,
    ) -> None:
        self.model = model
        self.benchmark = benchmark
        self.sizes = tuple(sorted(sizes))
        if {task.n for task in benchmark.tasks} != set(self.sizes):
            raise ValueError("V3 benchmark does not match program probe sizes")
        self.device = device
        self.rng = random.Random(seed)
        self.config = config or SearchV3Config()
        self.replay = V3ReplayBuffer()
        self.archive = ProgramArchive(benchmark.panel_hash)
        self.population: list[GeneratorProgram] = []
        self.scores: dict[str, FamilyScore] = {}
        self.families: dict[str, SequenceFamily] = {}
        self.records: dict[str, tuple[SequenceTaskScore, ...]] = {}
        self.semantic_best: dict[str, tuple[int, str]] = {}
        self.evaluations = 0

    def _family(self, program: GeneratorProgram) -> SequenceFamily:
        return SequenceFamily(tuple(GapSequence(n, program.generate(n)) for n in self.sizes))

    def _ranked_semantic_unique(self, programs: list[GeneratorProgram]) -> list[GeneratorProgram]:
        """Return scored programs with one best representative per behavior."""
        representatives: dict[str, GeneratorProgram] = {}
        for program in programs:
            if program.program_hash not in self.scores:
                continue
            semantic = self.families[program.program_hash].family_hash
            current = representatives.get(semantic)
            if current is None or (
                self._scalar(program), program.complexity, program.program_hash
            ) < (
                self._scalar(current), current.complexity, current.program_hash
            ):
                representatives[semantic] = program
        return sorted(representatives.values(), key=lambda x: (self._scalar(x), x.program_hash))

    def _assert_population_consistent(self) -> None:
        missing = [x.program_hash for x in self.population if x.program_hash not in self.scores]
        if missing:
            raise RuntimeError(f"V3 population contains {len(missing)} unscored programs")
        semantics = [self.families[x.program_hash].family_hash for x in self.population]
        if len(semantics) != len(set(semantics)):
            raise RuntimeError("V3 population contains semantic duplicates")

    def initialize(self) -> None:
        attempts = 0
        representatives: dict[str, GeneratorProgram] = {}
        while len(representatives) < self.config.population_size and attempts < 50 * self.config.population_size:
            attempts += 1
            program = random_program(self.rng)
            family = self._family(program)
            semantic = family.family_hash
            existing = representatives.get(semantic)
            if existing is None or (program.complexity, program.program_hash) < (
                existing.complexity, existing.program_hash
            ):
                representatives[semantic] = program
        if not representatives:
            raise RuntimeError("V3 initialization produced no programs")
        evaluated = self._evaluate_many(list(representatives.values()), record_replay=True)
        self.population = self._ranked_semantic_unique(evaluated)[: self.config.population_size]
        self._assert_population_consistent()

    def _evaluate_many(self, programs: list[GeneratorProgram], record_replay: bool) -> list[GeneratorProgram]:
        evaluated: list[GeneratorProgram] = []
        for program in programs:
            if program.program_hash in self.scores:
                evaluated.append(program)
                continue
            family = self._family(program)
            semantic = family.family_hash
            existing = self.semantic_best.get(semantic)
            if existing and existing[1] != program.program_hash and existing[0] <= program.complexity[0]:
                continue
            self.semantic_best[semantic] = (program.complexity[0], program.program_hash)
            score, records = self.benchmark.evaluate_family(family, include_traces=True)
            self.scores[program.program_hash] = score
            self.families[program.program_hash] = family
            self.records[program.program_hash] = records
            self.archive.add(program, family, score)
            self.evaluations += 1
            evaluated.append(program)
            if record_replay:
                samples = []
                for task, record in zip(self.benchmark.tasks, records):
                    assert record.trace is not None
                    behavior = V2Sample.from_trace(task.distribution, record.trace)
                    samples.append(V3Sample(program.to_dict(), behavior))
                self.replay.extend(samples)
        return evaluated

    def _novelty(self, program: GeneratorProgram) -> float:
        family = self.families[program.program_hash]
        fingerprints = {tuple(sequence.gaps) for sequence in family.sequences}
        return len(fingerprints) / len(family.sequences)

    def _scalar(self, program: GeneratorProgram) -> float:
        score = self.scores[program.program_hash]
        return (
            score.mean_log_normalized_total
            + self.config.complexity_weight * program.complexity[0]
            - self.config.novelty_weight * self._novelty(program)
        )

    def _parents(self) -> list[GeneratorProgram]:
        self._assert_population_consistent()
        ordered = sorted(self.population, key=self._scalar)
        archive = [item[0] for item in self.archive.items()]
        combined = {x.program_hash: x for x in ordered[: self.config.elite_parents] + archive}
        return self._ranked_semantic_unique(list(combined.values()))[: self.config.elite_parents]

    @property
    def best_program(self) -> GeneratorProgram:
        self._assert_population_consistent()
        if not self.population:
            raise RuntimeError("V3 search has no population")
        return min(self.population, key=lambda x: (self._scalar(x), x.program_hash))

    def candidate_items(self):
        """Export the Pareto set plus the scalar training winner."""
        items = {item[0].program_hash: item for item in self.archive.items()}
        best = self.best_program
        items[best.program_hash] = (
            best, self.families[best.program_hash], self.scores[best.program_hash]
        )
        return sorted(items.values(), key=lambda x: (x[0].program_hash != best.program_hash, self._scalar(x[0])))

    @torch.no_grad()
    def _mutation_kind(self, program: GeneratorProgram) -> str:
        records = self.records[program.program_hash]
        record = max((x for x in records if x.trace is not None), key=lambda x: x.trace.n)  # type: ignore[union-attr]
        task = next(x for x in self.benchmark.tasks if x.task_id == record.task_id)
        behavior = V2Sample.from_trace(task.distribution, record.trace)  # type: ignore[arg-type]
        batch = collate_v3([V3Sample(program.to_dict(), behavior)], self.device)
        self.model.eval()
        output = self.model(
            batch.program_tokens, batch.program_padding, batch.gap_features,
            batch.gap_padding, batch.context,
        )
        index = int(torch.distributions.Categorical(logits=output.mutation_logits[0]).sample())
        return MUTATION_KINDS[index]

    def _propose(self, parents: list[GeneratorProgram]):
        children: dict[str, GeneratorProgram] = {}
        provenance: dict[str, tuple[str, GeneratorProgram]] = {}
        for parent in parents:
            attempts = produced = 0
            while produced < self.config.children_per_parent and attempts < 10 * self.config.children_per_parent:
                attempts += 1
                kind = self.rng.choice(MUTATION_KINDS) if self.rng.random() < self.config.random_fraction else self._mutation_kind(parent)
                child = mutate_program(parent, kind, self.rng)
                if child.program_hash == parent.program_hash or child.program_hash in children:
                    continue
                family = self._family(child)
                existing = self.semantic_best.get(family.family_hash)
                if existing and existing[0] <= child.complexity[0]:
                    continue
                children[child.program_hash] = child
                provenance[child.program_hash] = (kind, parent)
                produced += 1
        return list(children.values()), provenance

    def step(self, iteration: int, train_callback) -> SearchV3Iteration:
        if not self.population:
            self.initialize()
        train_callback(self.replay)
        parents = self._parents()
        children, provenance = self._propose(parents)
        before = self.evaluations
        evaluated_children = self._evaluate_many(children, record_replay=True)
        improvements: list[V3Sample] = []
        for child in evaluated_children:
            kind, parent = provenance[child.program_hash]
            improvement = self._scalar(parent) - self._scalar(child)
            if improvement <= 0:
                continue
            for task, record in zip(self.benchmark.tasks, self.records[parent.program_hash]):
                assert record.trace is not None
                improvements.append(V3Sample(
                    parent.to_dict(), V2Sample.from_trace(task.distribution, record.trace), kind, improvement
                ))
        self.replay.extend(improvements)
        candidates = parents + evaluated_children
        self.population = self._ranked_semantic_unique(
            list({x.program_hash: x for x in candidates}.values())
        )[: self.config.population_size]
        self._assert_population_consistent()
        # One exact small-task counterfactual per iteration supplies genuine
        # per-gap marginal labels without dominating execution time.
        if self.population:
            program = self.population[0]
            task = self.benchmark.tasks[0]
            sequence = self.families[program.program_hash].for_n(task.n)
            record = next(x for x in self.records[program.program_hash] if x.task_id == task.task_id)
            if record.trace is not None:
                counterfactuals = deletion_counterfactuals(make_array(task), sequence)
                behavior = V2Sample.from_trace(
                    task.distribution, record.trace, counterfactuals=counterfactuals
                )
                self.replay.extend([V3Sample(program.to_dict(), behavior)])
        best = self.best_program
        return SearchV3Iteration(
            iteration, self.evaluations - before, len(self.replay), len(self.archive.items()),
            self.scores[best.program_hash].mean_log_normalized_total, best.complexity[0],
        )

    def state_dict(self) -> dict[str, object]:
        return {
            "schema_version": 3,
            "rng_state": self.rng.getstate(),
            "population": [x.to_dict() for x in self.population],
            "archive": [x[0].to_dict() for x in self.archive.items()],
            "replay": self.replay.state_dict(),
            "evaluations": self.evaluations,
        }

    def load_state_dict(self, payload: dict[str, object]) -> None:
        if payload.get("schema_version") != 3:
            raise ValueError("search state is not V3")
        self.rng.setstate(payload["rng_state"])  # type: ignore[arg-type]
        saved_population = [GeneratorProgram.from_dict(x) for x in payload["population"]]  # type: ignore[arg-type]
        archived = [GeneratorProgram.from_dict(x) for x in payload.get("archive", [])]  # type: ignore[arg-type]
        self.replay.load_state_dict(payload["replay"])  # type: ignore[arg-type]
        self.archive = ProgramArchive(self.benchmark.panel_hash)
        self.scores.clear(); self.families.clear(); self.records.clear(); self.semantic_best.clear()
        old_evaluations = int(payload.get("evaluations", 0)); self.evaluations = 0
        restored = self._evaluate_many(
            list({x.program_hash: x for x in saved_population + archived}.values()), False
        )
        restored_hashes = {x.program_hash for x in restored}
        population = [x for x in saved_population if x.program_hash in restored_hashes]
        if not population:
            population = restored
        self.population = self._ranked_semantic_unique(population)[: self.config.population_size]
        self._assert_population_consistent()
        self.evaluations = old_evaluations
