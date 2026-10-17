"""Self-play style policy iteration over grammar programs."""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

import torch

from core.evaluation import Benchmark, CandidateScore
from core.grammar import PRODUCTIONS, SearchState
from core.mcts import PUCTSearch
from core.search import ParetoArchive, SemanticCache
from core.generators import GapGenerator
from core.shellsort import OperationLimitExceeded

from .agent import NeuralStateEvaluator, resolve_device
from .network import PolicyValueFeasibilityNet
from .training import ReplayBuffer, ReplaySample, collate, train_step


@dataclass(frozen=True)
class IterationMetrics:
    episodes: int
    valid_programs: int
    real_evaluations: int
    replay_size: int
    mean_loss: float


class PolicyIteration:
    def __init__(
        self,
        model: PolicyValueFeasibilityNet,
        benchmark: Benchmark,
        device: str = "auto",
        simulations: int = 32,
        max_nodes: int = 20,
        seed: int = 0,
        learning_rate: float = 3e-4,
    ) -> None:
        self.device = resolve_device(device)
        self.model = model.to(self.device)
        self.benchmark = benchmark
        self.simulations = simulations
        self.max_nodes = max_nodes
        self.rng = random.Random(seed)
        self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=learning_rate)
        self.replay = ReplayBuffer()
        self.archive = ParetoArchive()
        self.candidates: dict[str, tuple[GapGenerator, CandidateScore]] = {}
        self.semantic_cache = SemanticCache()

    def set_benchmark(self, benchmark: Benchmark) -> None:
        self.benchmark = benchmark
        # Rewards are task-panel specific, so semantic scores cannot cross panels.
        self.semantic_cache = SemanticCache()

    def state_dict(self) -> dict[str, object]:
        return {
            "replay_samples": self.replay.samples,
            "candidates": self.candidates,
            "archive_scores": list(self.archive._items.values()),
            "rng_state": self.rng.getstate(),
        }

    def load_state_dict(self, state: dict[str, object]) -> None:
        old_samples = list(state.get("replay_samples", []))  # type: ignore[arg-type]
        self.replay.samples = [
            replace(sample, value=max(-1.0, min(1.0, sample.value)))
            for sample in old_samples
        ]
        self.candidates = dict(state.get("candidates", {}))  # type: ignore[arg-type]
        self.archive = ParetoArchive()
        for score in state.get("archive_scores", []):  # type: ignore[union-attr]
            self.archive.add(score)
        if state.get("rng_state") is not None:
            self.rng.setstate(state["rng_state"])  # type: ignore[arg-type]

    def generate_episode(
        self,
        temperature: float = 1.0,
        evaluator: NeuralStateEvaluator | None = None,
    ) -> tuple[list[ReplaySample], bool, int]:
        evaluator = evaluator or NeuralStateEvaluator(self.model, str(self.device))
        search = PUCTSearch(
            self.benchmark,
            evaluator=evaluator,
            simulations=self.simulations,
            seed=self.rng.randrange(2**31),
            cache=self.semantic_cache,
        )
        state = SearchState(max_nodes=self.max_nodes)
        trajectory: list[tuple[SearchState, list[float]]] = []
        while not state.terminal:
            policy = search.policy(state, temperature)
            trajectory.append((state, policy))
            state = state.apply(search.sample_action(policy))
        valid = True
        try:
            generator = state.build()
            score = self.benchmark.evaluate(generator)
            self.archive.add(score)
            self.candidates[score.program_id] = (generator, score)
            value = max(-1.0, min(1.0, score.reward))
        except (ArithmeticError, OperationLimitExceeded, OverflowError, ValueError):
            valid = False
            value = -1.0
        samples = [
            ReplaySample.from_state(partial, policy, value, float(valid))
            for partial, policy in trajectory
        ]
        return samples, valid, search.real_evaluations

    def run_iteration(
        self,
        episodes: int,
        gradient_steps: int,
        batch_size: int = 64,
    ) -> IterationMetrics:
        valid = 0
        evaluations = 0
        # Model weights stay fixed while episodes are collected, so state
        # predictions can be safely shared across all episodes in this iteration.
        evaluator = NeuralStateEvaluator(self.model, str(self.device))
        for _ in range(episodes):
            samples, is_valid, used = self.generate_episode(evaluator=evaluator)
            self.replay.extend(samples)
            valid += int(is_valid)
            evaluations += used
        losses: list[float] = []
        for _ in range(gradient_steps):
            if not self.replay.samples:
                break
            batch = collate(self.replay.sample(batch_size, self.rng), self.device)
            metrics = train_step(self.model, self.optimizer, batch)
            losses.append(metrics["loss"])
        return IterationMetrics(
            episodes=episodes,
            valid_programs=valid,
            real_evaluations=evaluations,
            replay_size=len(self.replay),
            mean_loss=sum(losses) / len(losses) if losses else 0.0,
        )
