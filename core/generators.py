"""Recursive and enumerative generator templates."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Protocol

from .dsl import Expr, evaluate
from .shellsort import validate_gaps


class GapGenerator(Protocol):
    @property
    def complexity(self) -> tuple[int, int]: ...
    def generate(self, n: int) -> tuple[int, ...]: ...
    def to_dict(self) -> dict[str, object]: ...


def program_id(generator: GapGenerator) -> str:
    payload = json.dumps(generator.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def generator_from_dict(payload: dict[str, object]) -> GapGenerator:
    template = payload.get("template")
    if template == "recursive":
        return RecursiveGenerator(
            Expr.from_dict(payload["init"]),  # type: ignore[arg-type]
            Expr.from_dict(payload["next"]),  # type: ignore[arg-type]
        )
    if template == "enumerative":
        return EnumerativeGenerator(
            int(payload["bound_a"]),
            int(payload["bound_b"]),
            Expr.from_dict(payload["element"]),  # type: ignore[arg-type]
            Expr.from_dict(payload["keep"]) if payload.get("keep") else None,  # type: ignore[arg-type]
        )
    raise ValueError(f"unknown generator template: {template}")


@dataclass(frozen=True)
class RecursiveGenerator:
    init: Expr
    next_gap: Expr
    step_factor: int = 4

    @property
    def complexity(self) -> tuple[int, int]:
        return self.init.size + self.next_gap.size, max(self.init.depth, self.next_gap.depth)

    def generate(self, n: int) -> tuple[int, ...]:
        if n <= 1:
            return ()
        maximum_steps = max(2, self.step_factor * math.ceil(math.log2(n + 1)))
        current = math.floor(evaluate(self.init, {"n": n}))
        gaps: list[int] = []
        for index in range(maximum_steps):
            if current <= 1:
                break
            if current >= n or (gaps and current >= gaps[-1]):
                raise ValueError("recursive generator produced an invalid gap")
            gaps.append(current)
            current = math.floor(evaluate(self.next_gap, {"n": n, "h": current, "i": index}))
        if current > 1:
            raise ValueError("recursive generator did not terminate")
        gaps.append(1)
        return validate_gaps(gaps, n)

    def to_dict(self) -> dict[str, object]:
        return {"template": "recursive", "init": self.init.to_dict(), "next": self.next_gap.to_dict()}


@dataclass(frozen=True)
class EnumerativeGenerator:
    bound_a: int
    bound_b: int
    element: Expr
    keep: Expr | None = None
    max_outputs: int = 256

    @property
    def complexity(self) -> tuple[int, int]:
        keep_size = self.keep.size if self.keep else 0
        keep_depth = self.keep.depth if self.keep else 0
        return self.element.size + keep_size + 2, max(self.element.depth, keep_depth) + 1

    def generate(self, n: int) -> tuple[int, ...]:
        if n <= 1:
            return ()
        if not (0 <= self.bound_a <= 64 and 0 <= self.bound_b <= 64):
            raise ValueError("enumeration bounds exceed execution budget")
        values = {1}
        for a in range(self.bound_a + 1):
            for b in range(self.bound_b + 1):
                gap = math.floor(evaluate(self.element, {"n": n, "a": a, "b": b}))
                should_keep = True
                if self.keep is not None:
                    should_keep = bool(
                        evaluate(self.keep, {"n": n, "g": gap, "a": a, "b": b})
                    )
                if should_keep and 1 <= gap < n:
                    values.add(gap)
                if len(values) > self.max_outputs:
                    raise ValueError("enumerative generator exceeded output budget")
        return validate_gaps(tuple(sorted(values, reverse=True)), n)

    def to_dict(self) -> dict[str, object]:
        return {
            "template": "enumerative",
            "bound_a": self.bound_a,
            "bound_b": self.bound_b,
            "element": self.element.to_dict(),
            "keep": self.keep.to_dict() if self.keep else None,
        }
