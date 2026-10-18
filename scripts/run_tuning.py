#!/usr/bin/env python3
"""Run resumable proof-constrained tuning of the discovered finite prefix."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.data import COMPACT_ARRAY_GENERATOR
from core.tasks import stage_tasks
from core.evaluation import EvaluationCostCache
from core.program import GeneratorProgram
from core.tuning import (
    ARTIFACT_SCHEMA_VERSION,
    SOURCE_PROGRAM_HASH,
    TunedCandidate,
    PrefixTuner,
    TuningConfig,
    panel_hash,
)


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def verify_source(source: Path, sizes: tuple[int, ...]) -> None:
    payload = json.loads(source.read_text())
    matches = [
        item for item in payload["candidates"]
        if item.get("program_hash") == SOURCE_PROGRAM_HASH
    ]
    if len(matches) != 1:
        raise ValueError("frozen seed 4 source program is absent or duplicated")
    program = GeneratorProgram.from_dict(matches[0]["program"])
    base = TunedCandidate.base()
    for n in sizes:
        if program.generate(n) != base.generate(n):
            raise ValueError(f"symbolic tuning backbone differs from frozen source at n={n}")


def candidate_payload(search: PrefixTuner, export_limit: int) -> dict[str, object]:
    items = search.candidate_items(export_limit)
    best_hash = search.best_score.candidate_hash
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_type": "tuning_candidates",
        "source_program_hash": SOURCE_PROGRAM_HASH,
        "proof_constraint": "finite prefix only; exact alpha and A/B geometric tail frozen",
        "train_best_candidate_hash": best_hash,
        "candidates": [
            {
                "candidate_hash": candidate.candidate_hash,
                "selection_roles": ["train_best"] if candidate.candidate_hash == best_hash else [],
                "candidate": candidate.to_dict(),
                "score": asdict(score),
            }
            for candidate, score in items
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=Path("result/final-smoke"))
    parser.add_argument("--manifest", type=Path, default=Path("data/experiment_manifest.json"))
    parser.add_argument("--source", type=Path, default=Path("result/discovery/selected-programs.json"))
    parser.add_argument("--stage", default="search")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--population", type=int, default=10)
    parser.add_argument("--elite-parents", type=int, default=3)
    parser.add_argument("--children-per-parent", type=int, default=2)
    parser.add_argument("--random-fraction", type=float, default=0.25)
    parser.add_argument("--initial-jitter", type=float, default=0.18)
    parser.add_argument("--minimum-jitter", type=float, default=0.015)
    parser.add_argument("--prefix-terms", type=int, default=8)
    parser.add_argument("--points", type=int)
    parser.add_argument("--distributions", nargs="+")
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--export-limit", type=int, default=32)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    section = manifest[args.stage]
    points = args.points if args.points is not None else int(section["points"])
    distributions = tuple(args.distributions or section["distributions"])
    tasks = tuple(stage_tasks(args.manifest, args.stage, distributions, points=points))
    sizes = tuple(sorted({task.n for task in tasks}))
    verify_source(args.source, sizes)

    args.run_dir.mkdir(parents=True, exist_ok=True)
    cache_path = args.cache or args.run_dir / "cost.sqlite"
    config = {
        key: str(value) if isinstance(value, Path) else value
        for key, value in vars(args).items()
    }
    config.update({
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "array_generator": COMPACT_ARRAY_GENERATOR,
        "sizes": list(sizes),
        "task_seeds": sorted({task.seed for task in tasks}),
        "panel_hash": panel_hash(tasks),
        "source_program_hash": SOURCE_PROGRAM_HASH,
    })
    atomic_json(args.run_dir / "config.json", config)

    search_config = TuningConfig(
        args.population,
        args.elite_parents,
        args.children_per_parent,
        args.random_fraction,
        args.initial_jitter,
        args.minimum_jitter,
    )
    checkpoint_path = args.run_dir / "checkpoint.json"
    metrics_path = args.run_dir / "metrics.json"
    candidates_path = args.run_dir / "candidates.json"
    metrics: list[dict[str, object]] = []
    with EvaluationCostCache(cache_path) as cache:
        search = PrefixTuner(
            tasks, cache, args.seed, args.prefix_terms, search_config
        )
        if args.resume and checkpoint_path.exists():
            search.load_state_dict(json.loads(checkpoint_path.read_text()))
            if metrics_path.exists():
                metrics = json.loads(metrics_path.read_text())
                metrics = [item for item in metrics if int(item["iteration"]) <= search.iteration]
            print(f"Resuming tuning from iteration {search.iteration}", flush=True)
        while search.iteration < args.iterations:
            record = search.step()
            metrics.append(record)
            atomic_json(checkpoint_path, search.state_dict())
            atomic_json(metrics_path, metrics)
            atomic_json(candidates_path, candidate_payload(search, args.export_limit))
            print(json.dumps(record), flush=True)
        if not search.scores:
            search.initialize()
        atomic_json(checkpoint_path, search.state_dict())
        atomic_json(candidates_path, candidate_payload(search, args.export_limit))
        print(json.dumps({
            "status": "complete",
            "stage": args.stage,
            "iterations": search.iteration,
            "evaluated_candidates": len(search.scores),
            "best_candidate_hash": search.best_score.candidate_hash,
            "best_prefix": list(search.best_candidate.prefix),
            "cache_hits": cache.hits,
            "cache_misses": cache.misses,
            "output": str(candidates_path),
        }), flush=True)


if __name__ == "__main__":
    main()
