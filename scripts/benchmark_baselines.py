#!/usr/bin/env python3
"""Print baseline operation counts for a deterministic benchmark."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.baselines import BASELINES
from core.data import Task, make_array
from core.fast_shellsort import benchmark_shellsort


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--distribution", default="random")
    args = parser.parse_args()
    task = Task(args.n, args.distribution, args.seed)
    values = make_array(task)
    for name, gap_fn in BASELINES.items():
        _, cost = benchmark_shellsort(values, gap_fn(args.n))
        print(f"{name:10s} comparisons={cost.comparisons:10d} moves={cost.moves:10d} total={cost.total:10d}")


if __name__ == "__main__":
    main()
