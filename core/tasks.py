"""Task-panel construction for search, validation, and final evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from .data import Task


def log_spaced_sizes(minimum: int, maximum: int, points: int) -> tuple[int, ...]:
    if minimum < 2 or maximum < minimum or points < 1:
        raise ValueError("invalid log-space size specification")
    if points == 1 or minimum == maximum:
        return (maximum,)
    ratio = (maximum / minimum) ** (1 / (points - 1))
    return tuple(sorted({round(minimum * ratio**index) for index in range(points)}))


def stage_tasks(
    manifest_path: Path,
    stage: str,
    distributions: tuple[str, ...] = (
        "random",
        "reversed",
        "nearly_sorted",
        "duplicates",
        "blocks",
    ),
    allow_test: bool = False,
    points: int = 4,
) -> list[Task]:
    if stage == "test" and not allow_test:
        raise PermissionError("test requires explicit allow_test=True")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if stage not in manifest:
        raise KeyError(f"unknown stage: {stage}")
    section = manifest[stage]
    minimum = int(section.get("min_n", 32))
    maximum = int(section.get("max_n", minimum * 10))
    seeds = tuple(int(seed) for seed in section["seeds"])
    sizes = (
        (maximum,)
        if points <= 1 or minimum == maximum
        else log_spaced_sizes(minimum, maximum, points)
    )
    return [
        Task(n, distribution, seed)
        for n in sizes
        for distribution in distributions
        for seed in seeds
    ]
