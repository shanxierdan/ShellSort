#!/usr/bin/env python3
"""Stress-test the variable-window quotient conjecture on small rational bases.

The frozen V3 theorem may use its exact orbit, but it must not be justified by a
false universal claim about every rational ratio.  This script generates small
exact models h_t=floor(alpha*(A/B)^t), chooses m=ceil(log_A(h_t)), and computes
the generalized holes exactly whenever the Apéry modulus is affordable.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import json
import math
from pathlib import Path

try:
    from scripts.analyze_v3_generalized_holes import generalized_hole_profile
except ModuleNotFoundError:
    from analyze_v3_generalized_holes import generalized_hole_profile


DEFAULT_RATIOS = ((5, 2), (7, 3), (12, 5), (13, 5), (17, 7))


def exact_rational_gaps(
    ratio_numerator: int,
    ratio_denominator: int,
    alpha: Fraction,
    maximum_gap: int,
    extra_terms: int,
) -> list[int]:
    if ratio_numerator <= ratio_denominator or ratio_denominator <= 0:
        raise ValueError("the rational ratio must be greater than one")
    numerator = alpha.numerator
    denominator = alpha.denominator
    gaps: list[int] = []
    while not gaps or gaps[-1] <= maximum_gap:
        gap = numerator // denominator
        if gap > 0 and (not gaps or gap != gaps[-1]):
            gaps.append(gap)
        numerator *= ratio_numerator
        denominator *= ratio_denominator
    for _ in range(extra_terms):
        gap = numerator // denominator
        if gap > 0 and gap != gaps[-1]:
            gaps.append(gap)
        numerator *= ratio_numerator
        denominator *= ratio_denominator
    return gaps


def audit_ratio(
    ratio_numerator: int,
    ratio_denominator: int,
    alpha: Fraction,
    minimum_gap: int,
    maximum_gap: int,
) -> dict[str, object]:
    gaps = exact_rational_gaps(
        ratio_numerator,
        ratio_denominator,
        alpha,
        maximum_gap,
        extra_terms=32,
    )
    rows = []
    for base, step in enumerate(gaps):
        if step < minimum_gap or step > maximum_gap:
            continue
        width = max(2, math.ceil(math.log(step, ratio_numerator)))
        generators = gaps[base + 1 : base + 1 + width]
        if len(generators) != width:
            raise AssertionError("exact generator left no complete future window")
        profile = generalized_hole_profile(step, generators)
        conductor = (
            None
            if profile is None
            else (profile[0][-1] + 1 if profile[0] else 0)
        )
        denominator_scale = step / (ratio_denominator**width)
        rows.append({
            "base_gap": step,
            "window": width,
            "h_over_A_to_m": step / (ratio_numerator**width),
            "h_over_B_to_m": denominator_scale,
            "finite": profile is not None,
            "generalized_holes": None if profile is None else len(profile[0]),
            "maximum_missing_multiplier": (
                None if profile is None or not profile[0] else profile[0][-1]
            ),
            "quotient_conductor": conductor,
            "conductor_over_h_over_B_to_m": (
                None
                if conductor is None
                else conductor / denominator_scale
            ),
        })
    return {
        "ratio": [ratio_numerator, ratio_denominator],
        "rows": rows,
        "infinite_window_count": sum(not bool(row["finite"]) for row in rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alpha", type=Fraction, default=Fraction(7, 13))
    parser.add_argument("--minimum-gap", type=int, default=100)
    parser.add_argument("--maximum-gap", type=int, default=50_000)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("result/v3/rational-quotient-stress.json"),
    )
    args = parser.parse_args()
    reports = [
        audit_ratio(a, b, args.alpha, args.minimum_gap, args.maximum_gap)
        for a, b in DEFAULT_RATIOS
    ]
    payload = {
        "schema_version": 1,
        "status": "counterexample_stress_not_a_claim_about_the_frozen_v3_orbit",
        "alpha": [args.alpha.numerator, args.alpha.denominator],
        "window_rule": "m=max(2,ceil(log_A(h_t)))",
        "reports": reports,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({"status": "complete", "output": str(args.output)}))


if __name__ == "__main__":
    main()
