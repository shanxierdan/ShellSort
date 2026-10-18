#!/usr/bin/env python3
"""Exact validation/test evaluation for proof-compatible tuning candidates."""

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
from core.evaluation import EvaluationCostCache
from core.tuning import (
    ARTIFACT_SCHEMA_VERSION,
    SOURCE_PROGRAM_HASH,
    TunedCandidate,
    panel_hash,
)

EVALUATOR_VERSION = 1


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def signature(candidate_items, tasks, stage: str, baseline_functions) -> str:
    sizes = sorted({task.n for task in tasks})
    payload = {
        "evaluator_version": EVALUATOR_VERSION,
        "stage": stage,
        "task_ids": [task.task_id for task in tasks],
        "candidate_hashes": [item["candidate_hash"] for item in candidate_items],
        "candidate_sequences": {
            item["candidate_hash"]: {
                str(n): TunedCandidate.from_dict(item["candidate"]).generate(n)
                for n in sizes
            }
            for item in candidate_items
        },
        "baseline_sequences": {
            str(n): {name: function(n) for name, function in baseline_functions.items()}
            for n in sizes
        },
        "array_generator": COMPACT_ARRAY_GENERATOR,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--manifest", type=Path, default=Path("data/experiment_manifest.json"))
    parser.add_argument("--stage", default="validation")
    parser.add_argument("--points", type=int)
    parser.add_argument("--distributions", nargs="+")
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--candidate-hash")
    parser.add_argument("--allow-test", action="store_true")
    args = parser.parse_args()

    is_test = args.stage == "test"
    if is_test and not args.allow_test:
        raise PermissionError("test requires --allow-test")
    manifest = json.loads(args.manifest.read_text())
    section = manifest[args.stage]
    points = args.points if args.points is not None else int(section["points"])
    distributions = tuple(args.distributions or section["distributions"])
    tasks = tuple(
        stage_tasks(
            args.manifest,
            args.stage,
            distributions,
            allow_test=is_test,
            points=points,
        )
    )

    candidate_set = json.loads(args.candidates.read_text())
    if candidate_set.get("source_program_hash") != SOURCE_PROGRAM_HASH:
        raise ValueError("candidate artifact is not based on the frozen source program")
    candidate_items = list(candidate_set["candidates"])
    requested_hash = args.candidate_hash or section.get("primary_candidate_hash")
    if requested_hash:
        candidate_items = [
            item for item in candidate_items if item["candidate_hash"] == requested_hash
        ]
        if len(candidate_items) != 1:
            raise ValueError(f"expected exactly one tuning candidate {requested_hash}")
    if is_test and len(candidate_items) != 1:
        raise ValueError("test evaluates exactly one frozen candidate")
    for item in candidate_items:
        candidate = TunedCandidate.from_dict(item["candidate"])
        if candidate.candidate_hash != item["candidate_hash"]:
            raise ValueError("tuning candidate hash mismatch")

    prefix_terms = TunedCandidate.from_dict(candidate_items[0]["candidate"]).prefix_terms
    original = TunedCandidate.base(prefix_terms)
    baseline_names = tuple(section.get(
        "baselines", ("untuned", "sedgewick", "tokuda", "ciura")
    ))
    baseline_functions = {}
    for name in baseline_names:
        if name == "untuned":
            baseline_functions[name] = original.generate
        elif name in BASELINES:
            baseline_functions[name] = BASELINES[name]
        else:
            raise ValueError(f"unknown tuning baseline: {name}")

    evaluation_signature = signature(
        candidate_items, tasks, args.stage, baseline_functions
    )
    output = args.output or args.candidates.parent / f"{args.stage}.json"
    if output.exists():
        existing = json.loads(output.read_text())
        if existing.get("evaluation_signature") == evaluation_signature:
            print(f"already complete: {output}", flush=True)
            return
        if is_test:
            raise RuntimeError(
                "existing test has a different signature; refusing to overwrite it"
            )
    cache_path = args.cache or output.parent / "final_evaluation_cost.sqlite"

    with EvaluationCostCache(cache_path) as cache:
        baseline_costs = {}
        for index, task in enumerate(tasks, 1):
            baseline_costs[task.task_id] = {
                name: cache.evaluate(
                    task, function(task.n), array_generator=COMPACT_ARRAY_GENERATOR
                )
                for name, function in baseline_functions.items()
            }
            print(f"tuning baseline {index}/{len(tasks)}: {task.task_id}", flush=True)

        reports = []
        for index, item in enumerate(candidate_items, 1):
            candidate = TunedCandidate.from_dict(item["candidate"])
            comparisons = moves = censored = 0
            log_cost = 0.0
            ratio_sums = {name: 0.0 for name in baseline_names}
            task_results = []
            for task in tasks:
                result = cache.evaluate(
                    task,
                    candidate.generate(task.n),
                    max_normalized_operations=50.0,
                    array_generator=COMPACT_ARRAY_GENERATOR,
                )
                comparisons += result.comparisons
                moves += result.moves
                censored += int(result.censored)
                scale = max(1.0, task.n * math.log2(task.n + 1))
                log_cost += math.log((result.total / scale) + 1e-12)
                ratios = {}
                serialized_baselines = {}
                for name, baseline in baseline_costs[task.task_id].items():
                    ratio = math.log((result.total + 1) / (baseline.total + 1))
                    ratio_sums[name] += ratio
                    ratios[name] = ratio
                    serialized_baselines[name] = {
                        "comparisons": baseline.comparisons,
                        "moves": baseline.moves,
                        "total": baseline.total,
                    }
                task_results.append({
                    "task_id": task.task_id,
                    "n": task.n,
                    "distribution": task.distribution,
                    "seed": task.seed,
                    "candidate": {
                        "comparisons": result.comparisons,
                        "moves": result.moves,
                        "total": result.total,
                        "censored": result.censored,
                    },
                    "baselines": serialized_baselines,
                    "log_ratios": ratios,
                })
            reports.append({
                "candidate_hash": candidate.candidate_hash,
                "selection_roles": item.get("selection_roles", []),
                "prefix": list(candidate.prefix),
                "prefix_terms": candidate.prefix_terms,
                "proof_compatibility": candidate.proof_compatibility,
                "task_count": len(tasks),
                "comparisons": comparisons,
                "moves": moves,
                "censored_tasks": censored,
                "mean_log_normalized_total": log_cost / len(tasks),
                "fixed_baseline_log_ratios": {
                    name: ratio_sums[name] / len(tasks) for name in baseline_names
                },
                "task_results": task_results,
            })
            print(
                f"tuning candidate {index}/{len(candidate_items)}: "
                f"{candidate.candidate_hash[:12]}",
                flush=True,
            )

        result_payload = {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "artifact_type": "final_evaluation",
            "evaluator_version": EVALUATOR_VERSION,
            "stage": args.stage,
            "source_program_hash": SOURCE_PROGRAM_HASH,
            "protocol": {
                "sizes": sorted({task.n for task in tasks}),
                "distributions": list(distributions),
                "seeds": sorted({task.seed for task in tasks}),
                "baselines": list(baseline_names),
                "array_generator": COMPACT_ARRAY_GENERATOR,
                "primary_candidate_hash": requested_hash,
                "success_rule": section.get("success_rule"),
            },
            "task_panel_hash": panel_hash(tasks),
            "evaluation_signature": evaluation_signature,
            "reports": reports,
        }
        if is_test:
            report = reports[0]
            ratios = report["fixed_baseline_log_ratios"]
            strong = [name for name in ("sedgewick", "tokuda", "ciura") if name in ratios]
            result_payload["test_decision"] = {
                "success": report["censored_tasks"] == 0
                and all(float(ratios[name]) < 0.0 for name in strong),
                "zero_censored_tasks": report["censored_tasks"] == 0,
                "beats_every_strong_baseline": all(
                    float(ratios[name]) < 0.0 for name in strong
                ),
                "mean_log_ratios": {name: ratios[name] for name in baseline_names},
            }
        atomic_json(output, result_payload)
        print(json.dumps({
            "status": "complete",
            "stage": args.stage,
            "reports": len(reports),
            "cache_hits": cache.hits,
            "cache_misses": cache.misses,
            "output": str(output),
        }), flush=True)


if __name__ == "__main__":
    main()
