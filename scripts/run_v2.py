#!/usr/bin/env python3
"""Train and run V2 self-supervised population search."""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch

from core.data import Task
from core.discovery import log_spaced_sizes
from core.evaluation_v2 import AbsoluteBenchmark
from core.generator_v2 import LogPositionGenerator
from core.search_v2 import PopulationSearchV2, SearchV2Config
from model.agent import resolve_device
from model.sequence_model import GapSequenceNet
from model.training_v2 import collate_v2, load_v2_checkpoint, save_v2_checkpoint, train_v2_step


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=Path("result/v2-smoke"))
    parser.add_argument("--device", default="auto")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--population", type=int, default=12)
    parser.add_argument("--elite-parents", type=int, default=4)
    parser.add_argument("--children-per-parent", type=int, default=3)
    parser.add_argument("--random-fraction", type=float, default=0.35)
    parser.add_argument("--gradient-steps", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--hidden-size", type=int, default=128)
    parser.add_argument("--layers", type=int, default=3)
    parser.add_argument("--heads", type=int, default=4)
    parser.add_argument("--min-n", type=int, default=32)
    parser.add_argument("--max-n", type=int, default=4096)
    parser.add_argument("--points", type=int, default=6)
    parser.add_argument("--distributions", nargs="+", default=("random", "reversed"))
    parser.add_argument("--task-seeds", type=int, nargs="+", default=(0,))
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    rng = random.Random(args.seed + 991)
    device = resolve_device(args.device)
    sizes = log_spaced_sizes(args.min_n, args.max_n, args.points)
    tasks = tuple(
        Task(n, distribution, seed)
        for n in sizes
        for distribution in args.distributions
        for seed in args.task_seeds
    )
    benchmark = AbsoluteBenchmark(tasks, cache_path=args.cache)
    model = GapSequenceNet(args.hidden_size, args.layers, args.heads).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    search = PopulationSearchV2(
        model,
        benchmark,
        sizes,
        device,
        args.seed,
        SearchV2Config(
            population_size=args.population,
            children_per_parent=args.children_per_parent,
            elite_parents=args.elite_parents,
            random_fraction=args.random_fraction,
        ),
    )
    args.run_dir.mkdir(parents=True, exist_ok=True)
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()}
    config.update({"schema_version": 2, "resolved_device": str(device), "sizes": sizes,
                   "panel_hash": benchmark.panel_hash})
    atomic_json(args.run_dir / "config.json", config)
    checkpoint = args.run_dir / "checkpoint-v2.pt"
    metrics_path = args.run_dir / "metrics-v2.json"
    metrics: list[dict[str, object]] = []
    start = 0
    if args.resume and checkpoint.exists():
        payload = load_v2_checkpoint(checkpoint, model, optimizer)
        search.load_state_dict(payload["training_state"]["search"])  # type: ignore[index]
        rng.setstate(payload["training_state"]["train_rng_state"])  # type: ignore[index,arg-type]
        start = int(payload["step"])
        if metrics_path.exists():
            metrics = json.loads(metrics_path.read_text())
        print(f"Resuming V2 from iteration {start}", flush=True)

    def train(replay) -> None:
        if len(replay) < 2:
            return
        for _ in range(args.gradient_steps):
            samples = replay.sample(args.batch_size, rng)
            train_v2_step(model, optimizer, collate_v2(samples, device))

    for iteration in range(start, args.iterations):
        record = asdict(search.step(iteration + 1, train))
        metrics.append(record)
        archive = [
            {
                "schema_version": 2,
                "family_hash": family.family_hash,
                "sequences": [sequence.to_dict() for sequence in family.sequences],
                "generator": LogPositionGenerator.from_family(family).to_dict(),
                "generator_hash": LogPositionGenerator.from_family(family).generator_hash,
                "score": asdict(score),
            }
            for family, score in search.archive.items()
        ]
        atomic_json(args.run_dir / "candidates-v2.json", {"schema_version": 2, "candidates": archive})
        atomic_json(metrics_path, metrics)
        save_v2_checkpoint(
            checkpoint,
            model,
            optimizer,
            iteration + 1,
            {"search": search.state_dict(), "train_rng_state": rng.getstate()},
        )
        print(json.dumps(record), flush=True)
    print(json.dumps({"device": str(device), "iterations": metrics,
                      "archive_size": len(search.archive.items())}, indent=2))


if __name__ == "__main__":
    main()
