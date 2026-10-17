"""Naturally valid gap sequences and semantics-preserving edit actions."""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from typing import Literal

from .shellsort import validate_gaps

EditKind = Literal["insert", "delete", "move", "rescale", "stop"]


@dataclass(frozen=True)
class EditAction:
    kind: EditKind
    index: int = -1
    value: float = 0.0
    end: int = -1


@dataclass(frozen=True)
class GapSequence:
    """An immutable valid Shellsort sequence tied to one array size."""

    n: int
    gaps: tuple[int, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "gaps", validate_gaps(self.gaps, self.n))

    @property
    def semantic_hash(self) -> str:
        payload = json.dumps({"schema": 2, "n": self.n, "gaps": self.gaps})
        return hashlib.sha256(payload.encode()).hexdigest()

    @property
    def log_positions(self) -> tuple[float, ...]:
        denominator = math.log(max(2, self.n))
        return tuple(math.log(gap) / denominator if gap > 1 else 0.0 for gap in self.gaps)

    @property
    def ratios(self) -> tuple[float, ...]:
        return tuple(math.log(left / right) for left, right in zip(self.gaps, self.gaps[1:]))

    def to_dict(self) -> dict[str, object]:
        return {"schema_version": 2, "n": self.n, "gaps": list(self.gaps)}

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "GapSequence":
        if int(payload.get("schema_version", 0)) != 2:
            raise ValueError("unsupported gap sequence schema")
        return cls(int(payload["n"]), tuple(int(x) for x in payload["gaps"]))  # type: ignore[arg-type]

    @classmethod
    def from_log_positions(
        cls, n: int, positions: tuple[float, ...] | list[float]
    ) -> "GapSequence":
        if n <= 1:
            return cls(n, ())
        values = {1}
        logarithm = math.log(n)
        for position in positions:
            z = min(1.0, max(0.0, float(position)))
            gap = int(round(math.exp(z * logarithm)))
            if 1 <= gap < n:
                values.add(gap)
        return cls(n, tuple(sorted(values, reverse=True)))

    @classmethod
    def random(
        cls,
        n: int,
        rng: random.Random,
        min_gaps: int = 3,
        max_gaps: int | None = None,
    ) -> "GapSequence":
        if n <= 1:
            return cls(n, ())
        upper = max_gaps or max(min_gaps, math.ceil(2.5 * math.log2(n)))
        target = rng.randint(min_gaps, max(min_gaps, upper))
        # A mixture of a noisy grid and uniform positions covers regular and
        # irregular structures without embedding any historical formula.
        grid = [(index + 1) / target for index in range(target - 1)]
        positions = [
            min(0.995, max(0.01, z + rng.gauss(0.0, 0.18 / target))) for z in grid
        ]
        if rng.random() < 0.5:
            positions = [rng.uniform(0.01, 0.995) for _ in range(target - 1)]
        return cls.from_log_positions(n, positions)

    def edit(self, action: EditAction) -> "GapSequence":
        if self.n <= 1 or action.kind == "stop":
            return self
        positions = list(self.log_positions[:-1])
        if action.kind == "insert":
            positions.append(min(0.995, max(0.005, action.value)))
        elif action.kind == "delete":
            if not positions:
                return self
            if not 0 <= action.index < len(positions):
                raise IndexError("delete index outside gap sequence")
            del positions[action.index]
        elif action.kind == "move":
            if not 0 <= action.index < len(positions):
                raise IndexError("move index outside gap sequence")
            positions[action.index] = min(0.995, max(0.005, positions[action.index] + action.value))
        elif action.kind == "rescale":
            if not positions:
                return self
            start = max(0, action.index)
            end = min(len(positions), action.end if action.end >= 0 else len(positions))
            for index in range(start, end):
                positions[index] = min(0.995, max(0.005, positions[index] * action.value))
        else:  # pragma: no cover - Literal protects normal callers
            raise ValueError(f"unknown edit action: {action.kind}")
        return GapSequence.from_log_positions(self.n, positions)

    def random_edit(self, rng: random.Random, max_gaps: int | None = None) -> tuple[EditAction, "GapSequence"]:
        editable = len(self.gaps) - 1
        kinds: list[EditKind] = ["insert", "move", "rescale", "stop"]
        if editable > 1:
            kinds.append("delete")
        if max_gaps is not None and len(self.gaps) >= max_gaps:
            kinds.remove("insert")
        kind = rng.choice(kinds)
        if kind == "insert":
            action = EditAction(kind, value=rng.uniform(0.01, 0.995))
        elif kind == "delete":
            action = EditAction(kind, index=rng.randrange(editable))
        elif kind == "move":
            action = EditAction(kind, index=rng.randrange(max(1, editable)), value=rng.gauss(0, 0.08))
        elif kind == "rescale":
            start = rng.randrange(max(1, editable))
            end = rng.randint(start + 1, max(start + 1, editable))
            action = EditAction(kind, index=start, end=end, value=math.exp(rng.gauss(0, 0.08)))
        else:
            action = EditAction("stop")
        return action, self.edit(action)


@dataclass(frozen=True)
class SequenceFamily:
    """A candidate across several n values, sharing normalized geometry."""

    sequences: tuple[GapSequence, ...]

    def __post_init__(self) -> None:
        if not self.sequences:
            raise ValueError("sequence family cannot be empty")
        if len({sequence.n for sequence in self.sequences}) != len(self.sequences):
            raise ValueError("sequence family sizes must be unique")

    @property
    def family_hash(self) -> str:
        return hashlib.sha256("|".join(x.semantic_hash for x in self.sequences).encode()).hexdigest()

    def for_n(self, n: int) -> GapSequence:
        for sequence in self.sequences:
            if sequence.n == n:
                return sequence
        raise KeyError(f"family has no sequence for n={n}")

    @classmethod
    def from_positions(cls, sizes: tuple[int, ...], positions: tuple[float, ...]) -> "SequenceFamily":
        return cls(tuple(GapSequence.from_log_positions(n, positions) for n in sizes))

    @classmethod
    def random(cls, sizes: tuple[int, ...], rng: random.Random) -> "SequenceFamily":
        reference = GapSequence.random(max(sizes), rng)
        return cls.from_positions(sizes, reference.log_positions[:-1])

    def edit(self, action: EditAction) -> "SequenceFamily":
        # Apply an edit in normalized coordinates to every n. Integer rounding
        # can yield different lengths, which is a real cross-scale effect.
        reference_count = max(1, len(self.sequences[-1].gaps) - 1)
        edited = []
        for sequence in self.sequences:
            count = max(1, len(sequence.gaps) - 1)
            if action.kind in {"delete", "move", "rescale"}:
                relative = action.index / max(1, reference_count - 1)
                index = min(count - 1, round(relative * max(0, count - 1)))
                end = action.end
                if action.kind == "rescale" and end >= 0:
                    end = min(count, max(index + 1, round(end / reference_count * count)))
                local = EditAction(action.kind, index, action.value, end)
            else:
                local = action
            edited.append(sequence.edit(local))
        return SequenceFamily(tuple(edited))
