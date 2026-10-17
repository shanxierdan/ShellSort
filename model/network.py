"""Compact Transformer encoder with policy, value and feasibility heads."""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor, nn


@dataclass
class ModelOutput:
    policy_logits: Tensor
    value: Tensor
    feasibility_logit: Tensor


class PolicyValueFeasibilityNet(nn.Module):
    def __init__(
        self,
        vocab_size: int,
        action_size: int,
        hidden_size: int = 128,
        layers: int = 3,
        heads: int = 4,
        max_length: int = 256,
    ) -> None:
        super().__init__()
        self.token_embedding = nn.Embedding(vocab_size, hidden_size)
        self.position_embedding = nn.Embedding(max_length, hidden_size)
        block = nn.TransformerEncoderLayer(
            d_model=hidden_size,
            nhead=heads,
            dim_feedforward=4 * hidden_size,
            dropout=0.1,
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(
            block,
            num_layers=layers,
            enable_nested_tensor=False,
        )
        self.policy = nn.Linear(hidden_size, action_size)
        self.value = nn.Linear(hidden_size, 1)
        self.feasibility = nn.Linear(hidden_size, 1)

    def forward(self, tokens: Tensor, padding_mask: Tensor | None = None) -> ModelOutput:
        if tokens.ndim != 2:
            raise ValueError("tokens must have shape [batch, sequence]")
        positions = torch.arange(tokens.shape[1], device=tokens.device).unsqueeze(0)
        hidden = self.token_embedding(tokens) + self.position_embedding(positions)
        encoded = self.encoder(hidden, src_key_padding_mask=padding_mask)
        # The BOS position acts as a learned global readout. It can attend to
        # every grammar token while avoiding sequence-length-dependent mean pooling.
        pooled = encoded[:, 0]
        return ModelOutput(
            policy_logits=self.policy(pooled),
            value=torch.tanh(self.value(pooled)).squeeze(-1),
            feasibility_logit=self.feasibility(pooled).squeeze(-1),
        )
