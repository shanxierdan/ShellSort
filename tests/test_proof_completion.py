from decimal import Decimal, getcontext
from math import ceil, gcd, log


A = 582_942_583_375_009
B = 250_000_000_000_000
ALPHA_NUMERATOR = 420_574_650_882_923
ALPHA_DENOMINATOR = 7_668_945_023_518_835


def exact_gap(index: int) -> int:
    return (
        ALPHA_NUMERATOR * A**index
        // (ALPHA_DENOMINATOR * B**index)
    )


def test_theorem_constants_and_guard_are_exact() -> None:
    assert gcd(A, B) == 1
    assert gcd(ALPHA_NUMERATOR, ALPHA_DENOMINATOR) == 1
    guard = 10**1000
    assert (
        ALPHA_NUMERATOR * A**2723
        < (guard + 1) * ALPHA_DENOMINATOR * B**2723
    )
    assert (
        ALPHA_NUMERATOR * A**2724
        >= (guard + 1) * ALPHA_DENOMINATOR * B**2724
    )
    assert exact_gap(2723) <= guard < exact_gap(2724)


def test_reported_exponents_use_the_exact_ratio() -> None:
    getcontext().prec = 70
    ratio = Decimal(A) / Decimal(B)
    kappa = ratio.ln() / Decimal(A).ln()
    dense_exponent = Decimal(1) + kappa / (Decimal(1) + kappa)
    sparse_exponent = Decimal(1) + 2 * kappa / (Decimal(1) + 2 * kappa)
    gamma = Decimal(A).ln() / Decimal(B).ln()
    zang_exponent = Decimal(1) + (gamma - 1) / (2 * gamma - 1)
    assert str(kappa).startswith("0.024901468995116044855")
    assert str(dense_exponent).startswith("1.02429645165747606869")
    assert str(sparse_exponent).startswith("1.04744027301502511325")
    assert zang_exponent == dense_exponent


def test_two_coordinate_and_unit_companion_identities_are_exact() -> None:
    t = 18
    width = 7
    for current in (exact_gap(t), exact_gap(t) + 1):
        future = [exact_gap(t + i) for i in range(1, width + 1)]
        quotient = [A**i * B ** (width - i) for i in range(1, width + 1)]
        error = [
            B ** (width - i) * (B**i * gap - A**i * current)
            for i, gap in enumerate(future, start=1)
        ]
        for gap, q_i, v_i in zip(future, quotient, error):
            assert B**width * gap == current * q_i + v_i

        companion_index = 3
        q_j = quotient[companion_index - 1]
        v_j = error[companion_index - 1]
        companion = future[companion_index - 1] + 1
        assert B**width * companion == current * q_j + v_j + B**width
        assert B**width * companion - B**width * future[companion_index - 1] == B**width

        for i in range(width - 1):
            assert A * quotient[i] == B * quotient[i + 1]
            local_error = B * future[i + 1] - A * future[i]
            assert A * error[i] - B * error[i + 1] == -(B**width) * local_error


def test_dense_companion_recurrence_covers_the_asymptotic_window() -> None:
    indices = [2724]
    while indices[-1] <= 3200:
        indices.append(indices[-1] + ceil(log(indices[-1] + 2)))

    next_index = 1
    for t in range(2724, 3201):
        while indices[next_index] <= t:
            next_index += 1
        offset = indices[next_index] - t
        window = ceil(log(exact_gap(t), A))
        assert 1 <= offset <= ceil(log(t + 2)) < window
