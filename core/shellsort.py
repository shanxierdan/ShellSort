"""Shellsort implementation with deterministic operation counting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence, TypeVar

T = TypeVar("T")


class OperationLimitExceeded(RuntimeError):
    """Raised when a candidate exceeds a deterministic evaluation budget."""


@dataclass(frozen=True)
class SortCost:
    comparisons: int
    moves: int

    @property
    def total(self) -> int:
        return self.comparisons + self.moves


def validate_gaps(gaps: Sequence[int], n: int) -> tuple[int, ...]:
    normalized = tuple(int(gap) for gap in gaps)
    if n <= 1:
        return ()
    if not normalized or normalized[-1] != 1:
        raise ValueError("gap sequence must end with 1")
    if any(gap < 1 or gap >= n for gap in normalized):
        raise ValueError("every gap must be in [1, n)")
    if any(left <= right for left, right in zip(normalized, normalized[1:])):
        raise ValueError("gaps must be strictly decreasing")
    return normalized


def shellsort(
    values: Iterable[T],
    gaps: Sequence[int],
    max_operations: int | None = None,
) -> tuple[list[T], SortCost]:
    array = list(values)
    valid_gaps = validate_gaps(gaps, len(array))
    comparisons = 0
    moves = 0

    for gap in valid_gaps:
        for index in range(gap, len(array)):
            value = array[index]
            cursor = index
            while cursor >= gap:
                comparisons += 1
                if max_operations is not None and comparisons + moves > max_operations:
                    raise OperationLimitExceeded("Shellsort operation budget exceeded")
                if array[cursor - gap] <= value:
                    break
                array[cursor] = array[cursor - gap]
                moves += 1
                if max_operations is not None and comparisons + moves > max_operations:
                    raise OperationLimitExceeded("Shellsort operation budget exceeded")
                cursor -= gap
            if cursor != index:
                array[cursor] = value
                moves += 1
                if max_operations is not None and comparisons + moves > max_operations:
                    raise OperationLimitExceeded("Shellsort operation budget exceeded")

    return array, SortCost(comparisons=comparisons, moves=moves)
