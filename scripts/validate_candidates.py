#!/usr/bin/env python3
"""Evaluate frozen candidates on a separated discovery stage."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.discovery import load_candidates, stage_tasks
from core.evaluation import Benchmark
from core.shellsort import OperationLimitExceeded


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--manifest", type=Path, default=Path("data/manifests.json"))
    parser.add_argument("--stage", choices=("train", "validation", "extrapolation", "final_test"), default="validation")
    parser.add_argument("--allow-final-test", action="store_true")
    parser.add_argument("--points", type=int, default=2)
    parser.add_argument("--distributions", nargs="+", default=("random", "reversed", "nearly_sorted", "duplicates", "blocks"))
    parser.add_argument("--seed-limit", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline-cache", type=Path)
    parser.add_argument("--candidate-budget-ratio", type=float, default=10.0)
    args = parser.parse_args()
    tasks = stage_tasks(
        args.manifest,
        args.stage,
        distributions=tuple(args.distributions),
        allow_final_test=args.allow_final_test,
        points=args.points,
    )
    if args.seed_limit is not None:
        allowed = sorted({task.seed for task in tasks})[: args.seed_limit]
        tasks = [task for task in tasks if task.seed in allowed]
    candidates = load_candidates(args.candidates)
    records = []
    if candidates:
        benchmark = Benchmark(
            tasks,
            baseline_cache=args.baseline_cache,
            candidate_budget_ratio=args.candidate_budget_ratio,
        )
        for item in candidates:
            try:
                records.append(asdict(benchmark.evaluate(item.verify())))
            except OperationLimitExceeded:
                records.append({"program_id": item.program_id, "status": "operation_limit_exceeded"})
    payload = {"stage": args.stage, "task_count": len(tasks), "scores": records}
    text = json.dumps(payload, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
