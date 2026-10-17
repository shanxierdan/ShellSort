#!/usr/bin/env python3
"""Evaluate frozen V2 generators absolutely and against each fixed baseline."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.baselines import BASELINES
from core.data import make_array
from core.discovery import stage_tasks
from core.fast_shellsort import benchmark_shellsort
from core.generator_v2 import LogPositionGenerator


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--stage", choices=("train", "validation", "extrapolation", "final_test"), default="validation")
    parser.add_argument("--manifest", type=Path, default=Path("data/manifests.json"))
    parser.add_argument("--points", type=int, default=4)
    parser.add_argument("--distributions", nargs="+", default=("random", "reversed"))
    parser.add_argument("--allow-final-test", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    tasks = stage_tasks(args.manifest, args.stage, tuple(args.distributions), args.allow_final_test, args.points)
    payload = json.loads(args.candidates.read_text())
    reports = []
    for item in payload["candidates"]:
        generator = LogPositionGenerator.from_dict(item["generator"])
        totals = {"candidate": [0, 0]}
        paired = {name: [] for name in BASELINES}
        for task in tasks:
            values = make_array(task)
            candidate = benchmark_shellsort(values, generator.generate(task.n))[1]
            totals["candidate"][0] += candidate.comparisons
            totals["candidate"][1] += candidate.moves
            for name, baseline in BASELINES.items():
                cost = benchmark_shellsort(values, baseline(task.n))[1]
                paired[name].append(math.log((candidate.total + 1) / (cost.total + 1)))
        reports.append({
            "generator_hash": generator.generator_hash,
            "task_count": len(tasks),
            "comparisons": totals["candidate"][0],
            "moves": totals["candidate"][1],
            "fixed_baseline_log_ratios": {name: sum(values) / len(values) for name, values in paired.items()},
        })
    result = {"schema_version": 2, "stage": args.stage, "reports": reports}
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
