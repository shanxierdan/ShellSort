#!/usr/bin/env python3
"""Audit the exact compound/carry reduction behind quotient intervals.

For d=h_t and a_i=h_(t+i), clear the common denominator B**m and set

    q_i = A**i * B**(m-i)
    v_i = B**(m-i) * (B**i*a_i - A**i*d).

Every certificate k*d=sum(c_i*a_i) then satisfies

    sum(c_i*q_i) = k*B**m-D
    sum(c_i*v_i) = D*d.

The divided q-coordinates form the compound sequence

    q_i/A = A**(i-1)*B**(m-i).

Its integer kernel has the adjacent carry basis A*unit_i-B*unit_(i+1).
Applying one such carry preserves q and changes v by exactly
-B**m times the local rounding error.  This script certifies those identities,
recovers the carry coordinates of stored quotient witnesses, and audits finite
error-gcd recovery.  It does not claim the still-open uniform interval theorem.
"""

from __future__ import annotations

import argparse
from functools import lru_cache
import json
import math
from pathlib import Path

try:
    from scripts.analyze_v3_number_theory import (
        RATIO_DENOMINATOR,
        RATIO_NUMERATOR,
        exact_positive_gaps,
        vector_gcd,
    )
except ModuleNotFoundError:  # Direct execution: python scripts/<name>.py
    from analyze_v3_number_theory import (
        RATIO_DENOMINATOR,
        RATIO_NUMERATOR,
        exact_positive_gaps,
        vector_gcd,
    )


def compound_weights(width: int, numerator: int, denominator: int) -> list[int]:
    """Return B^(m-1), A*B^(m-2), ..., A^(m-1)."""
    if width < 1 or numerator <= denominator or denominator <= 0:
        raise ValueError("require width>=1 and numerator>denominator>0")
    if math.gcd(numerator, denominator) != 1:
        raise ValueError("compound weights require a reduced rational ratio")
    return [
        numerator**index * denominator ** (width - 1 - index)
        for index in range(width)
    ]


def compound_frobenius(width: int, numerator: int, denominator: int) -> int:
    """Return the exact Frobenius number of the geometric compound sequence."""
    weights = compound_weights(width, numerator, denominator)
    if width == 1:
        return -1 if weights[0] == 1 else 0
    return (denominator - 1) * sum(weights[1:]) - weights[0]


