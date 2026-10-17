from scripts.analyze_v3_lattice_relations import (
    bounded_relation_vectors,
    recurrence_rows,
)
from scripts.analyze_v3_number_theory import (
    RATIO_DENOMINATOR,
    RATIO_NUMERATOR,
    exact_positive_gaps,
)


def test_rational_rounding_recurrence_is_exact_and_bounded() -> None:
    gaps = exact_positive_gaps(40)
    rows, errors = recurrence_rows(gaps[5:19])
    assert len(rows) == len(errors) == 13
    for row, error in zip(rows, errors):
        assert sum(coefficient * gap for coefficient, gap in zip(row, gaps[5:19])) == error
        assert -RATIO_DENOMINATOR < error < RATIO_NUMERATOR


def test_fixed_window_has_the_certified_number_of_bounded_relations() -> None:
    gaps = exact_positive_gaps(50)
    coefficient_limit = 2 * max(RATIO_NUMERATOR, RATIO_DENOMINATOR) ** 2
    for width in (4, 8, 12, 14):
        values = gaps[7 : 7 + width - 1]
        relations = bounded_relation_vectors(values)
        assert len(relations) == width - 3
        for relation in relations:
            assert sum(value * coefficient for value, coefficient in zip(values, relation)) == 0
            assert max(abs(coefficient) for coefficient in relation) <= coefficient_limit
