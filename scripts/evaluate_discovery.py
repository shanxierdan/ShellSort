#!/usr/bin/env python3
"""Evaluate frozen programs with exact shared caching and resume support."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.baselines import BASELINES
from core.data import COMPACT_ARRAY_GENERATOR
from core.tasks import stage_tasks
from core.benchmark import panel_hash
from core.evaluation import EvaluationCost, EvaluationCostCache
from core.program import GeneratorProgram

EVALUATOR_VERSION = 3


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def evaluation_signature(
    candidate_set: dict[str, object],
    tasks,
    stage: str,
    baselines,
    array_generator: str,
) -> str:
    baseline_sequences = {
        str(n): {name: function(n) for name, function in baselines.items()}
        for n in sorted({task.n for task in tasks})
    }
    payload = {
        "evaluator_version": EVALUATOR_VERSION,
        "stage": stage,
        "task_ids": [task.task_id for task in tasks],
        "program_hashes": [item["program_hash"] for item in candidate_set["candidates"]],
        "array_generator": array_generator,
        "baseline_sequences": baseline_sequences,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def warm_baselines(
    cache: EvaluationCostCache, tasks, baseline_functions, array_generator: str
) -> dict[str, dict[str, EvaluationCost]]:
    costs: dict[str, dict[str, EvaluationCost]] = {}
    for index, task in enumerate(tasks, 1):
        costs[task.task_id] = {
            name: cache.evaluate(
                task, baseline(task.n), array_generator=array_generator
            )
            for name, baseline in baseline_functions.items()
        }
        print(f"baseline task {index}/{len(tasks)}: {task.task_id}", flush=True)
    return costs


def evaluate_program(
    program: GeneratorProgram,
    item,
    tasks,
    baselines,
    cache: EvaluationCostCache,
    array_generator: str,
):
    comparisons = moves = 0
    censored_tasks = 0
    ratio_sums = {name: 0.0 for name in next(iter(baselines.values())).keys()}
    task_results = []
    for task in tasks:
        candidate = cache.evaluate(
            task,
            program.generate(task.n),
            max_normalized_operations=50.0,
            array_generator=array_generator,
        )
        comparisons += candidate.comparisons
        moves += candidate.moves
        censored_tasks += int(candidate.censored)
        task_baselines = {}
        task_ratios = {}
        for name, baseline in baselines[task.task_id].items():
            ratio = math.log((candidate.total + 1) / (baseline.total + 1))
            ratio_sums[name] += ratio
            task_ratios[name] = ratio
            task_baselines[name] = {
                "comparisons": baseline.comparisons,
                "moves": baseline.moves,
                "total": baseline.total,
                "censored": baseline.censored,
            }
        task_results.append({
            "task_id": task.task_id,
            "n": task.n,
            "distribution": task.distribution,
            "seed": task.seed,
            "candidate": {
                "comparisons": candidate.comparisons,
                "moves": candidate.moves,
                "total": candidate.total,
                "censored": candidate.censored,
            },
            "baselines": task_baselines,
            "log_ratios": task_ratios,
        })
    report = {
        "program_hash": program.program_hash,
        "selection_roles": item.get("selection_roles", []),
        "source_seeds": item.get("source_seeds", []),
        "task_count": len(tasks),
        "comparisons": comparisons,
        "moves": moves,
        "censored_tasks": censored_tasks,
        "complexity": program.complexity,
        "fixed_baseline_log_ratios": {
            name: value / len(tasks) for name, value in ratio_sums.items()
        },
        "task_results": task_results,
    }
    if "validation_selection" in item:
        report["validation_selection"] = item["validation_selection"]
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidates", type=Path)
    parser.add_argument(
        "--stage", choices=("train", "validation", "extrapolation", "test"),
        default="validation",
    )
    parser.add_argument("--manifest", type=Path, default=Path("data/discovery_manifest.json"))
    parser.add_argument("--points", type=int)
    parser.add_argument("--distributions", nargs="+")
    parser.add_argument("--baselines", nargs="+", choices=tuple(BASELINES))
    parser.add_argument(
        "--array-generator",
        choices=("python_reference", COMPACT_ARRAY_GENERATOR),
    )
    parser.add_argument("--program-hash")
    parser.add_argument("--allow-test", action="store_true")
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline-only", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    if args.stage not in manifest:
        raise KeyError(f"unknown evaluation stage: {args.stage}")
    section = manifest[args.stage]
    points = args.points if args.points is not None else int(section.get("points", 4))
    distributions = tuple(
        args.distributions
        if args.distributions is not None
        else section.get("distributions", ("random", "reversed"))
    )
    baseline_names = tuple(
        args.baselines
        if args.baselines is not None
        else section.get("baselines", tuple(BASELINES))
    )
    baseline_functions = {name: BASELINES[name] for name in baseline_names}
    array_generator = (
        args.array_generator
        if args.array_generator is not None
        else str(section.get("array_generator", "python_reference"))
    )
    expected_primary = section.get("primary_program_hash")
    program_hash = args.program_hash or (
        str(expected_primary) if args.stage == "test" and expected_primary else None
    )
    if (
        args.stage == "test"
        and expected_primary
        and program_hash != str(expected_primary)
    ):
        raise ValueError("test program hash differs from the frozen primary")

    tasks = stage_tasks(
        args.manifest, args.stage, distributions, args.allow_test, points
    )
    source_candidate_set = json.loads(args.candidates.read_text())
    candidate_set = dict(source_candidate_set)
    if program_hash:
        selected = [
            item for item in source_candidate_set["candidates"]
            if item["program_hash"] == program_hash
        ]
        if len(selected) != 1:
            raise ValueError(f"expected exactly one frozen program {program_hash}")
        expected_seed = section.get("primary_source_seed")
        if expected_seed is not None and int(expected_seed) not in selected[0].get("source_seeds", []):
            raise ValueError("frozen primary does not carry the expected source seed")
        candidate_set["candidates"] = selected
        candidate_set["validation_selected_program_hashes"] = [program_hash]
    candidates = candidate_set["candidates"]
    if args.stage == "test" and len(candidates) != 1:
        raise ValueError("test must evaluate exactly one preregistered primary")
    signature = evaluation_signature(
        candidate_set, tasks, args.stage, baseline_functions, array_generator
    )
    output = args.output
    cache_path = args.cache or (
        output.parent / "evaluation-cost.sqlite"
        if output else args.candidates.parent / "evaluation-cost.sqlite"
    )

    if output and output.exists() and not args.baseline_only:
        completed = json.loads(output.read_text())
        if completed.get("evaluation_signature") == signature:
            print(f"already complete: {output}", flush=True)
            return
        if args.stage == "test":
            raise RuntimeError(
                "existing test output has a different signature; "
                "refusing to overwrite a previously opened blind test"
            )

    progress_path = output.with_suffix(output.suffix + ".progress") if output else None
    reports_by_hash: dict[str, dict[str, object]] = {}
    if progress_path and progress_path.exists():
        progress = json.loads(progress_path.read_text())
        if progress.get("evaluation_signature") == signature:
            reports_by_hash = {item["program_hash"]: item for item in progress["reports"]}
            print(f"resuming {len(reports_by_hash)}/{len(candidates)} reports", flush=True)
        elif args.stage == "test":
            raise RuntimeError(
                "existing test progress has a different signature; "
                "refusing to mix protocols"
            )

    with EvaluationCostCache(cache_path) as cache:
        baselines = warm_baselines(
            cache, tasks, baseline_functions, array_generator
        )
        if args.baseline_only:
            print(json.dumps({
                "stage": args.stage,
                "baseline_tasks": len(tasks),
                "baselines": list(baseline_names),
                "array_generator": array_generator,
                "cache_hits": cache.hits,
                "cache_misses": cache.misses,
            }), flush=True)
            return

        for index, item in enumerate(candidates, 1):
            expected_hash = item["program_hash"]
            if expected_hash in reports_by_hash:
                continue
            program = GeneratorProgram.from_dict(item["program"])
            if program.program_hash != expected_hash:
                raise ValueError(f"program hash mismatch: {expected_hash}")
            reports_by_hash[expected_hash] = evaluate_program(
                program, item, tasks, baselines, cache, array_generator
            )
            reports = [
                reports_by_hash[candidate["program_hash"]]
                for candidate in candidates
                if candidate["program_hash"] in reports_by_hash
            ]
            if progress_path:
                atomic_json(progress_path, {
                    "schema_version": 3,
                    "status": "running",
                    "stage": args.stage,
                    "evaluation_signature": signature,
                    "completed_reports": len(reports),
                    "total_reports": len(candidates),
                    "reports": reports,
                })
            print(
                f"candidate {index}/{len(candidates)}: {expected_hash[:12]} "
                f"cache_hits={cache.hits} cache_misses={cache.misses}",
                flush=True,
            )

        reports = [reports_by_hash[item["program_hash"]] for item in candidates]
        result = {
            "schema_version": 3,
            "evaluator_version": EVALUATOR_VERSION,
            "stage": args.stage,
            "protocol": {
                "points": points,
                "sizes": sorted({task.n for task in tasks}),
                "distributions": list(distributions),
                "seeds": sorted({task.seed for task in tasks}),
                "baselines": list(baseline_names),
                "array_generator": array_generator,
                "primary_program_hash": program_hash,
                "success_rule": section.get("success_rule"),
            },
            "task_panel_hash": panel_hash(tasks),
            "evaluation_signature": signature,
            "train_best_program_hash": candidate_set.get("train_best_program_hash"),
            "validation_selected_program_hashes": candidate_set.get(
                "validation_selected_program_hashes", []
            ),
            "reports": reports,
        }
        if args.stage == "test":
            report = reports[0]
            ratios = report["fixed_baseline_log_ratios"]
            success = (
                int(report["censored_tasks"]) == 0
                and all(float(ratios[name]) < 0.0 for name in baseline_names)
            )
            result["test_decision"] = {
                "success": success,
                "zero_censored_tasks": int(report["censored_tasks"]) == 0,
                "beats_every_preregistered_baseline": all(
                    float(ratios[name]) < 0.0 for name in baseline_names
                ),
                "mean_log_ratios": {
                    name: float(ratios[name]) for name in baseline_names
                },
            }
        if output:
            atomic_json(output, result)
            if progress_path:
                progress_path.unlink(missing_ok=True)
        print(json.dumps({
            "status": "complete",
            "stage": args.stage,
            "reports": len(reports),
            "cache_hits": cache.hits,
            "cache_misses": cache.misses,
            "output": str(output) if output else None,
        }), flush=True)


if __name__ == "__main__":
    main()
