"""Frozen candidate artifacts and stage-separated task loading."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .data import Task
from .evaluation import CandidateScore
from .generators import GapGenerator, generator_from_dict, program_id


def log_spaced_sizes(minimum: int, maximum: int, points: int) -> tuple[int, ...]:
    if minimum < 2 or maximum < minimum or points < 1:
        raise ValueError("invalid log-space size specification")
    if points == 1 or minimum == maximum:
        return (maximum,)
    ratio = (maximum / minimum) ** (1 / (points - 1))
    return tuple(sorted({round(minimum * ratio**index) for index in range(points)}))


@dataclass(frozen=True)
class FrozenCandidate:
    schema_version: int
    program_id: str
    program: dict[str, object]
    search_score: dict[str, object]

    @classmethod
    def create(cls, generator: GapGenerator, score: CandidateScore) -> "FrozenCandidate":
        return cls(1, program_id(generator), generator.to_dict(), asdict(score))

    def verify(self) -> GapGenerator:
        generator = generator_from_dict(self.program)
        if program_id(generator) != self.program_id:
            raise ValueError("frozen candidate hash mismatch")
        return generator


def save_candidates(path: Path, candidates: list[FrozenCandidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": 1, "candidates": [asdict(item) for item in candidates]}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_candidates(path: Path) -> list[FrozenCandidate]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported candidate schema")
    candidates = [FrozenCandidate(**item) for item in payload["candidates"]]
    for candidate in candidates:
        candidate.verify()
    return candidates


def stage_tasks(
    manifest_path: Path,
    stage: str,
    distributions: tuple[str, ...] = ("random", "reversed", "nearly_sorted", "duplicates", "blocks"),
    allow_final_test: bool = False,
    points: int = 4,
) -> list[Task]:
    if stage == "final_test" and not allow_final_test:
        raise PermissionError("final_test requires explicit allow_final_test=True")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if stage not in manifest:
        raise KeyError(f"unknown discovery stage: {stage}")
    section = manifest[stage]
    minimum = int(section.get("min_n", 32))
    maximum = int(section.get("max_n", minimum * 10))
    seeds = tuple(int(seed) for seed in section["seeds"])
    if points <= 1 or minimum == maximum:
        sizes = (maximum,)
    else:
        sizes = log_spaced_sizes(minimum, maximum, points)
    return [Task(n, distribution, seed) for n in sizes for distribution in distributions for seed in seeds]
