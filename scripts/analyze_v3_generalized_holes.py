#!/usr/bin/env python3
"""Audit generalized Frobenius holes relevant to individual Shellsort passes.

For a current gap d and already applied future gaps A, the relevant quantity is

    U_d(A) = #{k >= 1 : k*d is not in the nonnegative semigroup <A>}.

Unlike the ordinary Frobenius number, U counts only holes on the arithmetic
progression d, rather than measuring the single most distant hole.  Incerpi and
Sedgewick's direct Shellsort lemma bounds the d-pass by O(N * (U_d(A)+1)).

The count is computed exactly from an Apéry set.  Finite-prefix measurements are
conjecture generators, not an asymptotic proof.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

try:
    from scripts.analyze_v3_number_theory import (
        RATIO_DENOMINATOR,
        RATIO_NUMERATOR,
        apery_set,
        exact_positive_gaps,
        semigroup_representations,
        vector_gcd,
    )
except ModuleNotFoundError:  # Direct execution: python scripts/<name>.py
    from analyze_v3_number_theory import (
        RATIO_DENOMINATOR,
        apery_set,
        exact_positive_gaps,
        semigroup_representations,
        vector_gcd,
    )
    from analyze_v3_number_theory import RATIO_NUMERATOR


def fixed_window_forced_hole_lower_bound(step: int, width: int) -> int:
    """Return a rigorous lower bound special to the frozen rational ratio.

    For h_t=floor(alpha*(A/B)^t), clearing B**width in a representation
    k*h_t=sum(c_i*h_(t+i)) shows that every k with

        k*A**width < h_t and A not dividing k

    is necessarily absent.  This finite-prefix value is usually zero because
    the frozen numerator A is very large; asymptotically it is linear in h_t
    for every fixed width.
    """
    if step <= 0 or width <= 0:
        raise ValueError("step and width must be positive")
    last_forced_multiplier = (step - 1) // (RATIO_NUMERATOR**width)
    return (
        last_forced_multiplier
        - last_forced_multiplier // RATIO_NUMERATOR
    )


def generalized_hole_profile(
    step: int, generators: list[int]
) -> tuple[list[int], int] | None:
    """Return missing positive multipliers and reduced Frobenius number.

    Return None when infinitely many such multiples are absent.  If g is the
    common divisor of the generators, finiteness is equivalent to g | step;
    in the finite case the problem is divided by g before constructing the
    Apéry set.
    """
    if step <= 0 or not generators or min(generators) <= 0:
        raise ValueError("step and generators must be positive")
    common_divisor = vector_gcd(generators)
    if step % common_divisor != 0:
        return None
    reduced_step = step // common_divisor
    reduced_generators = sorted({value // common_divisor for value in generators})
    representatives = apery_set(reduced_generators)
    modulus = len(representatives)
    if modulus == 1:
        return [], -1

    orbit_gcd = math.gcd(reduced_step, modulus)
    orbit_length = modulus // orbit_gcd
    orbit_period_value = orbit_length * reduced_step
    missing_multipliers: list[int] = []
    for offset in range(1, orbit_length):
        residue = (offset * reduced_step) % modulus
        deficit = representatives[residue] - offset * reduced_step
        if deficit > 0:
            periods_missing = (
                deficit + orbit_period_value - 1
            ) // orbit_period_value
            missing_multipliers.extend(
                period * orbit_length + offset
                for period in range(periods_missing)
            )
    missing_multipliers.sort()
    return missing_multipliers, max(representatives) - modulus


def generalized_hole_count(step: int, generators: list[int]) -> int | None:
    """Count positive multiples of step absent from the generated semigroup."""
    profile = generalized_hole_profile(step, generators)
    return None if profile is None else len(profile[0])


def log_log_slope(rows: list[dict[str, object]]) -> float | None:
    usable = [
        row for row in rows
        if int(row["base_gap"]) > 1 and int(row["generalized_holes"]) > 0
    ]
    if len(usable) < 2:
        return None
    tail = usable[-min(6, len(usable)):]
    xs = [math.log(int(row["base_gap"])) for row in tail]
    ys = [math.log(int(row["generalized_holes"])) for row in tail]
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    denominator = sum((value - mean_x) ** 2 for value in xs)
    if denominator == 0:
        return None
    return sum(
        (x_value - mean_x) * (y_value - mean_y)
        for x_value, y_value in zip(xs, ys)
    ) / denominator


def quotient_semigroup_generators(missing_multipliers: list[int]) -> list[int]:
    """Recover the minimal generators of {k: k is not missing}.

    Once the last hole is known, every larger integer is present.  Every
    minimal generator is smaller than twice the conductor, so a finite exact
    scan suffices.
    """
    if not missing_multipliers:
        return [1]
    missing = set(missing_multipliers)
    conductor = missing_multipliers[-1] + 1
    present = [value == 0 or value not in missing for value in range(2 * conductor)]
    generators: list[int] = []
    for value in range(1, 2 * conductor):
        if not present[value]:
            continue
        decomposable = any(
            present[left] and present[value - left]
            for left in range(1, value)
        )
        if not decomposable:
            generators.append(value)
    return generators


def best_coprime_generator_pair(generators: list[int]) -> tuple[int, int] | None:
    """Return the coprime pair with the smallest two-generator genus bound."""
    candidates = [
        (left, right)
        for index, left in enumerate(generators)
        for right in generators[index + 1 :]
        if math.gcd(left, right) == 1
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda pair: (pair[0] - 1) * (pair[1] - 1))


def audit_width(
    gaps: list[int], width: int, max_apery_modulus: int
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    infinite_count = 0
    skipped_large_modulus = 0
    for base in range(len(gaps) - width):
        step = gaps[base]
        generators = gaps[base + 1 : base + 1 + width]
        common_divisor = vector_gcd(generators)
        if step % common_divisor != 0:
            infinite_count += 1
            continue
        reduced_modulus = min(generators) // common_divisor
        if reduced_modulus > max_apery_modulus:
            skipped_large_modulus += 1
            continue
        profile = generalized_hole_profile(step, generators)
        if profile is None:
            raise AssertionError("finite generalized-hole case was misclassified")
        missing_multipliers, reduced_frobenius = profile
        holes = len(missing_multipliers)
        quotient_generators = quotient_semigroup_generators(missing_multipliers)
        coprime_pair = best_coprime_generator_pair(quotient_generators)
        quotient_generator_witnesses = []
        reduced_generators = [value // common_divisor for value in generators]
        reduced_step = step // common_divisor
        witnessed_multipliers = quotient_generators[:5]
        witnessed_coefficients = semigroup_representations(
            [multiplier * reduced_step for multiplier in witnessed_multipliers],
            reduced_generators,
        )
        for multiplier, coefficients in zip(
            witnessed_multipliers, witnessed_coefficients
        ):
            if coefficients is None:
                raise AssertionError("quotient generator lacks a representation")
            quotient_generator_witnesses.append({
                "multiplier": multiplier,
                "future_gap_coefficients": coefficients,
            })
        maximum_missing_multiplier = (
            missing_multipliers[-1] if missing_multipliers else 0
        )
        quotient_conductor = maximum_missing_multiplier + 1 if holes else 0
        denominator_scale = step / (RATIO_DENOMINATOR**width)
        row: dict[str, object] = {
            "base_index": base,
            "base_gap": step,
            "window_gcd": common_divisor,
            "smallest_reduced_generator": reduced_modulus,
            "generalized_holes": holes,
            "maximum_missing_multiplier": maximum_missing_multiplier,
            "quotient_conductor": quotient_conductor,
            "h_over_B_to_m": denominator_scale,
            "conductor_over_h_over_B_to_m": (
                quotient_conductor / denominator_scale
            ),
            "hole_density_through_last_hole": (
                holes / maximum_missing_multiplier
                if maximum_missing_multiplier else 0.0
            ),
            "quotient_semigroup_minimal_generators": quotient_generators,
            "best_coprime_generator_pair": list(coprime_pair) if coprime_pair else None,
            "two_generator_genus_upper_bound": (
                (coprime_pair[0] - 1) * (coprime_pair[1] - 1) // 2
                if coprime_pair else None
            ),
            "smallest_quotient_generator_witnesses": quotient_generator_witnesses,
            "reduced_semigroup_frobenius": reduced_frobenius,
            "holes_over_sqrt_base_gap": holes / math.sqrt(step),
            "rigorous_fixed_window_forced_holes": (
                fixed_window_forced_hole_lower_bound(step, width)
            ),
        }
        if step > 1 and holes > 0:
            row["absolute_log_exponent"] = math.log(holes) / math.log(step)
        rows.append(row)

    local_slopes = []
    for previous, current in zip(rows, rows[1:]):
        previous_gap = int(previous["base_gap"])
        current_gap = int(current["base_gap"])
        previous_holes = int(previous["generalized_holes"])
        current_holes = int(current["generalized_holes"])
        if previous_gap > 1 and previous_holes > 0 and current_holes > 0:
            local_slopes.append({
                "from_base_index": int(previous["base_index"]),
                "to_base_index": int(current["base_index"]),
                "slope": (
                    math.log(current_holes / previous_holes)
                    / math.log(current_gap / previous_gap)
                ),
            })
    return {
        "width": width,
        "finite_windows_computed": len(rows),
        "infinite_windows_before_modulus_cutoff": infinite_count,
        "skipped_large_apery_modulus": skipped_large_modulus,
        "tail_log_log_slope_last_at_most_six": log_log_slope(rows),
        "last_local_slopes": local_slopes[-5:],
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terms", type=int, default=32)
    parser.add_argument("--windows", type=int, nargs="+", default=(4, 6, 8, 14))
    parser.add_argument("--max-apery-modulus", type=int, default=600_000)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("result/v3/generalized-hole-audit-v3.json"),
    )
    args = parser.parse_args()
    if min(args.windows) < 2:
        raise ValueError("every window must contain at least two future gaps")
    if args.terms <= max(args.windows):
        raise ValueError("--terms must leave a complete future window")

    gaps = exact_positive_gaps(args.terms)
    reports = {
        str(width): audit_width(gaps, width, args.max_apery_modulus)
        for width in args.windows
    }
    payload = {
        "schema_version": 1,
        "status": "finite_exact_prefix_evidence_not_asymptotic_proof",
        "quantity": (
            "U_t(m)=number of positive multiples of h_t not representable by "
            "h_(t+1),...,h_(t+m)"
        ),
        "conditional_shellsort_theorem": {
            "pass_bound": "cost_t <= O(N*(U_t(m)+1))",
            "if_U_is_O_h_to_kappa": (
                "T(N)=O(N^((2*kappa+1)/(kappa+1))+N*log(N))"
            ),
            "strictly_below_four_thirds_when": "kappa < 1/2",
        },
        "fixed_window_asymptotic_obstruction": {
            "statement": (
                "for every fixed m, U_t(m) >= floor((h_t-1)/A^m) "
                "- floor(floor((h_t-1)/A^m)/A)"
            ),
            "consequence": "U_t(m)=Omega(h_t) for fixed m",
            "ratio_numerator_A": RATIO_NUMERATOR,
        },
        "sequence": {
            "positive_terms_generated": len(gaps),
            "max_apery_modulus": args.max_apery_modulus,
        },
        "windows": reports,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({
        "status": "complete",
        "output": str(args.output),
        "windows": list(reports),
    }))


if __name__ == "__main__":
    main()
