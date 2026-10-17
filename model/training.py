"""Replay storage, batching, joint loss and versioned checkpoints."""

from __future__ import annotations

import random
import os
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
from torch import Tensor
from torch.nn import functional as F

from core.grammar import PRODUCTIONS, SearchState

from .network import ModelOutput, PolicyValueFeasibilityNet


@dataclass(frozen=True)
class ReplaySample:
    tokens: tuple[int, ...]
    policy: tuple[float, ...]
    value: float
    feasibility: float
    legal_actions: tuple[int, ...]

    @classmethod
    def from_state(
        cls,
        state: SearchState,
        policy: list[float],
        value: float,
        feasibility: float,
    ) -> "ReplaySample":
        return cls(state.token_ids(), tuple(policy), value, feasibility, state.legal_actions())


class ReplayBuffer:
    def __init__(self, capacity: int = 100_000) -> None:
        self.capacity = capacity
        self.samples: list[ReplaySample] = []

    def extend(self, samples: list[ReplaySample]) -> None:
        self.samples.extend(samples)
        if len(self.samples) > self.capacity:
            del self.samples[: len(self.samples) - self.capacity]

    def sample(self, batch_size: int, rng: random.Random) -> list[ReplaySample]:
        return rng.sample(self.samples, min(batch_size, len(self.samples)))

    def __len__(self) -> int:
        return len(self.samples)


@dataclass
class Batch:
    tokens: Tensor
    padding_mask: Tensor
    policy: Tensor
    value: Tensor
    feasibility: Tensor
    legal_mask: Tensor


def collate(samples: list[ReplaySample], device: torch.device) -> Batch:
    if not samples:
        raise ValueError("cannot collate an empty batch")
    length = max(len(sample.tokens) for sample in samples)
    tokens = torch.zeros((len(samples), length), dtype=torch.long)
    padding = torch.ones((len(samples), length), dtype=torch.bool)
    legal = torch.zeros((len(samples), len(PRODUCTIONS)), dtype=torch.bool)
    for row, sample in enumerate(samples):
        tokens[row, : len(sample.tokens)] = torch.tensor(sample.tokens)
        padding[row, : len(sample.tokens)] = False
        legal[row, list(sample.legal_actions)] = True
    return Batch(
        tokens=tokens.to(device),
        padding_mask=padding.to(device),
        policy=torch.tensor([sample.policy for sample in samples], dtype=torch.float32, device=device),
        value=torch.tensor([sample.value for sample in samples], dtype=torch.float32, device=device),
        feasibility=torch.tensor(
            [sample.feasibility for sample in samples], dtype=torch.float32, device=device
        ),
        legal_mask=legal.to(device),
    )


def joint_loss(
    output: ModelOutput,
    batch: Batch,
    feasibility_weight: float = 1.0,
    entropy_weight: float = 0.01,
) -> tuple[Tensor, dict[str, float]]:
    logits = output.policy_logits.masked_fill(~batch.legal_mask, -1e9)
    log_probabilities = F.log_softmax(logits, dim=-1)
    policy_loss = -(batch.policy * log_probabilities).sum(dim=-1).mean()
    value_loss = F.mse_loss(output.value, batch.value)
    feasibility_loss = F.binary_cross_entropy_with_logits(
        output.feasibility_logit, batch.feasibility
    )
    probabilities = log_probabilities.exp()
    entropy = -(probabilities * log_probabilities).sum(dim=-1).mean()
    loss = policy_loss + value_loss + feasibility_weight * feasibility_loss - entropy_weight * entropy
    metrics = {
        "loss": float(loss.detach().cpu()),
        "policy_loss": float(policy_loss.detach().cpu()),
        "value_loss": float(value_loss.detach().cpu()),
        "feasibility_loss": float(feasibility_loss.detach().cpu()),
        "entropy": float(entropy.detach().cpu()),
    }
    return loss, metrics


def train_step(
    model: PolicyValueFeasibilityNet,
    optimizer: torch.optim.Optimizer,
    batch: Batch,
    gradient_clip: float = 1.0,
) -> dict[str, float]:
    model.train()
    optimizer.zero_grad(set_to_none=True)
    output = model(batch.tokens, batch.padding_mask)
    loss, metrics = joint_loss(output, batch)
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), gradient_clip)
    optimizer.step()
    return metrics


def save_checkpoint(
    path: Path,
    model: PolicyValueFeasibilityNet,
    optimizer: torch.optim.Optimizer | None,
    step: int,
    metadata: dict[str, object] | None = None,
    training_state: dict[str, object] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    previous = path.with_suffix(path.suffix + ".prev")
    torch.save(
        {
            "schema_version": 1,
            "grammar_action_count": len(PRODUCTIONS),
            "step": step,
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict() if optimizer else None,
            "metadata": metadata or {},
            "training_state": training_state or {},
        },
        temporary,
    )
    if path.exists():
        os.replace(path, previous)
    os.replace(temporary, path)


def load_checkpoint(
    path: Path,
    model: PolicyValueFeasibilityNet,
    optimizer: torch.optim.Optimizer | None = None,
) -> dict[str, object]:
    try:
        payload = torch.load(path, map_location="cpu", weights_only=False)
    except (EOFError, RuntimeError):
        previous = path.with_suffix(path.suffix + ".prev")
        if not previous.exists():
            raise
        payload = torch.load(previous, map_location="cpu", weights_only=False)
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported checkpoint schema")
    if payload.get("grammar_action_count") != len(PRODUCTIONS):
        raise ValueError("checkpoint grammar does not match current grammar")
    model.load_state_dict(payload["model"])
    if optimizer is not None and payload.get("optimizer") is not None:
        optimizer.load_state_dict(payload["optimizer"])
    return payload