def compound_normal_form(
    value: int, width: int, numerator: int, denominator: int
) -> list[int] | None:
    """Return the canonical compound representation, or None when absent.

    Coefficients 2..m lie in [0,B-1].  Successively reducing modulo B from
    the largest generator uniquely determines them; the remaining first
    coefficient is nonnegative exactly when ``value`` belongs to the
    compound numerical semigroup.
    """
    if value < 0:
        return None
    weights = compound_weights(width, numerator, denominator)
    if width == 1:
        return [value] if weights[0] == 1 else None
    remaining = value
    coefficients = [0] * width
    inverse_numerator = pow(numerator, -1, denominator)
    for index in range(width - 1, 0, -1):
        inverse_power = pow(inverse_numerator, index, denominator)
        digit = (remaining * inverse_power) % denominator
        coefficients[index] = digit
        difference = remaining - digit * weights[index]
        if difference % denominator != 0:
            raise AssertionError("compound digit did not clear one B-adic level")
        remaining = difference // denominator
        weights = [weight // denominator for weight in weights[:-1]]
    coefficients[0] = remaining
    if coefficients[0] < 0:
        return None
    original_weights = compound_weights(width, numerator, denominator)
    if sum(c * w for c, w in zip(coefficients, original_weights)) != value:
        raise AssertionError("compound normal form is not exact")
    return coefficients


def carry_coordinates(
    step: int,
    generators: list[int],
    numerator: int,
    denominator: int,
) -> tuple[list[int], list[int], list[int]]:
    """Return E_i, q_i and v_i for the exact two-coordinate reduction."""
    if step <= 0 or not generators or min(generators) <= 0:
        raise ValueError("step and generators must be positive")
    width = len(generators)
    errors = []
    quotient = []
    carries = []
    for index, gap in enumerate(generators, 1):
        error = denominator**index * gap - numerator**index * step
        if not (-denominator**index < error < numerator**index):
            raise AssertionError("cleared rounding error escaped its exact bound")
        errors.append(error)
        quotient.append(numerator**index * denominator ** (width - index))
        carries.append(denominator ** (width - index) * error)
    return errors, quotient, carries


def local_rounding_errors(
    generators: list[int], numerator: int, denominator: int
) -> list[int]:
    """Return B*a_(i+1)-A*a_i inside a future-gap window."""
    return [
        denominator * right - numerator * left
        for left, right in zip(generators, generators[1:])
    ]


def recover_adjacent_carries(
    coefficients: list[int],
    canonical: list[int],
    numerator: int,
    denominator: int,
) -> list[int]:
    """Recover z from c-c0=sum z_i(A*unit_i-B*unit_(i+1))."""
    if len(coefficients) != len(canonical):
        raise ValueError("coefficient vectors must have the same length")
    if len(coefficients) == 1:
        if coefficients != canonical:
            raise ValueError("one-dimensional compound representations are unique")
        return []
    difference = [left - right for left, right in zip(coefficients, canonical)]
    carries: list[int] = []
    numerator_value = difference[0]
    if numerator_value % numerator != 0:
        raise ValueError("difference is not in the adjacent carry lattice")
    carries.append(numerator_value // numerator)
    for index in range(1, len(coefficients) - 1):
        numerator_value = difference[index] + denominator * carries[-1]
        if numerator_value % numerator != 0:
            raise ValueError("difference is not in the adjacent carry lattice")
        carries.append(numerator_value // numerator)
    if difference[-1] != -denominator * carries[-1]:
        raise ValueError("difference has a nonzero final carry boundary")
    return carries


def _ceil_div(numerator: int, denominator: int) -> int:
    return -((-numerator) // denominator)


def apply_adjacent_carries(
    canonical: list[int],
    carries: list[int],
    numerator: int,
    denominator: int,
) -> list[int]:
    """Apply the q-kernel carry vector and return the resulting coefficients."""
    if len(carries) != max(0, len(canonical) - 1):
        raise ValueError("a width-m vector requires m-1 adjacent carries")
    coefficients = canonical.copy()
    for index, value in enumerate(carries):
        coefficients[index] += numerator * value
        coefficients[index + 1] -= denominator * value
    return coefficients


def solve_bounded_error_carries(
    canonical: list[int],
    quotient_coordinates: list[int],
    local_errors: list[int],
    error_target: int,
    numerator: int,
    denominator: int,
    max_states: int = 1_000_000,
) -> list[int] | None:
    """Solve the exact carry equation subject to nonnegative coefficients.

    The q-coordinate is fixed, so every feasible coefficient vector is the
    canonical vector plus adjacent carries.  Dynamic programming walks the
    bidiagonal nonnegativity constraints and tracks the remaining bounded
    error.  This is an exact finite constructor intended for audits; the
    asymptotic theorem still requires a uniform mathematical state bound.
    """
    width = len(canonical)
    if width != len(quotient_coordinates) or len(local_errors) != width - 1:
        raise ValueError("carry-system dimensions are inconsistent")
    if width == 1:
        return [] if error_target == 0 else None
    quotient_sum = sum(
        coefficient * value
        for coefficient, value in zip(canonical, quotient_coordinates)
    )
    states_visited = 0

    @lru_cache(maxsize=None)
    def search(
        index: int, previous_carry: int, remaining_error: int
    ) -> tuple[int, ...] | None:
        nonlocal states_visited
        states_visited += 1
        if states_visited > max_states:
            raise RuntimeError("bounded-error carry search exceeded --max-states")
        if index == width - 1:
            final_coefficient = canonical[-1] - denominator * previous_carry
            return () if final_coefficient >= 0 and remaining_error == 0 else None

        base = canonical[index]
        if index > 0:
            base -= denominator * previous_carry
        maximum_coefficient = quotient_sum // quotient_coordinates[index]
        lower = _ceil_div(-base, numerator)
        upper = (maximum_coefficient - base) // numerator
        if lower > upper:
            return None
        error = local_errors[index]
        if error:
            pivot = min(upper, max(lower, round(remaining_error / error)))
        else:
            pivot = min(upper, max(lower, 0))
        maximum_radius = max(pivot - lower, upper - pivot)
        for radius in range(maximum_radius + 1):
            candidates = (pivot,) if radius == 0 else (pivot - radius, pivot + radius)
            for carry in candidates:
                if carry < lower or carry > upper:
                    continue
                suffix = search(
                    index + 1,
                    carry,
                    remaining_error - carry * error,
                )
                if suffix is not None:
                    return (carry,) + suffix
        return None

    result = search(0, 0, error_target)
    if result is None:
        return None
    carries = list(result)
    coefficients = apply_adjacent_carries(
        canonical, carries, numerator, denominator
    )
    if any(value < 0 for value in coefficients):
        raise AssertionError("carry solver returned a negative coefficient")
    if sum(c * q for c, q in zip(coefficients, quotient_coordinates)) != quotient_sum:
        raise AssertionError("carry solver changed the q-coordinate")
    if sum(z * error for z, error in zip(carries, local_errors)) != error_target:
        raise AssertionError("carry solver missed its error target")
    return carries


def construct_certificate_via_carries(
    step: int,
    generators: list[int],
    multiplier: int,
    numerator: int,
    denominator: int,
    maximum_abs_D: int,
    max_states: int = 1_000_000,
) -> dict[str, object] | None:
    """Construct a positive quotient certificate from normal form and carries."""
    if multiplier <= 0 or maximum_abs_D < 0:
        raise ValueError("multiplier must be positive and D bound nonnegative")
    width = len(generators)
    _, quotient, carry_values = carry_coordinates(
        step, generators, numerator, denominator
    )
    local_errors = local_rounding_errors(generators, numerator, denominator)
    residue = (multiplier * denominator**width) % numerator
    minimum_lift = _ceil_div(-maximum_abs_D - residue, numerator)
    maximum_lift = (maximum_abs_D - residue) // numerator
    candidate_Ds = sorted(
        (residue + numerator * lift for lift in range(minimum_lift, maximum_lift + 1)),
        key=lambda value: (abs(value), value),
    )
    for cleared_carry in candidate_Ds:
        quotient_sum = multiplier * denominator**width - cleared_carry
        if quotient_sum < 0 or quotient_sum % numerator != 0:
            continue
        compound_value = quotient_sum // numerator
        canonical = compound_normal_form(
            compound_value, width, numerator, denominator
        )
        if canonical is None:
            continue
        residual = (
            sum(c * value for c, value in zip(canonical, carry_values))
            - cleared_carry * step
        )
        if residual % denominator**width != 0:
            raise AssertionError("candidate normal form broke B^m divisibility")
        error_target = residual // denominator**width
        carries = solve_bounded_error_carries(
            canonical,
            quotient,
            local_errors,
            error_target,
            numerator,
            denominator,
            max_states=max_states,
        )
        if carries is None:
            continue
        coefficients = apply_adjacent_carries(
            canonical, carries, numerator, denominator
        )
        if sum(c * gap for c, gap in zip(coefficients, generators)) != multiplier * step:
            raise AssertionError("constructed coefficients are not a quotient certificate")
        return {
            "multiplier": multiplier,
            "cleared_carry_D": cleared_carry,
            "compound_value": compound_value,
            "canonical_coefficients": canonical,
            "adjacent_carries": carries,
            "future_gap_coefficients": coefficients,
            "error_target": error_target,
        }
    return None


def decompose_certificate(
    step: int,
    generators: list[int],
    multiplier: int,
    coefficients: list[int],
    numerator: int,
    denominator: int,
) -> dict[str, object]:
    """Decompose one exact positive certificate into normal form plus carries."""
    if len(generators) != len(coefficients):
        raise ValueError("generator and coefficient lengths differ")
    if any(coefficient < 0 for coefficient in coefficients):
        raise ValueError("certificate coefficients must be nonnegative")
    if sum(c * gap for c, gap in zip(coefficients, generators)) != multiplier * step:
        raise ValueError("input is not an exact quotient certificate")
    width = len(generators)
    _, quotient, carry_values = carry_coordinates(
        step, generators, numerator, denominator
    )
    cleared_carry = (
        multiplier * denominator**width
        - sum(c * q for c, q in zip(coefficients, quotient))
    )
    if sum(c * value for c, value in zip(coefficients, carry_values)) != cleared_carry * step:
        raise AssertionError("certificate failed its two-coordinate identity")
    quotient_sum = multiplier * denominator**width - cleared_carry
    if quotient_sum % numerator != 0:
        raise AssertionError("q-coordinate did not have its forced A divisor")
    compound_value = quotient_sum // numerator
    canonical = compound_normal_form(
        compound_value, width, numerator, denominator
    )
    if canonical is None:
        raise AssertionError("existing q representation has no compound normal form")
    adjacent_carries = recover_adjacent_carries(
        coefficients, canonical, numerator, denominator
    )
    local_errors = local_rounding_errors(generators, numerator, denominator)
    residual = (
        sum(c * value for c, value in zip(canonical, carry_values))
        - cleared_carry * step
    )
    if residual % denominator**width != 0:
        raise AssertionError("normal-form residual is not a whole carry block")
    error_target = residual // denominator**width
    if sum(z * error for z, error in zip(adjacent_carries, local_errors)) != error_target:
        raise AssertionError("bounded-error carry equation failed")
    return {
        "multiplier": multiplier,
        "cleared_carry_D": cleared_carry,
        "compound_value": compound_value,
        "canonical_coefficients": canonical,
        "adjacent_carries": adjacent_carries,
        "error_target": error_target,
        "error_gcd": vector_gcd([abs(value) for value in local_errors]),
        "max_abs_adjacent_carry": max(map(abs, adjacent_carries), default=0),
    }


def _recovery_summary(lengths: list[int], total: int) -> dict[str, object]:
    histogram = {
        str(length): lengths.count(length) for length in sorted(set(lengths))
    }
    percentile_99 = None
    if lengths:
        ordered = sorted(lengths)
        percentile_99 = ordered[math.ceil(0.99 * len(ordered)) - 1]
    return {
        "bases_checked": total,
        "resolved_bases": len(lengths),
        "unresolved_tail_bases": total - len(lengths),
        "maximum_resolved_prefix": max(lengths, default=None),
        "p99_resolved_prefix": percentile_99,
        "histogram": histogram,
    }


def prefix_recovery_audit(errors: list[int]) -> dict[str, object]:
    """Measure how soon each finite suffix attains gcd one and both signs.

    Bases near the end can remain unresolved merely because the audited prefix
    stops.  They are reported separately instead of being treated as failures.
    """
    gcd_lengths: list[int] = []
    sign_lengths: list[int] = []
    for start in range(len(errors)):
        running_gcd = 0
        has_positive = False
        has_negative = False
        gcd_resolved = False
        sign_resolved = False
        for end in range(start, len(errors)):
            error = errors[end]
            length = end - start + 1
            running_gcd = math.gcd(running_gcd, abs(error))
            has_positive = has_positive or error > 0
            has_negative = has_negative or error < 0
            if not gcd_resolved and running_gcd == 1:
                gcd_lengths.append(length)
                gcd_resolved = True
            if not sign_resolved and has_positive and has_negative:
                sign_lengths.append(length)
                sign_resolved = True
            if gcd_resolved and sign_resolved:
                break
    return {
        "minimum_prefix_for_error_gcd_one": _recovery_summary(
            gcd_lengths, len(errors)
        ),
        "minimum_prefix_for_both_error_signs": _recovery_summary(
            sign_lengths, len(errors)
        ),
    }


def error_gcd_audit(gaps: list[int], widths: list[int]) -> dict[str, object]:
    errors = local_rounding_errors(
        gaps, RATIO_NUMERATOR, RATIO_DENOMINATOR
    )
    zero_run = 0
    maximum_zero_run = 0
    for error in errors:
        if error == 0:
            zero_run += 1
            maximum_zero_run = max(maximum_zero_run, zero_run)
        else:
            zero_run = 0
    reports: dict[str, object] = {}
    for width in widths:
        gcds = [
            vector_gcd([abs(value) for value in errors[start : start + width]])
            for start in range(len(errors) - width + 1)
        ]
        reports[str(width)] = {
            "windows_checked": len(gcds),
            "gcd_not_one": sum(value != 1 for value in gcds),
            "maximum_gcd": max(gcds),
        }
    return {
        "zero_error_count": sum(value == 0 for value in errors),
        "maximum_zero_error_run": maximum_zero_run,
        "windows": reports,
        **prefix_recovery_audit(errors),
    }


def audit_stored_witnesses(
    audit_path: Path, gaps: list[int]
) -> list[dict[str, object]]:
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for width_text, report in payload["windows"].items():
        width = int(width_text)
        for row in report["rows"]:
            base = int(row["base_index"])
            step = gaps[base]
            generators = gaps[base + 1 : base + 1 + width]
            for witness in row.get("smallest_quotient_generator_witnesses", []):
                decomposition = decompose_certificate(
                    step,
                    generators,
                    int(witness["multiplier"]),
                    [int(value) for value in witness["future_gap_coefficients"]],
                    RATIO_NUMERATOR,
                    RATIO_DENOMINATOR,
                )
                decomposition.update({
                    "base_index": base,
                    "base_gap": step,
                    "width": width,
                })
                rows.append(decomposition)
    return rows


def audit_small_model_interval(max_states: int) -> dict[str, object]:
    """Construct every certificate in one exact reduced-ratio demo interval."""
    step = 131
    generators = [328, 821, 2054, 5135]
    first = 223
    last = 445
    maximum_abs_D = 25
    maximum_used_D = 0
    maximum_adjacent_carry = 0
    endpoint_witnesses = []
    for multiplier in range(first, last + 1):
        witness = construct_certificate_via_carries(
            step,
            generators,
            multiplier,
            5,
            2,
            maximum_abs_D=maximum_abs_D,
            max_states=max_states,
        )
        if witness is None:
            raise AssertionError("carry constructor left a hole in the demo interval")
        maximum_used_D = max(maximum_used_D, abs(int(witness["cleared_carry_D"])))
        maximum_adjacent_carry = max(
            maximum_adjacent_carry,
            max(map(abs, witness["adjacent_carries"]), default=0),
        )
        if multiplier in {first, last}:
            endpoint_witnesses.append(witness)
    return {
        "status": "complete_exact_constructor_demo_not_v3_asymptotic_proof",
        "ratio": [5, 2],
        "alpha": [7, 13],
        "base_gap": step,
        "future_gaps": generators,
        "interval": [first, last],
        "certificates_constructed": last - first + 1,
        "maximum_allowed_abs_D": maximum_abs_D,
        "maximum_used_abs_D": maximum_used_D,
        "maximum_abs_adjacent_carry": maximum_adjacent_carry,
        "endpoint_witnesses": endpoint_witnesses,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terms", type=int, default=5000)
    parser.add_argument("--error-windows", type=int, nargs="+", default=(4, 8, 14, 32))
    parser.add_argument(
        "--witness-input",
        type=Path,
        default=Path("result/v3/generalized-hole-audit-v3-extended.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("result/v3/carry-interval-audit-v3.json"),
    )
    parser.add_argument("--include-small-model-demo", action="store_true")
    parser.add_argument("--max-states", type=int, default=1_000_000)
    args = parser.parse_args()
    if args.terms < 2:
        raise ValueError("--terms must be at least two")
    if min(args.error_windows) < 1 or max(args.error_windows) >= args.terms:
        raise ValueError("error windows must fit inside generated gaps")
    gaps = exact_positive_gaps(args.terms)
    witnesses = audit_stored_witnesses(args.witness_input, gaps)
    payload = {
        "schema_version": 1,
        "status": "exact_finite_carry_certificates_not_uniform_interval_proof",
        "sequence": {
            "ratio": [RATIO_NUMERATOR, RATIO_DENOMINATOR],
            "positive_terms_audited": len(gaps),
        },
        "exact_reduction": {
            "compound_q_coordinates": "q_i/A=A^(i-1)*B^(m-i)",
            "adjacent_q_kernel": "A*unit_i-B*unit_(i+1)",
            "v_change_per_carry": "-B^m*e_(t+i)",
            "remaining_target": (
                "prove a uniform nonnegative solution of the bounded-error "
                "carry equation over a consecutive multiplier interval"
            ),
        },
        "error_gcd_prefix_audit": error_gcd_audit(gaps, args.error_windows),
        "stored_witness_decompositions": witnesses,
        "stored_witnesses_verified": len(witnesses),
    }
    if args.include_small_model_demo:
        payload["small_model_interval_demo"] = audit_small_model_interval(
            args.max_states
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({
        "status": "complete",
        "output": str(args.output),
        "stored_witnesses_verified": len(witnesses),
    }))


if __name__ == "__main__":
    main()
