"""Compact cross-scale generators distilled from V2 sequence families."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from .sequence import GapSequence, SequenceFamily


@dataclass(frozen=True)
class LogPositionGenerator:
    """Generate h_i(n)=round(n**z_i) for learned normalized positions."""

    positions: tuple[float, ...]

    def __post_init__(self) -> None:
        normalized = tuple(sorted({round(float(z), 12) for z in self.positions if 0 < z < 1}, reverse=True))
        object.__setattr__(self, "positions", normalized)
        if not normalized:
            raise ValueError("generator needs at least one non-terminal position")

    def generate(self, n: int) -> tuple[int, ...]:
        return GapSequence.from_log_positions(n, self.positions).gaps

    @property
    def generator_hash(self) -> str:
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {"schema_version": 2, "type": "log_positions", "positions": list(self.positions)}

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "LogPositionGenerator":
        if payload.get("schema_version") != 2 or payload.get("type") != "log_positions":
            raise ValueError("unsupported V2 generator schema")
        return cls(tuple(float(x) for x in payload["positions"]))  # type: ignore[arg-type]

    @classmethod
    def from_family(cls, family: SequenceFamily) -> "LogPositionGenerator":
        # The largest n loses the fewest positions through integer collisions.
        return cls(family.sequences[-1].log_positions[:-1])

    def structural_report(self, sizes: tuple[int, ...]) -> dict[str, object]:
        return {
            "formula": "h_i(n) = round(n ** z_i), retain 1 <= h_i < n, append 1",
            "positions": self.positions,
            "sequences": {str(n): self.generate(n) for n in sizes},
            "gap_counts": {str(n): len(self.generate(n)) for n in sizes},
            "dynamic": len(self.generate(max(sizes) * 10)) >= len(self.generate(max(sizes))),
        }

