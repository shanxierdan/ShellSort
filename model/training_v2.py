"""Stratified V2 replay, feature construction, multi-task loss and checkpoints."""

from __future__ import annotations

import math
import os
import random
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
from torch import Tensor
from torch.nn import functional as F

from core.sequence import EditAction, GapSequence
from core.trace import Counterfactual, SortTrace

from .sequence_model import ACTION_KINDS, CONTEXT_SIZE, FEATURE_SIZE, GapSequenceNet

DISTRIBUTIONS = ("random", "reversed", "nearly_sorted", "duplicates", "blocks")


@dataclass(frozen=True)
class V2Sample:
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
    ) -> "V2Sample":
        by_index = {item.index: item for item in counterfactuals}
        contributions = tuple(
            (
                float(by_index[index].comparisons_delta),
                float(by_index[index].moves_delta),
            ) if index in by_index else (float("nan"), float("nan"))
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


class V2ReplayBuffer:
    def __init__(self, capacity: int = 200_000) -> None:
        self.capacity = capacity
        self.samples: list[V2Sample] = []

    def extend(self, samples: list[V2Sample]) -> None:
        self.samples.extend(samples)
        if len(self.samples) > self.capacity:
            del self.samples[: len(self.samples) - self.capacity]

    def sample(self, size: int, rng: random.Random) -> list[V2Sample]:
        """Balance improved and ordinary legal samples; invalids never enter."""
        improved = [sample for sample in self.samples if sample.improvement > 0]
        ordinary = [sample for sample in self.samples if sample.improvement <= 0]
        chosen: list[V2Sample] = []
        target = min(size // 2, len(improved))
        chosen.extend(rng.sample(improved, target))
        remaining = min(size - len(chosen), len(ordinary))
        chosen.extend(rng.sample(ordinary, remaining))
        if len(chosen) < min(size, len(self.samples)):
            pool = [x for x in self.samples if x not in chosen]
            chosen.extend(rng.sample(pool, min(size - len(chosen), len(pool))))
        rng.shuffle(chosen)
        return chosen

    def state_dict(self) -> dict[str, object]:
        return {"capacity": self.capacity, "samples": [asdict(x) for x in self.samples]}

    def load_state_dict(self, payload: dict[str, object]) -> None:
        self.capacity = int(payload["capacity"])
        self.samples = [V2Sample(**item) for item in payload["samples"]]  # type: ignore[arg-type]

    def __len__(self) -> int:
        return len(self.samples)


@dataclass
class V2Batch:
    features: Tensor
    context: Tensor
    padding_mask: Tensor
    log_costs: Tensor
    contributions: Tensor
    contribution_mask: Tensor
    actions: Tensor


def _features(sample: V2Sample) -> list[list[float]]:
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


def collate_v2(samples: list[V2Sample], device: torch.device) -> V2Batch:
    if not samples:
        raise ValueError("cannot collate empty V2 batch")
    length = max(len(x.gaps) for x in samples)
    features = torch.zeros((len(samples), length, FEATURE_SIZE), dtype=torch.float32)
    padding = torch.ones((len(samples), length), dtype=torch.bool)
    contribution = torch.zeros((len(samples), length, 2), dtype=torch.float32)
    contribution_mask = torch.zeros((len(samples), length), dtype=torch.bool)
    context = torch.zeros((len(samples), CONTEXT_SIZE), dtype=torch.float32)
    log_costs = torch.zeros((len(samples), 2), dtype=torch.float32)
    actions = torch.zeros(len(samples), dtype=torch.long)
    for row, sample in enumerate(samples):
        values = torch.tensor(_features(sample), dtype=torch.float32)
        features[row, : len(values)] = values
        padding[row, : len(values)] = False
        context[row, 0] = math.log(sample.n) / 20.0
        distribution_index = DISTRIBUTIONS.index(sample.distribution) if sample.distribution in DISTRIBUTIONS else 5
        context[row, 1 + distribution_index] = 1.0
        scale = max(1.0, sample.n * math.log2(sample.n + 1))
        log_costs[row] = torch.tensor(
            [math.log((sample.comparisons + 1) / scale), math.log((sample.moves + 1) / scale)]
        )
        for index, pair in enumerate(sample.contributions):
            if index < length and all(math.isfinite(x) for x in pair):
                contribution[row, index] = torch.tensor(
                    [math.copysign(math.log1p(abs(x)), x) for x in pair]
                )
                contribution_mask[row, index] = True
        actions[row] = ACTION_KINDS.index(sample.action_kind)
    return V2Batch(
        features.to(device), context.to(device), padding.to(device), log_costs.to(device),
        contribution.to(device), contribution_mask.to(device), actions.to(device)
    )


def v2_loss(output, batch: V2Batch) -> tuple[Tensor, dict[str, float]]:
    cost = F.huber_loss(output.log_costs, batch.log_costs)
    if batch.contribution_mask.any():
        contribution = F.huber_loss(
            output.contribution[batch.contribution_mask], batch.contributions[batch.contribution_mask]
        )
    else:
        contribution = cost.new_zeros(())
    action = F.cross_entropy(output.action_logits, batch.actions)
    # Pairwise ranking within a batch is derived directly from exact total cost.
    predicted = output.log_costs.sum(dim=-1)
    actual = batch.log_costs.sum(dim=-1)
    if len(predicted) > 1:
        left, right = predicted[:-1], predicted[1:]
        target = (actual[:-1] < actual[1:]).float()
        ranking = F.binary_cross_entropy_with_logits(right - left, target)
    else:
        ranking = cost.new_zeros(())
    loss = cost + 0.5 * contribution + 0.25 * action + 0.5 * ranking
    return loss, {
        "loss": float(loss.detach().cpu()),
        "cost_loss": float(cost.detach().cpu()),
        "contribution_loss": float(contribution.detach().cpu()),
        "action_loss": float(action.detach().cpu()),
        "ranking_loss": float(ranking.detach().cpu()),
    }


def train_v2_step(model: GapSequenceNet, optimizer, batch: V2Batch) -> dict[str, float]:
    model.train()
    optimizer.zero_grad(set_to_none=True)
    output = model(batch.features, batch.context, batch.padding_mask)
    loss, metrics = v2_loss(output, batch)
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
    optimizer.step()
    return metrics


def save_v2_checkpoint(path: Path, model, optimizer, step: int, state: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    previous = path.with_suffix(path.suffix + ".prev")
    torch.save({"schema_version": 2, "step": step, "model": model.state_dict(),
                "optimizer": optimizer.state_dict(), "training_state": state}, temporary)
    if path.exists():
        os.replace(path, previous)
    os.replace(temporary, path)


def load_v2_checkpoint(path: Path, model, optimizer=None) -> dict[str, object]:
    try:
        payload = torch.load(path, map_location="cpu", weights_only=False)
    except (EOFError, RuntimeError):
        payload = torch.load(path.with_suffix(path.suffix + ".prev"), map_location="cpu", weights_only=False)
    if payload.get("schema_version") != 2:
        raise ValueError("checkpoint is not a V2 sequence-model checkpoint")
    model.load_state_dict(payload["model"])
    if optimizer is not None:
        optimizer.load_state_dict(payload["optimizer"])
    return payload
