"""Adapters between grammar search states and the PyTorch model."""

from __future__ import annotations

import torch

from core.grammar import PRODUCTIONS, SearchState

from .network import PolicyValueFeasibilityNet


def resolve_device(requested: str = "auto") -> torch.device:
    if requested == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    device = torch.device(requested)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not visible in this runtime")
    return device


class NeuralStateEvaluator:
    def __init__(self, model: PolicyValueFeasibilityNet, device: str = "auto") -> None:
        self.device = resolve_device(device)
        self.model = model.to(self.device).eval()
        self.cache: dict[SearchState, tuple[list[float], float, float]] = {}

    @torch.no_grad()
    def predict(self, state: SearchState) -> tuple[list[float], float, float]:
        cached = self.cache.get(state)
        if cached is not None:
            return cached
        tokens = torch.tensor([state.token_ids()], dtype=torch.long, device=self.device)
        output = self.model(tokens)
        logits = output.policy_logits[0]
        mask = torch.zeros(len(PRODUCTIONS), dtype=torch.bool, device=self.device)
        mask[list(state.legal_actions())] = True
        probabilities = torch.softmax(logits.masked_fill(~mask, -torch.inf), dim=-1)
        result = (
            probabilities.cpu().tolist(),
            float(output.value[0].cpu()),
            float(torch.sigmoid(output.feasibility_logit[0]).cpu()),
        )
        self.cache[state] = result
        return result

    @torch.no_grad()
    def predict_many(self, states: list[SearchState]) -> list[tuple[list[float], float, float]]:
        if not states:
            return []
        missing = list(dict.fromkeys(state for state in states if state not in self.cache))
        if not missing:
            return [self.cache[state] for state in states]
        length = max(len(state.token_ids()) for state in missing)
        tokens = torch.zeros((len(missing), length), dtype=torch.long, device=self.device)
        padding = torch.ones((len(missing), length), dtype=torch.bool, device=self.device)
        for row, state in enumerate(missing):
            ids = torch.tensor(state.token_ids(), dtype=torch.long, device=self.device)
            tokens[row, : len(ids)] = ids
            padding[row, : len(ids)] = False
        output = self.model(tokens, padding)
        for row, state in enumerate(missing):
            mask = torch.zeros(len(PRODUCTIONS), dtype=torch.bool, device=self.device)
            legal = state.legal_actions()
            if legal:
                mask[list(legal)] = True
                probabilities = torch.softmax(
                    output.policy_logits[row].masked_fill(~mask, -torch.inf), dim=-1
                )
            else:
                probabilities = torch.zeros(len(PRODUCTIONS), device=self.device)
            self.cache[state] = (
                probabilities.cpu().tolist(),
                float(output.value[row].cpu()),
                float(torch.sigmoid(output.feasibility_logit[row]).cpu()),
            )
        return [self.cache[state] for state in states]
