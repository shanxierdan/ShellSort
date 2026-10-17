#!/usr/bin/env python3
"""Estimate finite-range scaling from the frozen V3 exact-cost cache.

This script deliberately reports empirical fits rather than asymptotic
complexity claims.  It only reads the already completed Validation and
Extrapolation random-permutation tasks; Final Test remains sealed.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.baselines import BASELINES
from core.discovery import stage_tasks
from core.program_v3 import GeneratorProgram
from core.sequence import GapSequence


DEFAULT_CANDIDATE = "f8e20407ede6a625fff7e6fb2c9f093bb026fc0ea8ddd87cea821525891e731c"
STRONG_BASELINES = ("sedgewick", "tokuda", "ciura")


def linear_fit(xs: list[float], ys: list[float]) -> dict[str, float | int | None]:
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("a linear fit requires at least two paired observations")
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    sxx = sum((x - x_mean) ** 2 for x in xs)
    if sxx == 0:
        raise ValueError("a linear fit requires non-constant x values")
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / sxx
    intercept = y_mean - slope * x_mean
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    sse = sum(value * value for value in residuals)
    rmse = math.sqrt(sse / len(xs))
    slope_se = None
    if len(xs) > 2:
        slope_se = math.sqrt((sse / (len(xs) - 2)) / sxx)
    return {
        "observations": len(xs),
        "intercept": intercept,
        "slope": slope,
        "slope_residual_se": slope_se,
        "log_rmse": rmse,
    }


def scaling_fits(rows: list[dict[str, object]]) -> dict[str, object]:
    ns = [int(row["n"]) for row in rows]
    totals = [float(row["mean_total_operations"]) for row in rows]
    power = linear_fit([math.log(n) for n in ns], [math.log(value) for value in totals])
    beta = float(power["slope"])
    power["beta"] = beta
    power["coefficient"] = math.exp(float(power["intercept"]))
    power["frobenius_window_equivalent_m"] = (
        1.0 / (beta - 1.0) if beta > 1.0 else None
    )

    n_log_n = linear_fit(
        [math.log(math.log(n)) for n in ns],
        [math.log(value / n) for n, value in zip(ns, totals)],
    )
    n_log_n["gamma"] = float(n_log_n["slope"])
    n_log_n["coefficient"] = math.exp(float(n_log_n["intercept"]))

    local = []
    for left, right in zip(rows, rows[1:]):
        left_n = int(left["n"])
        right_n = int(right["n"])
        # Validation ends at 1,000,000 and Extrapolation starts at
        # 1,000,001 with different task seeds.  Treating that near-duplicate
        # pair as a local scaling interval would amplify sampling noise by a
        # factor of roughly one million.
        if right_n / left_n < 1.05:
            continue
        left_total = float(left["mean_total_operations"])
        right_total = float(right["mean_total_operations"])
        local.append({
            "left_n": left_n,
            "right_n": right_n,
            "beta": math.log(right_total / left_total) / math.log(right_n / left_n),
        })
    return {"power_law": power, "n_log_n_power": n_log_n, "local_power_slopes": local}


def cached_cost(
    connection: sqlite3.Connection,
    sequence: GapSequence,
    task_id: str,
    budget: str,
) -> tuple[int, int, bool]:
    key = f"exact-v3:{sequence.semantic_hash}:{task_id}:{budget}"
    row = connection.execute(
        "SELECT comparisons, moves, censored FROM exact_cost_v3 WHERE cache_key=?", (key,)
    ).fetchone()
    if row is None:
        raise RuntimeError(f"missing completed cache row: {key}")
    return int(row[0]), int(row[1]), bool(row[2])


def series_for(
    connection: sqlite3.Connection,
    label: str,
    program: GeneratorProgram,
    manifest: Path,
) -> list[dict[str, object]]:
    by_stage_n: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    for stage, points in (("validation", 8), ("extrapolation", 4)):
        tasks = stage_tasks(manifest, stage, ("random",), False, points)
        for task in tasks:
            if label == "candidate":
                gaps = program.generate(task.n)
                budget = "budget-50"
            else:
                gaps = BASELINES[label](task.n)
                budget = "exact"
            comparisons, moves, censored = cached_cost(
                connection, GapSequence(task.n, tuple(gaps)), task.task_id, budget
            )
            if censored:
                raise RuntimeError(f"unexpected censored row for {label}: {task.task_id}")
            by_stage_n[(stage, task.n)].append({
                "seed": task.seed,
                "comparisons": comparisons,
                "moves": moves,
                "total_operations": comparisons + moves,
            })

    rows: list[dict[str, object]] = []
    for (stage, n), seed_costs in sorted(by_stage_n.items(), key=lambda item: item[0][1]):
        mean_comparisons = sum(int(x["comparisons"]) for x in seed_costs) / len(seed_costs)
        mean_moves = sum(int(x["moves"]) for x in seed_costs) / len(seed_costs)
        mean_total = mean_comparisons + mean_moves
        rows.append({
            "stage": stage,
            "n": n,
            "mean_comparisons": mean_comparisons,
            "mean_moves": mean_moves,
            "mean_total_operations": mean_total,
            "operations_per_n_log2_n": mean_total / (n * math.log2(n + 1)),
            "seed_costs": seed_costs,
        })
    return rows


def fits_by_range(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "validation_and_extrapolation": scaling_fits(rows),
        "validation": scaling_fits([row for row in rows if row["stage"] == "validation"]),
        "extrapolation": scaling_fits([row for row in rows if row["stage"] == "extrapolation"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selected", type=Path, default=Path("result/v3/selected-v3.json"))
    parser.add_argument(
        "--cache", type=Path, default=Path("result/v3/evaluation-cost-v3.sqlite")
    )
    parser.add_argument("--manifest", type=Path, default=Path("data/manifests.json"))
    parser.add_argument("--candidate-hash", default=DEFAULT_CANDIDATE)
    parser.add_argument(
        "--output", type=Path, default=Path("result/v3/complexity-estimate-v3.json")
    )
    args = parser.parse_args()

    selected = json.loads(args.selected.read_text(encoding="utf-8"))
    item = next(
        (entry for entry in selected["candidates"] if entry["program_hash"] == args.candidate_hash),
        None,
    )
    if item is None:
        raise ValueError(f"candidate not found in frozen selection: {args.candidate_hash}")
    program = GeneratorProgram.from_dict(item["program"])
    if program.program_hash != args.candidate_hash:
        raise ValueError("frozen candidate hash mismatch")

    labels = ("candidate",) + STRONG_BASELINES
    with sqlite3.connect(args.cache) as connection:
        series = {
            label: series_for(connection, label, program, args.manifest) for label in labels
        }

    payload = {
        "schema_version": 1,
        "status": "descriptive_estimate_not_asymptotic_proof",
        "candidate_program_hash": args.candidate_hash,
        "metric": "comparisons_plus_moves",
        "input_distribution": "uniform_random_permutation",
        "stages": ["validation", "extrapolation"],
        "final_test_used": False,
        "fit_warning": (
            "Slope standard errors only describe residuals around the selected log-linear model; "
            "they do not quantify asymptotic model uncertainty."
        ),
        "series": series,
        "fits": {label: fits_by_range(rows) for label, rows in series.items()},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({
        "status": "complete",
        "candidate": args.candidate_hash,
        "output": str(args.output),
        "candidate_extrapolation_beta": payload["fits"]["candidate"]["extrapolation"]
        ["power_law"]["beta"],
    }))


if __name__ == "__main__":
    main()
