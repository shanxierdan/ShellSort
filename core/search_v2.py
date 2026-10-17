"""Population-based, model-guided search over legal cross-scale sequences."""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass
from typing import Callable

import torch

from model.sequence_model import ACTION_KINDS, GapSequenceNet
from model.training_v2 import V2ReplayBuffer, V2Sample, collate_v2

from .data import Task, make_array
from .evaluation_v2 import AbsoluteBenchmark, FamilyArchive, FamilyScore, SequenceTaskScore
from .sequence import EditAction, GapSequence, SequenceFamily
from .trace import deletion_counterfactuals


@dataclass(frozen=True)
class SearchV2Config:
    population_size: int = 24
    children_per_parent: int = 4
    elite_parents: int = 8
    random_fraction: float = 0.25
    max_gap_factor: float = 3.0
    counterfactual_elites: int = 2


@dataclass(frozen=True)
class SearchIteration:
    iteration: int
    evaluated_families: int
    replay_size: int
    archive_size: int
    best_log_normalized_total: float
    best_comparisons: float
    best_moves: float
    best_passes: float


class PopulationSearchV2:
    def __init__(
        self,
        model: GapSequenceNet,
        benchmark: AbsoluteBenchmark,
        sizes: tuple[int, ...],
        device: torch.device,
        seed: int = 0,
        config: SearchV2Config | None = None,
    ) -> None:
        if {task.n for task in benchmark.tasks} != set(sizes):
            raise ValueError("benchmark tasks must cover exactly the family sizes")
        self.model = model
        self.benchmark = benchmark
        self.sizes = tuple(sorted(sizes))
        self.device = device
        self.rng = random.Random(seed)
        self.config = config or SearchV2Config()
        self.replay = V2ReplayBuffer()
        self.archive = FamilyArchive(benchmark.panel_hash)
        self.population: list[SequenceFamily] = []
        self.scores: dict[str, FamilyScore] = {}
        self.records: dict[str, tuple[SequenceTaskScore, ...]] = {}
        self.evaluations = 0

    def initialize(self) -> None:
        while len(self.population) < self.config.population_size:
            family = SequenceFamily.random(self.sizes, self.rng)
            if family.family_hash not in {x.family_hash for x in self.population}:
                self.population.append(family)
        self._evaluate_many(self.population, actions={})

    def _evaluate_many(
        self,
        families: list[SequenceFamily],
        actions: dict[str, tuple[EditAction, float]],
        record_replay: bool = True,
    ) -> None:
        for family in families:
            if family.family_hash in self.scores:
                continue
            score, records = self.benchmark.evaluate_family(family, include_traces=True)
            self.scores[family.family_hash] = score
            self.records[family.family_hash] = records
            self.archive.add(family, score)
            self.evaluations += 1
            action, improvement = actions.get(family.family_hash, (EditAction("stop"), 0.0))
            samples = []
            for task, record in zip(self.benchmark.tasks, records):
                assert record.trace is not None
                samples.append(V2Sample.from_trace(task.distribution, record.trace, action, improvement))
            if record_replay:
                self.replay.extend(samples)

    @staticmethod
    def _scalar(score: FamilyScore) -> float:
        return score.mean_log_normalized_total + 0.015 * math.log1p(score.objectives[2])

    def _parents(self) -> list[SequenceFamily]:
        ordered = sorted(self.population, key=lambda item: self._scalar(self.scores[item.family_hash]))
        elite = ordered[: min(self.config.elite_parents, len(ordered))]
        archive = [family for family, _ in self.archive.items()]
        combined = {item.family_hash: item for item in elite + archive}
        return list(combined.values())[: self.config.elite_parents]

    @torch.no_grad()
    def _model_action(self, family: SequenceFamily) -> EditAction:
        # Use a real trace from the largest n and first matching task as the
        # state. Search remains valid before the model is useful because a
        # fixed random exploration fraction is always retained.
        largest = family.sequences[-1]
        record = next(
            item for item in self.records[family.family_hash]
            if item.trace is not None and item.trace.n == largest.n
        )
        task = next(task for task in self.benchmark.tasks if task.task_id == record.task_id)
        sample = V2Sample.from_trace(task.distribution, record.trace)  # type: ignore[arg-type]
        batch = collate_v2([sample], self.device)
        self.model.eval()
        output = self.model(batch.features, batch.context, batch.padding_mask)
        kind = ACTION_KINDS[int(torch.distributions.Categorical(logits=output.action_logits[0]).sample())]
        editable = max(1, len(largest.gaps) - 1)
        max_gaps = max(4, math.ceil(self.config.max_gap_factor * math.log2(largest.n + 1)))
        if kind == "insert" and len(largest.gaps) >= max_gaps:
            kind = "move"
        if kind == "delete" and editable <= 1:
            kind = "insert"
        if kind == "insert":
            # Sample around poorly covered intervals as well as globally.
            positions = (1.0,) + largest.log_positions
            intervals = [(positions[i + 1], positions[i]) for i in range(len(positions) - 1)]
            low, high = max(intervals, key=lambda pair: pair[1] - pair[0])
            return EditAction("insert", value=self.rng.uniform(low, high))
        if kind in {"delete", "move"}:
            # A negative deletion delta means removing this gap reduced exact
            # work. Prefer gaps whose predicted marginal contribution is low.
            marginal = output.contribution[0, :editable].sum(dim=-1)
            index = int(torch.distributions.Categorical(logits=-marginal).sample())
            return EditAction(kind, index=index, value=self.rng.gauss(0, 0.05))
        if kind == "rescale":
            start = self.rng.randrange(editable)
            return EditAction("rescale", start, math.exp(self.rng.gauss(0, 0.05)), editable)
        return EditAction("stop")

    def _propose(
        self, parents: list[SequenceFamily]
    ) -> tuple[list[SequenceFamily], dict[str, tuple[EditAction, SequenceFamily]]]:
        children: dict[str, SequenceFamily] = {}
        provenance: dict[str, tuple[EditAction, SequenceFamily]] = {}
        for parent in parents:
            parent_score = self._scalar(self.scores[parent.family_hash])
            produced = 0
            attempts = 0
            while produced < self.config.children_per_parent and attempts < 8 * self.config.children_per_parent:
                attempts += 1
                if self.rng.random() < self.config.random_fraction:
                    reference = parent.sequences[-1]
                    action, _ = reference.random_edit(
                        self.rng,
                        max_gaps=max(4, math.ceil(self.config.max_gap_factor * math.log2(reference.n + 1))),
                    )
                else:
                    action = self._model_action(parent)
                if action.kind == "stop":
                    # stop is a useful supervised decision for local rollouts,
                    # but population search still needs alternative children.
                    reference = parent.sequences[-1]
                    action, _ = reference.random_edit(self.rng)
                    if action.kind == "stop":
                        action = EditAction("insert", value=self.rng.uniform(0.01, 0.995))
                child = parent.edit(action)
                if child.family_hash == parent.family_hash or child.family_hash in children:
                    continue
                children[child.family_hash] = child
                # Improvement is filled after exact evaluation.
                provenance[child.family_hash] = (action, parent)
                produced += 1
        return list(children.values()), provenance

    def _add_counterfactual_labels(self) -> None:
        for family, _ in self.archive.items()[: self.config.counterfactual_elites]:
            task = self.benchmark.tasks[0]
            sequence = family.for_n(task.n)
            record = next(x for x in self.records[family.family_hash] if x.task_id == task.task_id)
            assert record.trace is not None
            counterfactuals = deletion_counterfactuals(make_array(task), sequence)
            self.replay.extend([
                V2Sample.from_trace(task.distribution, record.trace, counterfactuals=counterfactuals)
            ])

    def step(self, iteration: int, train_callback: Callable[[V2ReplayBuffer], None]) -> SearchIteration:
        if not self.population:
            self.initialize()
        train_callback(self.replay)
        parents = self._parents()
        children, provenance = self._propose(parents)
        before = self.evaluations
        self._evaluate_many(children, actions={})
        # Replace replay action labels with positive-improvement examples. The
        # absolute-cost samples already inserted remain useful cost supervision.
        improved_samples: list[V2Sample] = []
        for child in children:
            action, parent = provenance[child.family_hash]
            parent_scalar = self._scalar(self.scores[parent.family_hash])
            improvement = parent_scalar - self._scalar(self.scores[child.family_hash])
            if improvement <= 0:
                continue
            for task, record in zip(self.benchmark.tasks, self.records[parent.family_hash]):
                assert record.trace is not None
                improved_samples.append(
                    V2Sample.from_trace(task.distribution, record.trace, action, improvement)
                )
        self.replay.extend(improved_samples)
        candidates = parents + children
        self.population = sorted(
            {x.family_hash: x for x in candidates}.values(),
            key=lambda item: self._scalar(self.scores[item.family_hash]),
        )[: self.config.population_size]
        self._add_counterfactual_labels()
        best = self.population[0]
        score = self.scores[best.family_hash]
        return SearchIteration(
            iteration,
            self.evaluations - before,
            len(self.replay),
            len(self.archive.items()),
            score.mean_log_normalized_total,
            *score.objectives,
        )

    def state_dict(self) -> dict[str, object]:
        return {
            "schema_version": 2,
            "rng_state": self.rng.getstate(),
            "population": [[sequence.to_dict() for sequence in family.sequences] for family in self.population],
            "archive": [
                [sequence.to_dict() for sequence in family.sequences]
                for family, _ in self.archive.items()
            ],
            "scores": {key: asdict(value) for key, value in self.scores.items()},
            "replay": self.replay.state_dict(),
            "evaluations": self.evaluations,
        }

    def load_state_dict(self, payload: dict[str, object]) -> None:
        if int(payload.get("schema_version", 0)) != 2:
            raise ValueError("search state is not V2")
        self.rng.setstate(payload["rng_state"])  # type: ignore[arg-type]
        self.population = [
            SequenceFamily(tuple(
                GapSequence.from_dict(item)
                for item in family
            ))
            for family in payload["population"]  # type: ignore[union-attr]
        ]
        archived = [
            SequenceFamily(tuple(GapSequence.from_dict(item) for item in family))
            for family in payload.get("archive", [])  # type: ignore[union-attr]
        ]
        self.replay.load_state_dict(payload["replay"])  # type: ignore[arg-type]
        # Exact counts are normally SQLite cache hits. Re-evaluation restores
        # traces needed by the edit model and reconstructs the common-panel archive.
        self.scores.clear()
        self.records.clear()
        self.archive = FamilyArchive(self.benchmark.panel_hash)
        previous_evaluations = int(payload.get("evaluations", 0))
        self.evaluations = 0
        self._evaluate_many(
            list({x.family_hash: x for x in self.population + archived}.values()),
            actions={},
            record_replay=False,
        )
        self.evaluations = previous_evaluations
