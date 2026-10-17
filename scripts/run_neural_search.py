#!/usr/bin/env python3
"""Pretrain and run neural-guided PUCT policy iteration."""

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
from core.discovery import FrozenCandidate, log_spaced_sizes, save_candidates
from core.evaluation import Benchmark
from core.grammar import PRODUCTIONS, VOCAB_SIZE
from model.agent import resolve_device
from model.network import PolicyValueFeasibilityNet
from model.policy_iteration import PolicyIteration
from model.pretrain import curated_samples
from model.training import ReplayBuffer, collate, load_checkpoint, save_checkpoint, train_step


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=Path("result/neural-smoke"))
    parser.add_argument("--device", default="auto")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--iterations", type=int, default=2)
    parser.add_argument("--episodes", type=int, default=8)
    parser.add_argument("--simulations", type=int, default=16)
    parser.add_argument("--gradient-steps", type=int, default=4)
    parser.add_argument("--pretrain-steps", type=int, default=20)
    parser.add_argument("--max-nodes", type=int, default=16)
    parser.add_argument("--hidden-size", type=int, default=128)
    parser.add_argument("--layers", type=int, default=3)
    parser.add_argument("--heads", type=int, default=4)
    parser.add_argument("--train-min-n", type=int, default=32)
    parser.add_argument("--train-max-n", type=int, default=100000)
    parser.add_argument("--train-points", type=int, default=8)
    parser.add_argument("--train-distributions", nargs="+", default=("random", "reversed"))
    parser.add_argument("--train-seeds", type=int, nargs="+", default=(0,))
    parser.add_argument("--panel-points", type=int, default=8)
    parser.add_argument("--panel-distributions", type=int, default=2)
    parser.add_argument("--panel-seeds", type=int, default=1)
    parser.add_argument("--baseline-cache", type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    rng = random.Random(args.seed)
    device = resolve_device(args.device)
    model = PolicyValueFeasibilityNet(
        VOCAB_SIZE,
        len(PRODUCTIONS),
        hidden_size=args.hidden_size,
        layers=args.layers,
        heads=args.heads,
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4)

    train_sizes = log_spaced_sizes(args.train_min_n, args.train_max_n, args.train_points)
    panel_size = min(args.panel_points, len(train_sizes))
    distribution_panel_size = min(args.panel_distributions, len(args.train_distributions))
    seed_panel_size = min(args.panel_seeds, len(args.train_seeds))
    initial_sizes = tuple(rng.sample(list(train_sizes), panel_size))
    initial_distributions = tuple(rng.sample(list(args.train_distributions), distribution_panel_size))
    initial_seeds = tuple(rng.sample(list(args.train_seeds), seed_panel_size))
    tasks = [
        Task(n, distribution, seed)
        for n in initial_sizes
        for distribution in initial_distributions
        for seed in initial_seeds
    ]
    trainer = PolicyIteration(
        model,
        Benchmark(tasks, baseline_cache=args.baseline_cache),
        device=str(device),
        simulations=args.simulations,
        max_nodes=args.max_nodes,
        seed=args.seed,
    )
    args.run_dir.mkdir(parents=True, exist_ok=True)
    config = {
        key: str(value) if isinstance(value, Path) else value
        for key, value in vars(args).items()
    }
    config["resolved_device"] = str(device)
    (args.run_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    checkpoint_path = args.run_dir / "checkpoint.pt"
    metrics_path = args.run_dir / "metrics.json"
    metrics = []
    start_iteration = 0
    if args.resume and checkpoint_path.exists():
        # Checkpoints created before reward schema v1 used invalid target -5
        # with a tanh value head. Preserve learned weights/replay but discard
        # incompatible optimizer moments during the one-time migration.
        payload = load_checkpoint(checkpoint_path, model, optimizer=None)
        reward_schema = int(payload.get("metadata", {}).get("reward_schema_version", 0))
        if reward_schema >= 1 and payload.get("optimizer") is not None:
            trainer.optimizer.load_state_dict(payload["optimizer"])
        saved_state = payload.get("training_state", {})
        trainer.load_state_dict(saved_state)
        if saved_state.get("panel_rng_state") is not None:
            rng.setstate(saved_state["panel_rng_state"])
        start_iteration = int(payload["step"])
        if metrics_path.exists():
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        print(f"Resuming from iteration {start_iteration}", flush=True)
    else:
        pretrain = ReplayBuffer()
        pretrain.extend(curated_samples(max_nodes=max(20, args.max_nodes)))
        for _ in range(args.pretrain_steps):
            batch = collate(pretrain.sample(32, rng), device)
            train_step(model, optimizer, batch)

    for iteration in range(start_iteration, args.iterations):
        panel_sizes = tuple(rng.sample(list(train_sizes), panel_size))
        panel_distributions = tuple(
            rng.sample(list(args.train_distributions), distribution_panel_size)
        )
        panel_seeds = tuple(rng.sample(list(args.train_seeds), seed_panel_size))
        panel_tasks = [
            Task(n, distribution, seed)
            for n in panel_sizes
            for distribution in panel_distributions
            for seed in panel_seeds
        ]
        trainer.set_benchmark(Benchmark(panel_tasks, baseline_cache=args.baseline_cache))
        record = asdict(trainer.run_iteration(args.episodes, args.gradient_steps))
        record["iteration"] = iteration + 1
        record["panel_sizes"] = panel_sizes
        record["panel_distributions"] = panel_distributions
        record["panel_seeds"] = panel_seeds
        metrics.append(record)

        pareto_ids = {item["program_id"] for item in trainer.archive.records()}
        frozen = [
            FrozenCandidate.create(generator, score)
            for program_id, (generator, score) in trainer.candidates.items()
            if program_id in pareto_ids
        ]
        save_candidates(args.run_dir / "candidates.json", frozen)
        metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        summary = {"device": str(device), "iterations": metrics, "pareto": trainer.archive.records()}
        (args.run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        training_state = trainer.state_dict()
        training_state["panel_rng_state"] = rng.getstate()
        save_checkpoint(
            checkpoint_path,
            model,
            trainer.optimizer,
            iteration + 1,
            {"device": str(device), "reward_schema_version": 1},
            training_state,
        )
        print(json.dumps(record), flush=True)

    summary = {"device": str(device), "iterations": metrics, "pareto": trainer.archive.records()}
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
