from fractions import Fraction

from scripts.stress_test_carry_orbits import (
    exact_floor_window,
    floor_window_patterns,
    leading_zero_error_run,
    parametric_counterexample_case,
)


def test_exact_floor_window_uses_rational_theta() -> None:
    gaps = exact_floor_window(5, 2, 10_000, Fraction(96, 15_625), 6)
    assert gaps == [25_000, 62_500, 156_250, 390_625, 976_563, 2_441_407]
    assert leading_zero_error_run(gaps, 5, 2) == 3


def test_all_theta_enumeration_contains_long_zero_prefix_counterexample() -> None:
    patterns = floor_window_patterns(5, 2, 10_000, 6)
    target = [25_000, 62_500, 156_250, 390_625, 976_563, 2_441_407]
    assert any(gaps == target for gaps, _ in patterns)


def test_parametric_family_has_exact_linear_bad_prefix_and_finite_quotient() -> None:
    report = parametric_counterexample_case(6)
    assert report["window_m"] == 8
    assert report["local_errors"] == [0, 0, 0, 0, 0, -1, 1]
    assert report["two_c_minus_five_b"] == 1
    assert report["guaranteed_missing_multiplier"] % 5 != 0


def test_parametric_normalized_conductor_lower_bound_grows_exponentially() -> None:
    reports = [parametric_counterexample_case(length) for length in range(3, 9)]
    normalized = [
        float(row["conductor_lower_bound_over_h_over_B_to_m"])
        for row in reports
    ]
    assert all(right > 2 * left for left, right in zip(normalized, normalized[1:]))
