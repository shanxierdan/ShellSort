#!/usr/bin/env python3
"""Certify the bounded integer relations forced by the V3 rational ratio.

For a fixed future window, let x_i be its first m-1 gaps and set

    e_i = B*x_(i+1) - A*x_i.

Every e_i is an integer in (-B, A).  Eliminating the common inhomogeneous
coordinate from these recurrences gives m-3 independent exact relations
z*x = 0 whose coefficients are bounded independently of the base index.

The script verifies those identities with exact integer arithmetic and reports
their size after the Kannan-lattice normalization.  The finite report is a
reproducible diagnostic; the asymptotic consequence is proved in
docs/固定窗口关键前提审计.md.
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


def recurrence_rows(values: list[int]) -> tuple[list[list[int]], list[int]]:
    """Return r_i and e_i with r_i dot values = e_i exactly."""
    dimension = len(values)
    rows: list[list[int]] = []
    errors: list[int] = []
    for index in range(dimension - 1):
        row = [0] * dimension
        row[index] = -RATIO_NUMERATOR
        row[index + 1] = RATIO_DENOMINATOR
        error = (
            RATIO_DENOMINATOR * values[index + 1]
            - RATIO_NUMERATOR * values[index]
        )
        if not (-RATIO_DENOMINATOR < error < RATIO_NUMERATOR):
            raise AssertionError("rational-rounding error escaped its exact interval")
        if sum(coefficient * value for coefficient, value in zip(row, values)) != error:
            raise AssertionError("recurrence identity failed")
        rows.append(row)
        errors.append(error)
    return rows, errors


def bounded_relation_vectors(values: list[int]) -> list[list[int]]:
    """Return len(values)-2 independent bounded vectors orthogonal to values.

    If some recurrence error e_p is nonzero, the coefficient-space vectors
    e_i unit_p - e_p unit_i are visibly independent for i != p.  The map from
    recurrence coefficients to gap coefficients is injective because its
    bidiagonal matrix has full row rank.  If every error is zero, the
    recurrence rows themselves are independent exact relations.
    """
    rows, errors = recurrence_rows(values)
    target_count = len(values) - 2
    pivot = next((index for index, error in enumerate(errors) if error != 0), None)
    if pivot is None:
        relations = rows[:target_count]
    else:
        relations = []
        for index in range(len(errors)):
            if index == pivot:
                continue
            relation = [
                errors[index] * rows[pivot][column]
                - errors[pivot] * rows[index][column]
                for column in range(len(values))
            ]
            relations.append(relation)
    if len(relations) != target_count:
        raise AssertionError("wrong number of independent relations")
    for relation in relations:
        if not any(relation):
            raise AssertionError("constructed a zero relation")
        if sum(coefficient * value for coefficient, value in zip(relation, values)) != 0:
            raise AssertionError("exact integer relation failed")
    return relations


def log_euclidean_norm(values: list[int]) -> float:
    squared_norm = sum(value * value for value in values)
    if squared_norm == 0:
        raise ValueError("the zero vector has no logarithmic norm")
    return 0.5 * math.log(squared_norm)


def summarize(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "minimum": ordered[0],
        "median": statistics.median(ordered),
        "maximum": ordered[-1],
    }


def audit_window(gaps: list[int], width: int) -> dict[str, object]:
    relation_count = width - 3
    rows: list[dict[str, object]] = []
    coefficient_limit = 2 * max(RATIO_NUMERATOR, RATIO_DENOMINATOR) ** 2
    for base in range(len(gaps) - width):
        window = gaps[base + 1 : base + 1 + width]
        values = window[:-1]
        relations = bounded_relation_vectors(values)
        if len(relations) != relation_count:
            raise AssertionError("relation rank certificate has the wrong size")

        product_root_log = sum(math.log(value) for value in window) / (width - 1)
        relation_logs = []
        maximum_coefficient = 0
        for relation in relations:
            weighted = [
                value * coefficient for value, coefficient in zip(values, relation)
            ]
            relation_logs.append(log_euclidean_norm(weighted) - product_root_log)
            maximum_coefficient = max(
                maximum_coefficient, max(abs(value) for value in relation)
            )
        if maximum_coefficient > coefficient_limit:
            raise AssertionError("bounded relation exceeded the uniform coefficient limit")

        # Each relation has at most four nonzero coordinates.  This is a
        # uniform, closed-form upper bound on the (width-3)-rd successive
        # minimum of the normalized weighted congruence lattice.
        relation_radius_bound_log = (
            math.log(4)
            + 2 * math.log(max(RATIO_NUMERATOR, RATIO_DENOMINATOR))
            + math.log(max(values))
            - product_root_log
        )
        rows.append({
            "base_index": base,
            "base_gap": gaps[base],
            "primitive": vector_gcd(window) == 1,
            "independent_relations": relation_count,
            "maximum_relation_coefficient": maximum_coefficient,
            "log_normalized_relation_radius": max(relation_logs),
            "log_uniform_relation_radius_bound": relation_radius_bound_log,
        })

    primitive_rows = [row for row in rows if bool(row["primitive"])]
    return {
        "windows_checked": len(rows),
        "primitive_windows": len(primitive_rows),
        "certified_relation_rank": relation_count,
        "coefficient_limit": coefficient_limit,
        "log_normalized_relation_radius": summarize([
            float(row["log_normalized_relation_radius"]) for row in rows
        ]),
        "log_uniform_relation_radius_bound": summarize([
            float(row["log_uniform_relation_radius_bound"]) for row in rows
        ]),
        "selected_rows": [
            rows[index]
            for index in sorted({0, len(rows) // 2, len(rows) - 1})
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terms", type=int, default=800)
    parser.add_argument("--windows", type=int, nargs="+", default=(4, 8, 12, 14))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("result/v3/lattice-relation-audit-v3.json"),
    )
    args = parser.parse_args()
    if min(args.windows) < 4:
        raise ValueError("every audited window must have width at least four")
    if args.terms <= max(args.windows):
        raise ValueError("--terms must leave at least one complete future window")

    gaps = exact_positive_gaps(args.terms)
    reports = {str(width): audit_window(gaps, width) for width in args.windows}
    payload = {
        "schema_version": 1,
        "status": "exact_finite_certificates_supporting_a_separate_asymptotic_proof",
        "sequence": {
            "ratio": [RATIO_NUMERATOR, RATIO_DENOMINATOR],
            "positive_terms_audited": len(gaps),
        },
        "theorem_checked": {
            "bounded_rounding_error": (
                "-B < B*h_(t+1)-A*h_t < A"
            ),
            "fixed_window_relation_rank": "m-3",
            "consequence": (
                "fixed-m normalized Kannan lattices escape compact sets; "
                "primitive windows have Frobenius number Omega(h_t^(3/2))"
            ),
            "warning": (
                "finite arithmetic checks do not replace the proof in "
                "docs/固定窗口关键前提审计.md"
            ),
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
        "terms": len(gaps),
        "windows": list(reports),
    }))


if __name__ == "__main__":
    main()
