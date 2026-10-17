#!/usr/bin/env python3
"""Freeze one V3 extrapolation candidate per seed using Validation only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

STRONG_BASELINES = ("sedgewick", "tokuda", "ciura")


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def selection_key(report: dict[str, object]):
    ratios = report["fixed_baseline_log_ratios"]
    strong = [float(ratios[name]) for name in STRONG_BASELINES]
    complexity = tuple(int(x) for x in report["complexity"])
    return (
        int(report.get("censored_tasks", 0)),
        max(strong),
        sum(strong) / len(strong),
        int(report["comparisons"]) + int(report["moves"]),
        complexity,
        report["program_hash"],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=Path("result/v3"))
    parser.add_argument("--seeds", type=int, nargs="+", default=(0, 1, 2, 3, 4))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or args.run_root / "selected-v3.json"

    selected: dict[str, dict[str, object]] = {}
    source_validation_signatures: dict[str, str] = {}
    for seed in args.seeds:
        seed_dir = args.run_root / f"seed-{seed}"
        candidate_set = json.loads((seed_dir / "candidates-v3.json").read_text())
        validation = json.loads((seed_dir / "validation-v3.json").read_text())
        if validation.get("evaluator_version") not in {2, 3} or validation.get("stage") != "validation":
            raise ValueError(f"seed {seed} Validation is not a completed V3 evaluation result")
        candidates = {item["program_hash"]: item for item in candidate_set["candidates"]}
        reports = validation["reports"]
        if set(candidates) != {item["program_hash"] for item in reports}:
            raise ValueError(f"seed {seed} Validation does not cover its frozen candidate set")
        winner = min(reports, key=selection_key)
        program_hash = winner["program_hash"]
        ratios = winner["fixed_baseline_log_ratios"]
        strong = {name: ratios[name] for name in STRONG_BASELINES}
        selection = {
            "rule": "minimize_worst_strong_baseline_log_ratio",
            "censored_tasks": int(winner.get("censored_tasks", 0)),
            "strong_baselines": list(STRONG_BASELINES),
            "worst_log_ratio": max(strong.values()),
            "mean_log_ratio": sum(strong.values()) / len(strong),
            "ratios": strong,
        }
        if program_hash in selected:
            selected[program_hash]["source_seeds"].append(seed)
        else:
            item = dict(candidates[program_hash])
            roles = list(item.get("selection_roles", []))
            if "validation_winner" not in roles:
                roles.append("validation_winner")
            item.update({
                "selection_roles": roles,
                "source_seeds": [seed],
                "validation_selection": selection,
            })
            selected[program_hash] = item
        source_validation_signatures[str(seed)] = validation["evaluation_signature"]
        print(
            f"seed={seed} winner={program_hash[:12]} worst_strong={selection['worst_log_ratio']:.9f}",
            flush=True,
        )

    candidates = sorted(selected.values(), key=lambda item: min(item["source_seeds"]))
    atomic_json(output, {
        "schema_version": 3,
        "selection_stage": "validation",
        "selection_rule": {
            "per_seed": 1,
            "objective": "prefer zero censored tasks, then minimize worst log ratio over Sedgewick, Tokuda and Ciura",
            "deduplicate_identical_program_hashes": True,
        },
        "source_validation_signatures": source_validation_signatures,
        "validation_selected_program_hashes": [item["program_hash"] for item in candidates],
        "candidates": candidates,
    })
    print(f"selected {len(candidates)} unique programs -> {output}", flush=True)


if __name__ == "__main__":
    main()
