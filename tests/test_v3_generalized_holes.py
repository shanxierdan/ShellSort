from fractions import Fraction

from scripts.analyze_v3_generalized_holes import (
    best_coprime_generator_pair,
    fixed_window_forced_hole_lower_bound,
    generalized_hole_count,
    quotient_semigroup_generators,
)
from scripts.analyze_v3_number_theory import (
    ALPHA_DENOMINATOR,
    ALPHA_NUMERATOR,
    RATIO_DENOMINATOR,
    RATIO_NUMERATOR,
    apery_set,
    exact_positive_gaps,
    frobenius_number,
    semigroup_representation,
)
from scripts.stress_test_rational_quotients import audit_ratio


def test_apery_set_and_frobenius_number_agree() -> None:
    representatives = apery_set([3, 5])
    assert representatives == [0, 10, 5]
    assert max(representatives) - len(representatives) == 7
    assert frobenius_number([3, 5]) == 7


def test_generalized_holes_count_only_requested_multiples() -> None:
    assert generalized_hole_count(1, [3, 5]) == 4  # 1, 2, 4, 7
    assert generalized_hole_count(2, [3, 5]) == 2  # 2, 4
    assert generalized_hole_count(3, [3, 5]) == 0


def test_generalized_holes_handle_common_divisor_exactly() -> None:
    assert generalized_hole_count(4, [6, 10]) == 2
    assert generalized_hole_count(3, [6, 10]) is None


def test_semigroup_representation_recovers_exact_coefficients() -> None:
    assert semigroup_representation(7, [3, 5]) is None
    coefficients = semigroup_representation(8, [3, 5])
    assert coefficients is not None
    assert 3 * coefficients[0] + 5 * coefficients[1] == 8


def test_quotient_semigroup_generators_are_recovered_from_holes() -> None:
    assert quotient_semigroup_generators([1, 2, 4, 7]) == [3, 5]
    assert quotient_semigroup_generators([]) == [1]
    assert best_coprime_generator_pair([6, 10, 15]) is None
    assert best_coprime_generator_pair([6, 7, 11]) == (6, 7)


def test_fixed_window_lower_bound_counts_nonmultiples_of_ratio_numerator() -> None:
    width = 2
    scale = RATIO_NUMERATOR**width
    assert fixed_window_forced_hole_lower_bound(scale, width) == 0
    assert fixed_window_forced_hole_lower_bound(4 * scale + 1, width) == 4


def test_documented_small_quotient_generators_have_exact_witnesses() -> None:
    gaps = exact_positive_gaps(24)
    base = 14
    step = gaps[base]
    future = gaps[base + 1 : base + 9]
    assert 242 * step == 23 * future[0] + 2 * future[1] + 14 * future[2]
    assert (
        313 * step
        == 20 * future[0]
        + 20 * future[1]
        + 3 * future[3]
        + future[4]
    )
    assert (
        353 * step
        == 69 * future[0]
        + 4 * future[1]
        + 8 * future[2]
        + future[4]
    )


def test_two_dimensional_carry_identity_is_exact() -> None:
    gaps = exact_positive_gaps(24)
    base = 14
    width = 8
    step = gaps[base]
    future = gaps[base + 1 : base + 1 + width]
    coefficients = [23, 2, 14, 0, 0, 0, 0, 0]
    multiplier = 242

    errors = [
        RATIO_DENOMINATOR**index * gap
        - RATIO_NUMERATOR**index * step
        for index, gap in enumerate(future, 1)
    ]
    quotient_coordinates = [
        RATIO_NUMERATOR**index * RATIO_DENOMINATOR ** (width - index)
        for index in range(1, width + 1)
    ]
    carry_coordinates = [
        RATIO_DENOMINATOR ** (width - index) * error
        for index, error in enumerate(errors, 1)
    ]
    carry = (
        multiplier * RATIO_DENOMINATOR**width
        - sum(c * q for c, q in zip(coefficients, quotient_coordinates))
    )

    assert carry * step == sum(
        c * value for c, value in zip(coefficients, carry_coordinates)
    )
    assert multiplier * RATIO_DENOMINATOR**width == carry + sum(
        c * q for c, q in zip(coefficients, quotient_coordinates)
    )


def test_proof_guard_starts_at_exact_index_2724() -> None:
    guard = 10**1000
    previous_numerator = ALPHA_NUMERATOR * RATIO_NUMERATOR**2723
    previous_denominator = ALPHA_DENOMINATOR * RATIO_DENOMINATOR**2723
    first_numerator = previous_numerator * RATIO_NUMERATOR
    first_denominator = previous_denominator * RATIO_DENOMINATOR
    assert previous_numerator // previous_denominator <= guard
    assert first_numerator // first_denominator > guard


def test_small_rational_model_refutes_a_universal_saturation_claim() -> None:
    report = audit_ratio(12, 5, Fraction(7, 13), 592, 592)
    assert report["rows"] == [{
        "base_gap": 592,
        "window": 3,
        "h_over_A_to_m": 592 / 12**3,
        "h_over_B_to_m": 592 / 5**3,
        "finite": False,
        "generalized_holes": None,
        "maximum_missing_multiplier": None,
        "quotient_conductor": None,
        "conductor_over_h_over_B_to_m": None,
    }]
    assert report["infinite_window_count"] == 1
