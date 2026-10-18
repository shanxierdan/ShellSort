#!/usr/bin/env python3
"""Enumerate all floor windows over theta and stress the carry-interval scale.

For fixed A/B, d and m, the vector

    floor((A/B)^i * (d+theta)),  1<=i<=m,

is piecewise constant for theta in [0,1).  Enumerating its exact rational
breakpoints tests every possible rounding state, rather than one alpha orbit.
The resulting counterexamples show that small-scale saturation is not
automatic.  A separate exact A/B=5/2 family below makes the asymptotic point:
its low-controllability prefix has length m-3 and forces a quotient hole whose
normalized size grows exponentially in m.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import json
import math
from pathlib import Path

try:
    from scripts.analyze_generalized_holes import generalized_hole_profile
except ModuleNotFoundError:
    from analyze_generalized_holes import generalized_hole_profile


DEFAULT_CASES = {
    "3/2": (3, 2, (100, 1_000, 10_000)),
    "5/2": (5, 2, (100, 1_000, 10_000)),
    "7/3": (7, 3, (100, 1_000, 3_000)),
}


def exact_floor_window(
    numerator: int,
    denominator: int,
    step: int,
    theta: Fraction,
    width: int,
) -> list[int]:
    scaled = step * theta.denominator + theta.numerator
    return [
        numerator**index * scaled
        // (denominator**index * theta.denominator)
        for index in range(1, width + 1)
    ]


def floor_window_patterns(
    numerator: int, denominator: int, step: int, width: int
) -> list[tuple[list[int], Fraction]]:
    """Return every distinct floor window and one exact theta witness."""
    breakpoints = {Fraction(0), Fraction(1)}
    for index in range(1, width + 1):
        numerator_power = numerator**index
        denominator_power = denominator**index
        first = (step * numerator_power + denominator_power - 1) // denominator_power
        last = (
            ((step + 1) * numerator_power + denominator_power - 1)
            // denominator_power
        )
        for integer_part in range(first, last + 1):
            value = Fraction(
                integer_part * denominator_power, numerator_power
            ) - step
            if 0 < value < 1:
                breakpoints.add(value)
    ordered = sorted(breakpoints)
    patterns: list[tuple[list[int], Fraction]] = []
    for left, right in zip(ordered, ordered[1:]):
        theta = (left + right) / 2
        gaps = exact_floor_window(
            numerator, denominator, step, theta, width
        )
        if not patterns or patterns[-1][0] != gaps:
            patterns.append((gaps, theta))
    return patterns


def leading_zero_error_run(
    gaps: list[int], numerator: int, denominator: int
) -> int:
    run = 0
    for left, right in zip(gaps, gaps[1:]):
        if denominator * right - numerator * left != 0:
            break
        run += 1
    return run


def parametric_counterexample_case(prefix_power: int) -> dict[str, object]:
    """Return one member of an exact 5/2 low-controllability family.

    Put d=2^L*u with u congruent to 3 modulo 4 and u asymptotic to
    6*(5/2)^L, then use m=L+2 future floors at theta=0.  The local errors are
    0^(L-1),-1,1.  If a representation of k*d uses neither of the last two
    generators, then 5 divides k.  Otherwise their coefficients y,z obey
    2y+3z=0 modulo u, hence y+z>=u/3.  This supplies an explicit quotient
    hole of order u*(5/2)^L while d/2^m=u/4.
    """
    if prefix_power < 2:
        raise ValueError("prefix_power must be at least two")
    numerator = 5
    denominator = 2
    scaled = 6 * numerator**prefix_power
    divisor = denominator**prefix_power
    u = (scaled + divisor - 1) // divisor
    u += (3 - u) % 4
    step = denominator**prefix_power * u
    width = prefix_power + 2
    gaps = exact_floor_window(
        numerator, denominator, step, Fraction(0), width
    )
    errors = [
        denominator * right - numerator * left
        for left, right in zip(gaps, gaps[1:])
    ]
    expected_errors = [0] * (prefix_power - 1) + [-1, 1]
    if errors != expected_errors:
        raise AssertionError("parametric family lost its exact error word")
    if not numerator ** (width - 1) < step <= numerator**width:
        raise AssertionError("family width is not ceil(log_A(d))")
    penultimate, final = gaps[-2:]
    if 2 * final - 5 * penultimate != 1:
        raise AssertionError("last two generators are not certified coprime")

    # Every k below u*b/(3*d), not divisible by five, is absent.  Pick the
    # largest such integer to obtain a concrete exact conductor lower bound.
    guaranteed_hole = (u * penultimate - 1) // (3 * step)
    while guaranteed_hole % 5 == 0:
        guaranteed_hole -= 1
    if guaranteed_hole <= 0:
        raise AssertionError("parametric hole bound became vacuous")
    conductor_lower_bound = guaranteed_hole + 1
    scale_numerator = step
    scale_denominator = denominator**width
    normalized_lower_bound = (
        conductor_lower_bound * scale_denominator / scale_numerator
    )
    return {
        "ratio": [numerator, denominator],
        "prefix_power_L": prefix_power,
        "base_gap": step,
        "window_m": width,
        "u": u,
        "local_errors": errors,
        "leading_zero_error_run": prefix_power - 1,
        "last_two_generators": [penultimate, final],
        "two_c_minus_five_b": 2 * final - 5 * penultimate,
        "guaranteed_missing_multiplier": guaranteed_hole,
        "quotient_conductor_lower_bound": conductor_lower_bound,
        "h_over_B_to_m_exact": [scale_numerator, scale_denominator],
        "conductor_lower_bound_over_h_over_B_to_m": normalized_lower_bound,
        "proof_status": (
            "exact_family_member; quotient_is_finite_because_the_last_two_"
            "future_gaps_are_coprime"
        ),
    }


def audit_case(
    numerator: int, denominator: int, step: int
) -> dict[str, object]:
    width = max(2, math.ceil(math.log(step, numerator)))
    patterns = floor_window_patterns(numerator, denominator, step, width)
    infinite = 0
    worst: dict[str, object] | None = None
    for gaps, theta in patterns:
        profile = generalized_hole_profile(step, gaps)
        if profile is None:
            infinite += 1
            continue
        conductor = profile[0][-1] + 1 if profile[0] else 0
        scale = step / (denominator**width)
        ratio = conductor / scale
        errors = [
            denominator * right - numerator * left
            for left, right in zip(gaps, gaps[1:])
        ]
        row: dict[str, object] = {
            "theta": [theta.numerator, theta.denominator],
            "future_gaps": gaps,
            "local_errors": errors,
            "leading_zero_error_run": leading_zero_error_run(
                gaps, numerator, denominator
            ),
            "quotient_conductor": conductor,
            "h_over_B_to_m": scale,
            "conductor_over_h_over_B_to_m": ratio,
        }
        if worst is None or ratio > float(worst["conductor_over_h_over_B_to_m"]):
            worst = row
    return {
        "ratio": [numerator, denominator],
        "base_gap": step,
        "window": width,
        "rounding_patterns": len(patterns),
        "infinite_quotient_patterns": infinite,
        "worst_finite_pattern": worst,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("result/discovery/carry-orbit-stress.json"),
    )
    args = parser.parse_args()
    reports = []
    for numerator, denominator, steps in DEFAULT_CASES.values():
        reports.extend(
            audit_case(numerator, denominator, step) for step in steps
        )
    payload = {
        "schema_version": 1,
        "status": "exact_parametric_generic_counterexample_not_frozen_candidate_proof",
        "claim_refuted": (
            "a polynomial-in-m multiple of d/B^m bounds every finite "
            "rational-floor quotient uniformly over rounding states"
        ),
        "exact_parametric_counterexample_family": [
            parametric_counterexample_case(prefix_power)
            for prefix_power in range(2, 13)
        ],
        "remaining_frozen_orbit_requirement": (
            "exclude long low-controllability carry prefixes for the exact "
            "candidate alpha,A,B orbit"
        ),
        "reports": reports,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({"status": "complete", "output": str(args.output)}))


if __name__ == "__main__":
    main()
