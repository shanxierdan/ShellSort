"""Classic Shellsort gap families exposed through one registry."""

from __future__ import annotations

import math
from collections.abc import Callable

GapFunction = Callable[[int], tuple[int, ...]]


def _descending(values: set[int], n: int) -> tuple[int, ...]:
    if n <= 1:
        return ()
    values = {value for value in values if 1 <= value < n}
    values.add(1)
    return tuple(sorted(values, reverse=True))


def shell(n: int) -> tuple[int, ...]:
    values: set[int] = {1}
    gap = n // 2
    while gap >= 1:
        values.add(gap)
        gap //= 2
    return _descending(values, n)


def hibbard(n: int) -> tuple[int, ...]:
    values: set[int] = set()
    k = 1
    while (gap := 2**k - 1) < n:
        values.add(gap)
        k += 1
    return _descending(values, n)


def knuth(n: int) -> tuple[int, ...]:
    values: set[int] = set()
    gap = 1
    while gap < n:
        values.add(gap)
        gap = 3 * gap + 1
    return _descending(values, n)


def pratt(n: int) -> tuple[int, ...]:
    values: set[int] = set()
    power_two = 1
    while power_two < n:
        value = power_two
        while value < n:
            values.add(value)
            value *= 3
        power_two *= 2
    return _descending(values, n)


def sedgewick(n: int) -> tuple[int, ...]:
    values: set[int] = set()
    k = 0
    while True:
        even = 9 * 2 ** (2 * k) - 9 * 2**k + 1
        odd = 2 ** (2 * k + 4) - 3 * 2 ** (k + 2) + 1
        if even >= n and odd >= n:
            break
        values.update((even, odd))
        k += 1
    return _descending(values, n)


def tokuda(n: int) -> tuple[int, ...]:
    values: set[int] = set()
    k = 0
    while True:
        gap = math.ceil((9 * (9 / 4) ** k - 4) / 5)
        if gap >= n:
            break
        values.add(gap)
        k += 1
    return _descending(values, n)


def ciura(n: int) -> tuple[int, ...]:
    ascending = [1, 4, 10, 23, 57, 132, 301, 701, 1750]
    while ascending[-1] < n:
        ascending.append(max(ascending[-1] + 1, round(ascending[-1] * 2.25)))
    return _descending(set(ascending), n)


BASELINES: dict[str, GapFunction] = {
    "shell": shell,
    "hibbard": hibbard,
    "knuth": knuth,
    "pratt": pratt,
    "sedgewick": sedgewick,
    "tokuda": tokuda,
    "ciura": ciura,
}

