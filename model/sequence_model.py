"""V2 neural model over realized gap sequences rather than AST tokens."""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor, nn


ACTION_KINDS = ("insert", "delete", "move", "rescale", "stop")
FEATURE_SIZE = 10
CONTEXT_SIZE = 7  # log(n) plus five distributions and unknown


@dataclass
class SequenceModelOutput:
    log_costs: Tensor
    contribution: Tensor
    action_logits: Tensor
    token_action_logits: Tensor
    uncertainty: Tensor


class GapSequenceNet(nn.Module):
    def __init__(
        self,
        hidden_size: int = 128,
        layers: int = 3,
        heads: int = 4,
        feature_size: int = FEATURE_SIZE,
        context_size: int = CONTEXT_SIZE,
    ) -> None:
        super().__init__()
        self.feature_size = feature_size
        self.context_size = context_size
        self.input = nn.Linear(feature_size, hidden_size)
        self.context = nn.Sequential(nn.Linear(context_size, hidden_size), nn.GELU())
        self.cls = nn.Parameter(torch.zeros(1, 1, hidden_size))
        block = nn.TransformerEncoderLayer(
            hidden_size,
            heads,
            4 * hidden_size,
            dropout=0.1,
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(block, layers, enable_nested_tensor=False)
        self.cost = nn.Linear(hidden_size, 2)
        self.uncertainty = nn.Linear(hidden_size, 2)
        self.contribution = nn.Linear(hidden_size, 2)
        self.action = nn.Linear(hidden_size, len(ACTION_KINDS))

    def forward(self, features: Tensor, context: Tensor, padding_mask: Tensor) -> SequenceModelOutput:
        if features.ndim != 3 or features.shape[-1] != self.feature_size:
            raise ValueError("features must have shape [batch, gaps, feature_size]")
        hidden = self.input(features)
        cls = self.cls.expand(features.shape[0], -1, -1) + self.context(context).unsqueeze(1)
        encoded = self.encoder(
            torch.cat((cls, hidden), dim=1),
            src_key_padding_mask=torch.cat(
                (torch.zeros((features.shape[0], 1), dtype=torch.bool, device=features.device), padding_mask),
                dim=1,
            ),
        )
        pooled, tokens = encoded[:, 0], encoded[:, 1:]
        return SequenceModelOutput(
            log_costs=self.cost(pooled),
            contribution=self.contribution(tokens),
            action_logits=self.action(pooled),
            # Contribution is also the token-level edit priority. Keeping the
            # alias in the output preserves a convenient inspection API.
            token_action_logits=-self.contribution(tokens),
            uncertainty=torch.nn.functional.softplus(self.uncertainty(pooled)) + 1e-4,
        )
