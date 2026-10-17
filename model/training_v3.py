"""V3 replay, joint program/behavior batches and atomic checkpoints."""

from __future__ import annotations

import os
import random
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
from torch.nn import functional as F

from core.program_v3 import GeneratorProgram, MUTATION_KINDS

from .program_model_v3 import GeneratorProgramNet, program_token_ids
from .training_v2 import V2Sample, _features, collate_v2


@dataclass(frozen=True)
class V3Sample:
    program: dict[str, object]
    behavior: V2Sample
    mutation_kind: str = "replace_expression"
    improvement: float = 0.0


class V3ReplayBuffer:
    def __init__(self, capacity: int = 200_000) -> None:
        self.capacity = capacity
        self.samples: list[V3Sample] = []

    def extend(self, samples: list[V3Sample]) -> None:
        self.samples.extend(samples)
        if len(self.samples) > self.capacity:
            del self.samples[: len(self.samples) - self.capacity]

    def sample(self, size: int, rng: random.Random) -> list[V3Sample]:
        improved = [x for x in self.samples if x.improvement > 0]
        ordinary = [x for x in self.samples if x.improvement <= 0]
        target = min(size // 2, len(improved))
        result = rng.sample(improved, target)
        result.extend(rng.sample(ordinary, min(size - len(result), len(ordinary))))
        if len(result) < min(size, len(self.samples)):
            remaining = [x for x in self.samples if x not in result]
            result.extend(rng.sample(remaining, min(size - len(result), len(remaining))))
        rng.shuffle(result)
        return result

    def state_dict(self) -> dict[str, object]:
        return {"capacity": self.capacity, "samples": [asdict(x) for x in self.samples]}

    def load_state_dict(self, payload: dict[str, object]) -> None:
        self.capacity = int(payload["capacity"])
        self.samples = []
        for item in payload["samples"]:  # type: ignore[union-attr]
            behavior = V2Sample(**item["behavior"])
            self.samples.append(V3Sample(item["program"], behavior, item["mutation_kind"], item["improvement"]))

    def __len__(self) -> int:
        return len(self.samples)


@dataclass
class V3Batch:
    program_tokens: torch.Tensor
    program_padding: torch.Tensor
    gap_features: torch.Tensor
    gap_padding: torch.Tensor
    context: torch.Tensor
    log_costs: torch.Tensor
    mutations: torch.Tensor
    contributions: torch.Tensor
    contribution_mask: torch.Tensor


def collate_v3(samples: list[V3Sample], device: torch.device) -> V3Batch:
    if not samples:
        raise ValueError("cannot collate empty V3 batch")
    programs = [program_token_ids(GeneratorProgram.from_dict(x.program)) for x in samples]
    length = max(len(x) for x in programs)
    tokens = torch.zeros((len(samples), length), dtype=torch.long)
    padding = torch.ones((len(samples), length), dtype=torch.bool)
    for row, values in enumerate(programs):
        tokens[row, : len(values)] = torch.tensor(values)
        padding[row, : len(values)] = False
    v2 = collate_v2([x.behavior for x in samples], device)
    mutations = torch.tensor([MUTATION_KINDS.index(x.mutation_kind) for x in samples], dtype=torch.long)
    return V3Batch(
        tokens.to(device), padding.to(device), v2.features, v2.padding_mask,
        v2.context, v2.log_costs, mutations.to(device)
        , v2.contributions, v2.contribution_mask
    )


def train_v3_step(model: GeneratorProgramNet, optimizer, batch: V3Batch) -> dict[str, float]:
    model.train()
    optimizer.zero_grad(set_to_none=True)
    output = model(batch.program_tokens, batch.program_padding, batch.gap_features, batch.gap_padding, batch.context)
    cost = F.huber_loss(output.log_costs, batch.log_costs)
    mutation = F.cross_entropy(output.mutation_logits, batch.mutations)
    if batch.contribution_mask.any():
        contribution = F.huber_loss(
            output.contribution[batch.contribution_mask],
            batch.contributions[batch.contribution_mask],
        )
    else:
        contribution = cost.new_zeros(())
    predicted = output.log_costs.sum(dim=-1)
    actual = batch.log_costs.sum(dim=-1)
    if len(predicted) > 1:
        target = (actual[:-1] < actual[1:]).float()
        ranking = F.binary_cross_entropy_with_logits(predicted[1:] - predicted[:-1], target)
    else:
        ranking = cost.new_zeros(())
    loss = cost + 0.5 * ranking + 0.3 * mutation + 0.25 * contribution
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
    optimizer.step()
    return {"loss": float(loss.detach().cpu()), "cost_loss": float(cost.detach().cpu()),
            "ranking_loss": float(ranking.detach().cpu()), "mutation_loss": float(mutation.detach().cpu()),
            "contribution_loss": float(contribution.detach().cpu())}


def save_v3_checkpoint(path: Path, model, optimizer, step: int, state: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    previous = path.with_suffix(path.suffix + ".prev")
    torch.save({"schema_version": 3, "step": step, "model": model.state_dict(),
                "optimizer": optimizer.state_dict(), "training_state": state}, temporary)
    if path.exists():
        os.replace(path, previous)
    os.replace(temporary, path)


def load_v3_checkpoint(path: Path, model, optimizer=None) -> dict[str, object]:
    try:
        payload = torch.load(path, map_location="cpu", weights_only=False)
    except (EOFError, RuntimeError):
        payload = torch.load(path.with_suffix(path.suffix + ".prev"), map_location="cpu", weights_only=False)
    if payload.get("schema_version") != 3:
        raise ValueError("checkpoint is not a V3 generator-program checkpoint")
    model.load_state_dict(payload["model"])
    if optimizer is not None:
        optimizer.load_state_dict(payload["optimizer"])
    return payload
