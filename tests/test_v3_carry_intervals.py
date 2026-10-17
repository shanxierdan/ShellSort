from scripts.analyze_v3_carry_intervals import (
    audit_small_model_interval,
    carry_coordinates,
    compound_frobenius,
    compound_normal_form,
    compound_weights,
    construct_certificate_via_carries,
    decompose_certificate,
    prefix_recovery_audit,
    recover_adjacent_carries,
)
from scripts.analyze_v3_number_theory import (
    RATIO_DENOMINATOR,
    RATIO_NUMERATOR,
    exact_positive_gaps,
)


def test_compound_sequence_normal_form_and_frobenius() -> None:
    assert compound_weights(3, 3, 2) == [4, 6, 9]
    assert compound_frobenius(3, 3, 2) == 11
    assert compound_normal_form(11, 3, 3, 2) is None
    coefficients = compound_normal_form(13, 3, 3, 2)
    assert coefficients == [1, 0, 1]


def test_adjacent_carries_generate_the_exact_q_kernel() -> None:
    canonical = [8, 1, 0, 1]
    carries = [-2, 3, -1]
    numerator = 7
    denominator = 3
    coefficients = canonical.copy()
    for index, value in enumerate(carries):
        coefficients[index] += numerator * value
        coefficients[index + 1] -= denominator * value
    assert recover_adjacent_carries(
        coefficients, canonical, numerator, denominator
    ) == carries


def test_unit_companion_extends_kernel_by_one_direct_summand() -> None:
    numerator = 5
    denominator = 2
    width = 4
    companion_index = 2
    quotient = [
        numerator**index * denominator ** (width - index)
        for index in range(1, width + 1)
    ]
    carries = [3, -2, 4]
    unit_exchange = -7
    vector = [0] * (width + 1)
    for index, value in enumerate(carries):
        vector[index] += numerator * value
        vector[index + 1] -= denominator * value
    vector[companion_index] -= unit_exchange
    vector[-1] += unit_exchange
    augmented_quotient = quotient + [quotient[companion_index]]
    assert sum(x * q for x, q in zip(vector, augmented_quotient)) == 0

    merged = vector[:-1]
    merged[companion_index] += vector[-1]
    assert recover_adjacent_carries(
        merged, [0] * width, numerator, denominator
    ) == carries
    assert vector[-1] == unit_exchange


def test_each_adjacent_carry_changes_v_by_one_local_error_block() -> None:
    gaps = exact_positive_gaps(24)
    step = gaps[14]
    generators = gaps[15:23]
    _, quotient, carry_values = carry_coordinates(
        step, generators, RATIO_NUMERATOR, RATIO_DENOMINATOR
    )
    width = len(generators)
    for index in range(width - 1):
        local_error = (
            RATIO_DENOMINATOR * generators[index + 1]
            - RATIO_NUMERATOR * generators[index]
        )
        assert (
            RATIO_NUMERATOR * quotient[index]
            - RATIO_DENOMINATOR * quotient[index + 1]
        ) == 0
        assert (
            RATIO_NUMERATOR * carry_values[index]
            - RATIO_DENOMINATOR * carry_values[index + 1]
        ) == -(RATIO_DENOMINATOR**width) * local_error


def test_documented_certificate_has_exact_compound_carry_decomposition() -> None:
    gaps = exact_positive_gaps(24)
    step = gaps[14]
    generators = gaps[15:23]
    result = decompose_certificate(
        step,
        generators,
        242,
        [23, 2, 14, 0, 0, 0, 0, 0],
        RATIO_NUMERATOR,
        RATIO_DENOMINATOR,
    )
    assert result["multiplier"] == 242
    assert result["error_gcd"] >= 1
    assert len(result["canonical_coefficients"]) == len(generators)
    assert len(result["adjacent_carries"]) == len(generators) - 1


def test_small_rational_certificate_exercises_nonzero_carry_equation() -> None:
    result = decompose_certificate(
        131,
        [328, 821, 2054, 5135],
        223,
        [44, 13, 2, 0],
        5,
        2,
    )
    assert result["cleared_carry_D"] == 8
    assert result["canonical_coefficients"] == [89, 0, 0, 0]
    assert result["adjacent_carries"] == [-9, -1, 0]
    assert result["error_target"] == -21


def test_carry_constructor_independently_recovers_small_certificate() -> None:
    result = construct_certificate_via_carries(
        131,
        [328, 821, 2054, 5135],
        223,
        5,
        2,
        maximum_abs_D=25,
    )
    assert result is not None
    coefficients = result["future_gap_coefficients"]
    assert sum(
        coefficient * gap
        for coefficient, gap in zip(coefficients, [328, 821, 2054, 5135])
    ) == 223 * 131


def test_carry_constructor_fills_a_complete_small_model_interval() -> None:
    report = audit_small_model_interval(max_states=200_000)
    assert report["interval"] == [223, 445]
    assert report["certificates_constructed"] == 223
    assert report["maximum_used_abs_D"] <= report["maximum_allowed_abs_D"]


def test_prefix_recovery_audit_distinguishes_truncated_suffixes() -> None:
    report = prefix_recovery_audit([2, 4, 3, -1])
    gcd_report = report["minimum_prefix_for_error_gcd_one"]
    sign_report = report["minimum_prefix_for_both_error_signs"]
    assert gcd_report["maximum_resolved_prefix"] == 3
    assert gcd_report["unresolved_tail_bases"] == 0
    assert sign_report["maximum_resolved_prefix"] == 4
    assert sign_report["unresolved_tail_bases"] == 1
