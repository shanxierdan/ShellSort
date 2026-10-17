#!/usr/bin/env python3
"""Run the first deterministic random-search baseline."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.data import Task
from core.dsl import Expr
from core.evaluation import Benchmark
from core.generators import RecursiveGenerator
from core.search import random_expression, random_search


def candidate_factory(rng: random.Random) -> RecursiveGenerator:
    # Keeping Init simple makes the baseline generate enough valid candidates.
    divisor = rng.choice((2, 3, 4, 5))
    init = Expr("floor", (Expr("div", (Expr.variable("n"), Expr.constant(divisor))),))
    next_gap = random_expression(rng, ("h",), depth=3)
    return RecursiveGenerator(init, next_gap)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget", type=int, default=100)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--run-dir", type=Path, default=Path("result/smoke"))
    args = parser.parse_args()
    tasks = [Task(n, "random", seed) for n in (64, 128, 256) for seed in (0, 1)]
    archive, evaluations = random_search(candidate_factory, Benchmark(tasks), args.budget, args.seed)
    args.run_dir.mkdir(parents=True, exist_ok=True)
    output = {"budget": args.budget, "real_evaluations": evaluations, "pareto": archive.records()}
    (args.run_dir / "summary.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
