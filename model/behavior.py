"""Execution-trace samples and tensor features used by the program model."""

from __future__ import annotations

import math
from dataclasses import dataclass

import torch
from torch import Tensor

from core.sequence import EditAction
from core.trace import Counterfactual, SortTrace

DISTRIBUTIONS = ("random", "reversed", "nearly_sorted", "duplicates", "blocks")
FEATURE_SIZE = 10
CONTEXT_SIZE = 7


@dataclass(frozen=True)
class TraceSample:
    n: int
    distribution: str
    gaps: tuple[int, ...]
    comparisons: int
    moves: int
    pass_comparisons: tuple[int, ...]
    pass_moves: tuple[int, ...]
    contributions: tuple[tuple[float, float], ...] = ()
    action_kind: str = "stop"
    improvement: float = 0.0

    @classmethod
    def from_trace(
        cls,
        distribution: str,
        trace: SortTrace,
        action: EditAction | None = None,
        improvement: float = 0.0,
        counterfactuals: tuple[Counterfactual, ...] = (),
    ) -> "TraceSample":
        by_index = {item.index: item for item in counterfactuals}
        contributions = tuple(
            (
                float(by_index[index].comparisons_delta),
                float(by_index[index].moves_delta),
            )
            if index in by_index
            else (float("nan"), float("nan"))
            for index in range(len(trace.gaps))
        )
        return cls(
            trace.n,
            distribution,
            trace.gaps,
            trace.cost.comparisons,
            trace.cost.moves,
            tuple(item.comparisons for item in trace.passes),
            tuple(item.moves for item in trace.passes),
            contributions,
            action.kind if action else "stop",
            improvement,
        )


@dataclass
class BehaviorBatch:
    features: Tensor
    context: Tensor
    padding_mask: Tensor
    log_costs: Tensor
    contributions: Tensor
    contribution_mask: Tensor


def gap_features(sample: TraceSample) -> list[list[float]]:
    log_n = math.log(max(2, sample.n))
    length = len(sample.gaps)
    output = []
    for index, gap in enumerate(sample.gaps):
        previous = sample.gaps[index - 1] if index else sample.n
        following = sample.gaps[index + 1] if index + 1 < length else 1
        output.append(
            [
                math.log(gap) / log_n if gap > 1 else 0.0,
                math.log(previous / gap),
                math.log(gap / following) if gap > following else 0.0,
                index / max(1, length - 1),
                gap / sample.n,
                length / max(1.0, math.log2(sample.n + 1)),
                math.log1p(sample.pass_comparisons[index]) / log_n,
                math.log1p(sample.pass_moves[index]) / log_n,
                sample.pass_comparisons[index] / max(1, sample.comparisons),
                sample.pass_moves[index] / max(1, sample.moves),
            ]
        )
    return output


def collate_behavior(samples: list[TraceSample], device: torch.device) -> BehaviorBatch:
    if not samples:
        raise ValueError("cannot collate an empty behavior batch")
    length = max(len(sample.gaps) for sample in samples)
    features = torch.zeros((len(samples), length, FEATURE_SIZE), dtype=torch.float32)
    padding = torch.ones((len(samples), length), dtype=torch.bool)
    contributions = torch.zeros((len(samples), length, 2), dtype=torch.float32)
    contribution_mask = torch.zeros((len(samples), length), dtype=torch.bool)
    context = torch.zeros((len(samples), CONTEXT_SIZE), dtype=torch.float32)
    log_costs = torch.zeros((len(samples), 2), dtype=torch.float32)
    for row, sample in enumerate(samples):
        values = torch.tensor(gap_features(sample), dtype=torch.float32)
        features[row, : len(values)] = values
        padding[row, : len(values)] = False
        context[row, 0] = math.log(sample.n) / 20.0
        distribution_index = (
            DISTRIBUTIONS.index(sample.distribution)
            if sample.distribution in DISTRIBUTIONS
            else 5
        )
        context[row, 1 + distribution_index] = 1.0
        scale = max(1.0, sample.n * math.log2(sample.n + 1))
        log_costs[row] = torch.tensor(
            [
                math.log((sample.comparisons + 1) / scale),
                math.log((sample.moves + 1) / scale),
            ]
        )
        for index, pair in enumerate(sample.contributions):
            if index < length and all(math.isfinite(value) for value in pair):
                contributions[row, index] = torch.tensor(
                    [math.copysign(math.log1p(abs(value)), value) for value in pair]
                )
                contribution_mask[row, index] = True
    return BehaviorBatch(
        features.to(device),
        context.to(device),
        padding.to(device),
        log_costs.to(device),
        contributions.to(device),
        contribution_mask.to(device),
    )
