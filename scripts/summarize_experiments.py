#!/usr/bin/env python3
"""Aggregate per-seed search and validation outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    runs = []
    for summary_path in sorted(args.run_root.glob("seed-*/summary.json")):
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        pareto = summary.get("pareto", [])
        best = min(pareto, key=lambda item: item["loss"]) if pareto else None
        validation_path = summary_path.parent / "validation.json"
        validation = None
        if validation_path.exists():
            records = json.loads(validation_path.read_text(encoding="utf-8"))
            scores = [item for item in records.get("scores", []) if "loss" in item]
            validation = min(scores, key=lambda item: item["loss"]) if scores else None
        runs.append(
            {
                "run": summary_path.parent.name,
                "device": summary.get("device"),
                "best_search": best,
                "best_validation": validation,
                "iterations": summary.get("iterations", []),
            }
        )
    payload = {"run_count": len(runs), "runs": runs}
    output = args.output or args.run_root / "aggregate.json"
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
