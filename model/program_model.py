"""Joint encoder for a generator program, realized gaps, and sort traces."""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor, nn

from core.dsl import Expr
from core.program import GeneratorProgram, MUTATION_KINDS

from .behavior import CONTEXT_SIZE, FEATURE_SIZE

PROGRAM_SYMBOLS = (
    "PAD", "BOS", "INIT", "ASSIGN", "EMIT", "PRED", "NONE",
    "const_neg", "const_small", "const_medium", "const_large",
    "n", "t", "last", "k", "r0", "r1", "r2", "r3",
    "add", "sub", "mul", "div", "mod", "min", "max", "pow",
    "sqrt", "log", "floor", "ceil", "abs", "lt", "le", "eq", "and", "or", "not", "if",
    "fuel_0", "fuel_1", "fuel_2", "fuel_3", "fuel_4",
)
PROGRAM_VOCAB = {symbol: index for index, symbol in enumerate(PROGRAM_SYMBOLS)}


def _expr_tokens(expr: Expr) -> list[int]:
    if expr.op == "const":
        value = float(expr.value)
        bucket = "const_neg" if value < 0 else "const_small" if value < 1 else "const_medium" if value < 8 else "const_large"
        return [PROGRAM_VOCAB[bucket]]
    if expr.op == "var":
        return [PROGRAM_VOCAB.get(str(expr.value), PROGRAM_VOCAB["NONE"])]
    output = [PROGRAM_VOCAB.get(expr.op, PROGRAM_VOCAB["NONE"])]
    for arg in expr.args:
        output.extend(_expr_tokens(arg))
    return output


def program_token_ids(program: GeneratorProgram) -> tuple[int, ...]:
    output = [PROGRAM_VOCAB["BOS"]]
    fuel_bucket = min(4, (program.fuel_base + program.fuel_log) // 4)
    output.append(PROGRAM_VOCAB[f"fuel_{fuel_bucket}"])
    for initializer in program.initializers:
        output.append(PROGRAM_VOCAB["INIT"])
        output.extend(_expr_tokens(initializer))
    for statement in program.body:
        output.append(PROGRAM_VOCAB["ASSIGN" if statement.kind == "assign" else "EMIT"])
        if statement.kind == "assign":
            output.append(PROGRAM_VOCAB[f"r{statement.target}"])
        output.extend(_expr_tokens(statement.expression))
        output.append(PROGRAM_VOCAB["PRED"] if statement.predicate else PROGRAM_VOCAB["NONE"])
        if statement.predicate:
            output.extend(_expr_tokens(statement.predicate))
    return tuple(output[:512])


@dataclass
class ProgramModelOutput:
    mutation_logits: Tensor
    log_costs: Tensor
    contribution: Tensor


class GeneratorProgramNet(nn.Module):
    def __init__(self, hidden_size: int = 128, layers: int = 3, heads: int = 4) -> None:
        super().__init__()
        self.program_embedding = nn.Embedding(len(PROGRAM_SYMBOLS), hidden_size)
        self.program_position = nn.Embedding(512, hidden_size)
        self.behavior_input = nn.Linear(FEATURE_SIZE, hidden_size)
        self.context = nn.Linear(CONTEXT_SIZE, hidden_size)
        program_block = nn.TransformerEncoderLayer(
            hidden_size, heads, 4 * hidden_size, dropout=0.1, batch_first=True, norm_first=True
        )
        behavior_block = nn.TransformerEncoderLayer(
            hidden_size, heads, 4 * hidden_size, dropout=0.1, batch_first=True, norm_first=True
        )
        self.program_encoder = nn.TransformerEncoder(program_block, layers, enable_nested_tensor=False)
        self.behavior_encoder = nn.TransformerEncoder(behavior_block, max(1, layers - 1), enable_nested_tensor=False)
        self.fusion = nn.Sequential(nn.Linear(2 * hidden_size, hidden_size), nn.GELU(), nn.LayerNorm(hidden_size))
        self.mutation = nn.Linear(hidden_size, len(MUTATION_KINDS))
        self.cost = nn.Linear(hidden_size, 2)
        self.contribution = nn.Linear(hidden_size, 2)

    def forward(
        self,
        program_tokens: Tensor,
        program_padding: Tensor,
        gap_features: Tensor,
        gap_padding: Tensor,
        context: Tensor,
    ) -> ProgramModelOutput:
        positions = torch.arange(program_tokens.shape[1], device=program_tokens.device).unsqueeze(0)
        program = self.program_embedding(program_tokens) + self.program_position(positions)
        program = self.program_encoder(program, src_key_padding_mask=program_padding)
        program_pool = program[:, 0]
        behavior = self.behavior_input(gap_features) + self.context(context).unsqueeze(1)
        behavior = self.behavior_encoder(behavior, src_key_padding_mask=gap_padding)
        mask = (~gap_padding).unsqueeze(-1)
        behavior_pool = (behavior * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1)
        fused = self.fusion(torch.cat((program_pool, behavior_pool), dim=-1))
        return ProgramModelOutput(
            self.mutation(fused), self.cost(fused), self.contribution(behavior)
        )

