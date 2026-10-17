#!/usr/bin/env python3
"""Audit exact gcd and numerical-semigroup structure of the V3 sequence.

All gaps are generated with integer arithmetic from the frozen rational
constants.  Frobenius numbers are computed through the Apéry-set shortest
path formulation and are intentionally restricted by the smallest generator.
The output is finite-prefix evidence, never a proof for the infinite sequence.
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
import statistics
from pathlib import Path


ALPHA_NUMERATOR = 420574650882923
ALPHA_DENOMINATOR = 7668945023518835
RATIO_NUMERATOR = 582942583375009
RATIO_DENOMINATOR = 250000000000000


def exact_positive_gaps(count: int) -> list[int]:
    numerator = ALPHA_NUMERATOR
    denominator = ALPHA_DENOMINATOR
    gaps: list[int] = []
    while len(gaps) < count:
        gap = numerator // denominator
        if gap > 0:
            gaps.append(gap)
        numerator *= RATIO_NUMERATOR
        denominator *= RATIO_DENOMINATOR
    return gaps


def vector_gcd(values: list[int]) -> int:
    result = 0
    for value in values:
        result = math.gcd(result, value)
    return result


def apery_set(generators: list[int]) -> list[int]:
    """Return minimum semigroup representatives modulo the smallest generator."""
    generators = sorted(set(generators))
    if vector_gcd(generators) != 1:
        raise ValueError("Apéry set requires a primitive generator vector")
    modulus = generators[0]
    if modulus == 1:
        return [0]
    distances: list[int | None] = [None] * modulus
    distances[0] = 0
    queue: list[tuple[int, int]] = [(0, 0)]
    steps = generators[1:]
    while queue:
        distance, residue = heapq.heappop(queue)
        if distances[residue] != distance:
            continue
        for step in steps:
            target = (residue + step) % modulus
            candidate = distance + step
            previous = distances[target]
            if previous is None or candidate < previous:
                distances[target] = candidate
                heapq.heappush(queue, (candidate, target))
    if any(value is None for value in distances):
        raise RuntimeError("primitive generators did not reach every residue")
    return [int(value) for value in distances]


def semigroup_representations(
    values: list[int], generators: list[int]
) -> list[list[int] | None]:
    """Return exact representations for many targets using one shortest-path run.

    Coefficient vectors are aligned with the sorted unique generators.  The
    shortest representative of each target residue is recovered with Dijkstra
    predecessors; any remaining multiple of the modulus is supplied by the
    smallest generator.  An absent target receives None.
    """
    if any(value < 0 for value in values) or not generators or min(generators) <= 0:
        raise ValueError("values must be nonnegative and generators positive")
    ordered = sorted(set(generators))
    if vector_gcd(ordered) != 1:
        raise ValueError("representation helper requires primitive generators")
    modulus = ordered[0]
    if modulus == 1:
        return [[value] + [0] * (len(ordered) - 1) for value in values]

    distances: list[int | None] = [None] * modulus
    predecessors: list[tuple[int, int] | None] = [None] * modulus
    distances[0] = 0
    queue: list[tuple[int, int]] = [(0, 0)]
    for_index = list(enumerate(ordered[1:], 1))
    while queue:
        distance, residue = heapq.heappop(queue)
        if distances[residue] != distance:
            continue
        for generator_index, step in for_index:
            target = (residue + step) % modulus
            candidate = distance + step
            previous = distances[target]
            if previous is None or candidate < previous:
                distances[target] = candidate
                predecessors[target] = (residue, generator_index)
                heapq.heappush(queue, (candidate, target))

    results: list[list[int] | None] = []
    for value in values:
        coefficients = [0] * len(ordered)
        residue = value % modulus
        representative = distances[residue]
        if representative is None or value < representative:
            results.append(None)
            continue
        coefficients[0] = (value - representative) // modulus
        while residue != 0:
            predecessor = predecessors[residue]
            if predecessor is None:
                raise RuntimeError("reachable Apéry residue lost its predecessor")
            previous_residue, generator_index = predecessor
            coefficients[generator_index] += 1
            residue = previous_residue
        if sum(c * g for c, g in zip(coefficients, ordered)) != value:
            raise AssertionError("reconstructed semigroup representation is not exact")
        results.append(coefficients)
    return results


def semigroup_representation(value: int, generators: list[int]) -> list[int] | None:
    """Return one exact representation; see :func:`semigroup_representations`."""
    return semigroup_representations([value], generators)[0]


def frobenius_number(generators: list[int]) -> int:
    """Return F(a) using minimum representatives modulo the smallest a."""
    distances = apery_set(generators)
    return max(distances) - len(distances)


def quantiles(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    ordered = sorted(values)
    return {
        "minimum": ordered[0],
        "median": statistics.median(ordered),
        "maximum": ordered[-1],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terms", type=int, default=5000)
    parser.add_argument("--windows", type=int, nargs="+", default=(3, 4, 5, 6, 8, 12, 14))
    parser.add_argument("--max-apery-modulus", type=int, default=20000)
    parser.add_argument(
        "--output", type=Path, default=Path("result/v3/number-theory-audit-v3.json")
    )
    args = parser.parse_args()
    if args.terms < max(args.windows) + 2:
        raise ValueError("--terms must leave at least one complete future window")

    gaps = exact_positive_gaps(args.terms)
    gcd_lengths: list[int] = []
    unresolved = 0
    for base in range(len(gaps) - 1):
        running_gcd = 0
        resolved = False
        for length, gap in enumerate(gaps[base + 1 :], 1):
            running_gcd = math.gcd(running_gcd, gap)
            if running_gcd == 1:
                gcd_lengths.append(length)
                resolved = True
                break
        if not resolved:
            unresolved += 1

    window_reports: dict[str, object] = {}
    for width in args.windows:
        nonprimitive = []
        frobenius_rows = []
        for base in range(len(gaps) - width):
            window = gaps[base + 1 : base + 1 + width]
            common_divisor = vector_gcd(window)
            if common_divisor != 1:
                nonprimitive.append({
                    "base_index": base,
                    "base_gap": gaps[base],
                    "gcd": common_divisor,
                })
                continue
            if window[0] > args.max_apery_modulus:
                continue
            value = frobenius_number(window)
            product_scale = math.exp(sum(math.log(item) for item in window) / (width - 1))
            rho = width / (width - 1)
            frobenius_rows.append({
                "base_index": base,
                "base_gap": gaps[base],
                "smallest_generator": window[0],
                "frobenius": value,
                "normalized_by_product": value / product_scale,
                "normalized_by_base_gap": value / (gaps[base] ** rho),
            })
        window_reports[str(width)] = {
            "windows_checked": len(gaps) - width,
            "nonprimitive_count": len(nonprimitive),
            "first_nonprimitive_windows": nonprimitive[:10],
            "apery_windows_computed": len(frobenius_rows),
            "frobenius_over_product_scale": quantiles(
                [float(row["normalized_by_product"]) for row in frobenius_rows]
            ),
            "frobenius_over_base_gap_power": quantiles(
                [float(row["normalized_by_base_gap"]) for row in frobenius_rows]
            ),
            "apery_rows": frobenius_rows,
        }

    payload = {
        "schema_version": 1,
        "status": "finite_exact_prefix_evidence_not_infinite_proof",
        "sequence": {
            "alpha": [ALPHA_NUMERATOR, ALPHA_DENOMINATOR],
            "ratio": [RATIO_NUMERATOR, RATIO_DENOMINATOR],
            "positive_terms_audited": len(gaps),
            "first_gaps": gaps[:16],
            "last_gap": gaps[-1],
        },
        "minimum_future_window_for_gcd_one": {
            "resolved_bases": len(gcd_lengths),
            "unresolved_tail_bases": unresolved,
            "maximum": max(gcd_lengths),
            "histogram": {
                str(length): gcd_lengths.count(length) for length in sorted(set(gcd_lengths))
            },
        },
        "windows": window_reports,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({
        "status": "complete",
        "output": str(args.output),
        "terms": len(gaps),
        "max_gcd_window": max(gcd_lengths),
    }))


if __name__ == "__main__":
    main()
