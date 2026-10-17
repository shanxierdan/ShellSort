#!/usr/bin/env python3
"""Freeze one v3_tune candidate using only its independent validation panel."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.v3_tune import V3_TUNE_SCHEMA_VERSION, V3_TUNE_SOURCE_PROGRAM_HASH


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def selection_key(report: dict[str, object]) -> tuple[int, float, int, str]:
    return (
        int(report["censored_tasks"]),
        float(report["mean_log_normalized_total"]),
        int(report["comparisons"]) + int(report["moves"]),
        str(report["candidate_hash"]),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    candidate_set = json.loads(args.candidates.read_text())
    validation = json.loads(args.validation.read_text())
    if candidate_set.get("source_program_hash") != V3_TUNE_SOURCE_PROGRAM_HASH:
        raise ValueError("v3_tune source hash mismatch")
    validation_stage = str(validation.get("stage", ""))
    if not validation_stage.startswith("v3_tune_") or not validation_stage.endswith("_validation"):
        raise ValueError("selection requires a completed v3_tune_validation artifact")
    candidates = {item["candidate_hash"]: item for item in candidate_set["candidates"]}
    reports = validation["reports"]
    if set(candidates) != {item["candidate_hash"] for item in reports}:
        raise ValueError("v3_tune validation does not exactly cover the exported candidates")
    winner = min(reports, key=selection_key)
    candidate_hash = winner["candidate_hash"]
    item = dict(candidates[candidate_hash])
    roles = list(item.get("selection_roles", []))
    if "v3_tune_validation_winner" not in roles:
        roles.append("v3_tune_validation_winner")
    item["selection_roles"] = roles
    item["validation_selection"] = {
        "rule": "zero censoring then minimum self-supervised mean log normalized total",
        "candidate_hash": candidate_hash,
        "mean_log_normalized_total": winner["mean_log_normalized_total"],
        "comparisons": winner["comparisons"],
        "moves": winner["moves"],
        "fixed_baseline_log_ratios": winner["fixed_baseline_log_ratios"],
    }
    atomic_json(args.output, {
        "schema_version": V3_TUNE_SCHEMA_VERSION,
        "artifact_type": "v3_tune_selected",
        "selection_stage": validation_stage,
        "selection_rule": (
            "zero censoring then minimum self-supervised mean log normalized total; "
            "baselines are report-only"
        ),
        "source_program_hash": V3_TUNE_SOURCE_PROGRAM_HASH,
        "source_validation_signature": validation["evaluation_signature"],
        "primary_candidate_hash": candidate_hash,
        "candidates": [item],
    })
    print(
        f"v3_tune selected {candidate_hash[:12]} prefix={winner['prefix']} -> {args.output}",
        flush=True,
    )


if __name__ == "__main__":
    main()
