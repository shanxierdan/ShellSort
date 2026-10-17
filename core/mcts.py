"""PUCT tree search over typed grammar states."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Protocol

from .evaluation import Benchmark, CandidateScore
from .shellsort import OperationLimitExceeded
from .grammar import PRODUCTIONS, SearchState
from .search import SemanticCache


class StateEvaluator(Protocol):
    def predict(self, state: SearchState) -> tuple[list[float], float, float]:
        """Return action priors, value and feasibility probability."""


class UniformEvaluator:
    def predict(self, state: SearchState) -> tuple[list[float], float, float]:
        return [1.0 / len(PRODUCTIONS)] * len(PRODUCTIONS), 0.0, 1.0

    def predict_many(self, states: list[SearchState]) -> list[tuple[list[float], float, float]]:
        return [self.predict(state) for state in states]


@dataclass
class Edge:
    prior: float
    visits: int = 0
    value_sum: float = 0.0

    @property
    def q(self) -> float:
        return self.value_sum / self.visits if self.visits else 0.0


@dataclass
class Node:
    state: SearchState
    edges: dict[int, Edge] = field(default_factory=dict)
    expanded: bool = False
    root_noise_applied: bool = False


class PUCTSearch:
    def __init__(
        self,
        benchmark: Benchmark,
        evaluator: StateEvaluator | None = None,
        simulations: int = 64,
        c_puct: float = 1.5,
        feasibility_power: float = 0.5,
        invalid_value: float = -1.0,
        dirichlet_alpha: float = 0.3,
        dirichlet_fraction: float = 0.25,
        seed: int = 0,
        cache: SemanticCache | None = None,
    ) -> None:
        self.benchmark = benchmark
        self.evaluator = evaluator or UniformEvaluator()
        self.simulations = simulations
        self.c_puct = c_puct
        self.feasibility_power = feasibility_power
        self.invalid_value = invalid_value
        self.dirichlet_alpha = dirichlet_alpha
        self.dirichlet_fraction = dirichlet_fraction
        self.rng = random.Random(seed)
        self.cache = cache or SemanticCache()
        self.nodes: dict[SearchState, Node] = {}
        self.real_evaluations = 0

    def _terminal_value(self, state: SearchState) -> float:
        try:
            generator = state.build()
            cached = self.cache.get(generator)
            if cached is None:
                cached = self.benchmark.evaluate(generator)
                self.cache.put(generator, cached)
                self.real_evaluations += 1
            return cached.reward
        except (ArithmeticError, OperationLimitExceeded, OverflowError, ValueError):
            return self.invalid_value

    def _expand(self, node: Node) -> float:
        priors, value, feasibility = self.evaluator.predict(node.state)
        legal = node.state.legal_actions()
        if not legal:
            node.expanded = True
            return self.invalid_value
        children = [node.state.apply(action) for action in legal]
        predict_many = getattr(self.evaluator, "predict_many", None)
        if predict_many is None:
            child_feasibility = [1.0] * len(legal)
        else:
            child_feasibility = [prediction[2] for prediction in predict_many(children)]
        weighted = {
            action: max(0.0, priors[action]) * max(1e-9, child_feasibility[index]) ** self.feasibility_power
            for index, action in enumerate(legal)
        }
        total = sum(weighted.values())
        if total <= 0:
            weighted = {action: 1.0 for action in legal}
            total = float(len(legal))
        node.edges = {action: Edge(weight / total) for action, weight in weighted.items()}
        node.expanded = True
        return value

    def _simulate(self, root: Node) -> None:
        node = root
        path: list[Edge] = []
        while True:
            if node.state.terminal:
                value = self._terminal_value(node.state)
                break
            if not node.expanded:
                value = self._expand(node)
                break
            if not node.edges:
                value = self.invalid_value
                break
            total_visits = sum(edge.visits for edge in node.edges.values())
            action, edge = max(
                node.edges.items(),
                key=lambda item: item[1].q
                + self.c_puct * item[1].prior * math.sqrt(total_visits + 1) / (item[1].visits + 1),
            )
            path.append(edge)
            state = node.state.apply(action)
            node = self.nodes.setdefault(state, Node(state))
        for edge in path:
            edge.visits += 1
            edge.value_sum += value

    def policy(self, state: SearchState, temperature: float = 1.0) -> list[float]:
        root = self.nodes.setdefault(state, Node(state))
        if not root.expanded:
            self._simulate(root)
        if root.edges and not root.root_noise_applied and self.dirichlet_fraction > 0:
            noise = [self.rng.gammavariate(self.dirichlet_alpha, 1.0) for _ in root.edges]
            noise_total = sum(noise)
            for (edge, sample) in zip(root.edges.values(), noise):
                fraction = sample / noise_total
                edge.prior = (1 - self.dirichlet_fraction) * edge.prior + self.dirichlet_fraction * fraction
            root.root_noise_applied = True
        for _ in range(max(0, self.simulations - 1)):
            self._simulate(root)
        probabilities = [0.0] * len(PRODUCTIONS)
        if not root.edges:
            return probabilities
        if temperature <= 1e-8:
            best = max(root.edges, key=lambda action: root.edges[action].visits)
            probabilities[best] = 1.0
            return probabilities
        weights = {action: edge.visits ** (1.0 / temperature) for action, edge in root.edges.items()}
        total = sum(weights.values())
        if total == 0:
            total = float(len(weights))
            weights = {action: 1.0 for action in weights}
        for action, weight in weights.items():
            probabilities[action] = weight / total
        return probabilities

    def sample_action(self, policy: list[float]) -> int:
        return self.rng.choices(range(len(policy)), weights=policy, k=1)[0]
