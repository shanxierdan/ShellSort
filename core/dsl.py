"""Small typed expression language used by gap-generator templates."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Mapping

EPSILON = 1e-9


def _saturate(value: int | float, bound: float) -> float:
    """Convert a numeric result to a finite float without overflowing first."""
    if isinstance(value, int):
        if value > bound:
            return bound
        if value < -bound:
            return -bound
        return float(value)
    if math.isnan(value):
        raise ValueError("expression produced NaN")
    if value == math.inf:
        return bound
    if value == -math.inf:
        return -bound
    return max(-bound, min(bound, float(value)))


@dataclass(frozen=True)
class Expr:
    op: str
    args: tuple["Expr", ...] = ()
    value: float | str | None = None

    @staticmethod
    def constant(value: float) -> "Expr":
        return Expr("const", value=float(value))

    @staticmethod
    def variable(name: str) -> "Expr":
        return Expr("var", value=name)

    @property
    def size(self) -> int:
        return 1 + sum(arg.size for arg in self.args)

    @property
    def depth(self) -> int:
        return 1 + max((arg.depth for arg in self.args), default=0)

    def to_dict(self) -> dict[str, object]:
        return {"op": self.op, "value": self.value, "args": [arg.to_dict() for arg in self.args]}

    def structural_hash(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def from_dict(payload: Mapping[str, object]) -> "Expr":
        return Expr(
            op=str(payload["op"]),
            value=payload.get("value"),
            args=tuple(Expr.from_dict(item) for item in payload.get("args", [])),  # type: ignore[arg-type]
        )


def evaluate(expr: Expr, env: Mapping[str, float], bound: float = 1e12) -> float:
    if not math.isfinite(bound) or bound <= 0:
        raise ValueError("expression bound must be positive and finite")
    if expr.op == "const":
        result = float(expr.value)
    elif expr.op == "var":
        if expr.value not in env:
            raise ValueError(f"undefined variable: {expr.value}")
        result = float(env[str(expr.value)])
    else:
        values = [evaluate(arg, env, bound) for arg in expr.args]
        if expr.op == "add":
            result = values[0] + values[1]
        elif expr.op == "sub":
            result = values[0] - values[1]
        elif expr.op == "mul":
            result = values[0] * values[1]
        elif expr.op == "div":
            denominator = math.copysign(max(abs(values[1]), EPSILON), values[1] or 1.0)
            result = values[0] / denominator
        elif expr.op == "min":
            result = min(values)
        elif expr.op == "max":
            result = max(values)
        elif expr.op == "sqrt":
            result = math.sqrt(abs(values[0]))
        elif expr.op == "log":
            result = math.log1p(abs(values[0]))
        elif expr.op == "floor":
            result = math.floor(values[0])
        elif expr.op == "ceil":
            result = math.ceil(values[0])
        elif expr.op == "abs":
            result = abs(values[0])
        elif expr.op == "mod":
            denominator = max(1.0, abs(values[1]))
            result = values[0] % denominator
        elif expr.op == "if":
            result = values[1] if bool(values[0]) else values[2]
        elif expr.op == "pow":
            base, exponent = abs(values[0]), max(-64.0, min(64.0, values[1]))
            if not base and exponent <= 0:
                result = 0.0
            elif base and exponent and exponent * math.log(base) > math.log(bound):
                # Avoid constructing a huge Python integer or overflowing a
                # float only to clamp it on the following line.
                result = bound
            else:
                try:
                    result = math.pow(base, exponent)
                except OverflowError:
                    result = bound
        elif expr.op == "lt":
            result = float(values[0] < values[1])
        elif expr.op == "le":
            result = float(values[0] <= values[1])
        elif expr.op == "eq":
            result = float(math.isclose(values[0], values[1]))
        elif expr.op == "and":
            result = float(bool(values[0]) and bool(values[1]))
        elif expr.op == "or":
            result = float(bool(values[0]) or bool(values[1]))
        elif expr.op == "not":
            result = float(not bool(values[0]))
        else:
            raise ValueError(f"unsupported operation: {expr.op}")
    return _saturate(result, bound)
