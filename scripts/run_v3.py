#!/usr/bin/env python3
"""Run V3 self-supervised search over complete generator programs."""

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
from core.search_v3 import ProgramSearchV3, SearchV3Config
from model.agent import resolve_device
from model.program_model_v3 import GeneratorProgramNet
from model.training_v3 import collate_v3, load_v3_checkpoint, save_v3_checkpoint, train_v3_step


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def candidate_payload(search: ProgramSearchV3) -> dict[str, object]:
    best_hash = search.best_program.program_hash
    pareto_hashes = {item[0].program_hash for item in search.archive.items()}
    candidates = []
    for program, family, score in search.candidate_items():
        roles = []
        if program.program_hash == best_hash:
            roles.append("train_best")
        if program.program_hash in pareto_hashes:
            roles.append("pareto")
        candidates.append({
            "schema_version": 3,
            "program_hash": program.program_hash,
            "selection_roles": roles,
            "program": program.to_dict(),
            "complexity": program.complexity,
            "sequences": [sequence.to_dict() for sequence in family.sequences],
            "score": asdict(score),
        })
    return {
        "schema_version": 3,
        "train_best_program_hash": best_hash,
        "candidates": candidates,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=Path("result/v3-smoke"))
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
    train_rng = random.Random(args.seed + 1907)
    device = resolve_device(args.device)
    sizes = log_spaced_sizes(args.min_n, args.max_n, args.points)
    tasks = tuple(Task(n, distribution, seed) for n in sizes
                  for distribution in args.distributions for seed in args.task_seeds)
    benchmark = AbsoluteBenchmark(tasks, cache_path=args.cache)
    model = GeneratorProgramNet(args.hidden_size, args.layers, args.heads).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    search = ProgramSearchV3(
        model, benchmark, sizes, device, args.seed,
        SearchV3Config(args.population, args.elite_parents, args.children_per_parent, args.random_fraction),
    )
    args.run_dir.mkdir(parents=True, exist_ok=True)
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()}
    config.update({"schema_version": 3, "resolved_device": str(device), "sizes": sizes,
                   "panel_hash": benchmark.panel_hash})
    atomic_json(args.run_dir / "config-v3.json", config)
    checkpoint = args.run_dir / "checkpoint-v3.pt"
    metrics_path = args.run_dir / "metrics-v3.json"
    metrics: list[dict[str, object]] = []
    start = 0
    if args.resume and checkpoint.exists():
        payload = load_v3_checkpoint(checkpoint, model, optimizer)
        search.load_state_dict(payload["training_state"]["search"])  # type: ignore[index]
        train_rng.setstate(payload["training_state"]["train_rng_state"])  # type: ignore[index,arg-type]
        torch_rng_state = payload["training_state"].get("torch_rng_state")  # type: ignore[index,union-attr]
        if torch_rng_state is not None:
            torch.set_rng_state(torch_rng_state)
        cuda_rng_state = payload["training_state"].get("cuda_rng_state_all")  # type: ignore[index,union-attr]
        if cuda_rng_state is not None and torch.cuda.is_available():
            torch.cuda.set_rng_state_all(cuda_rng_state)
        start = int(payload["step"])
        if metrics_path.exists():
            metrics = [
                item for item in json.loads(metrics_path.read_text())
                if int(item["iteration"]) <= start
            ]
        print(f"Resuming V3 from iteration {start}", flush=True)

    def train(replay) -> None:
        if len(replay) < 2:
            return
        for _ in range(args.gradient_steps):
            train_v3_step(model, optimizer, collate_v3(replay.sample(args.batch_size, train_rng), device))

    for iteration in range(start, args.iterations):
        record = asdict(search.step(iteration + 1, train))
        metrics.append(record)
        atomic_json(args.run_dir / "candidates-v3.json", candidate_payload(search))
        atomic_json(metrics_path, metrics)
        save_v3_checkpoint(checkpoint, model, optimizer, iteration + 1,
                           {
                               "search": search.state_dict(),
                               "train_rng_state": train_rng.getstate(),
                               "torch_rng_state": torch.get_rng_state(),
                               "cuda_rng_state_all": (
                                   torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None
                               ),
                           })
        print(json.dumps(record), flush=True)
    if search.population:
        # Also refresh an older resumed run whose checkpoint was already at
        # the requested iteration and whose archive omitted the scalar winner.
        atomic_json(args.run_dir / "candidates-v3.json", candidate_payload(search))
    print(json.dumps({"device": str(device), "iterations": metrics,
                      "archive_size": len(search.archive.items())}, indent=2))


if __name__ == "__main__":
    main()
