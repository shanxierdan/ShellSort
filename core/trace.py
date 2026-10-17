"""Per-gap Shellsort execution traces and counterfactual measurements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence, TypeVar

from .sequence import GapSequence
from .shellsort import OperationLimitExceeded, SortCost, validate_gaps

T = TypeVar("T")


@dataclass(frozen=True)
class PassTrace:
    gap: int
    comparisons: int
    moves: int
    adjacent_inversions_before: int
    adjacent_inversions_after: int


@dataclass(frozen=True)
class SortTrace:
    n: int
    gaps: tuple[int, ...]
    passes: tuple[PassTrace, ...]

    @property
    def cost(self) -> SortCost:
        return SortCost(
            sum(item.comparisons for item in self.passes),
            sum(item.moves for item in self.passes),
        )


def _adjacent_inversions(values: Sequence[T]) -> int:
    return sum(left > right for left, right in zip(values, values[1:]))


def shellsort_trace(
    values: Iterable[T],
    gaps: Sequence[int],
    max_operations: int | None = None,
    disorder: bool = True,
) -> tuple[list[T], SortTrace]:
    array = list(values)
    valid = validate_gaps(gaps, len(array))
    passes: list[PassTrace] = []
    total = 0
    for gap in valid:
        comparisons = moves = 0
        before = _adjacent_inversions(array) if disorder else 0
        for index in range(gap, len(array)):
            value = array[index]
            cursor = index
            while cursor >= gap:
                comparisons += 1
                total += 1
                if max_operations is not None and total > max_operations:
                    raise OperationLimitExceeded("Shellsort operation budget exceeded")
                if array[cursor - gap] <= value:
                    break
                array[cursor] = array[cursor - gap]
                moves += 1
                total += 1
                if max_operations is not None and total > max_operations:
                    raise OperationLimitExceeded("Shellsort operation budget exceeded")
                cursor -= gap
            if cursor != index:
                array[cursor] = value
                moves += 1
                total += 1
                if max_operations is not None and total > max_operations:
                    raise OperationLimitExceeded("Shellsort operation budget exceeded")
        after = _adjacent_inversions(array) if disorder else 0
        passes.append(PassTrace(gap, comparisons, moves, before, after))
    return array, SortTrace(len(array), valid, tuple(passes))


@dataclass(frozen=True)
class Counterfactual:
    index: int
    gap: int
    comparisons_delta: int
    moves_delta: int


def deletion_counterfactuals(
    values: Sequence[int], sequence: GapSequence, limit: int | None = None
) -> tuple[Counterfactual, ...]:
    """Cost increase after deleting each non-terminal gap.

    Positive deltas mean the gap was useful; negative deltas mean deletion
    improved the sequence.
    """
    _, base = shellsort_trace(values, sequence.gaps, disorder=False)
    output: list[Counterfactual] = []
    indices = range(max(0, len(sequence.gaps) - 1))
    if limit is not None:
        indices = range(min(len(sequence.gaps) - 1, limit))
    for index in indices:
        child = GapSequence(sequence.n, sequence.gaps[:index] + sequence.gaps[index + 1 :])
        _, trace = shellsort_trace(values, child.gaps, disorder=False)
        output.append(
            Counterfactual(
                index,
                sequence.gaps[index],
                trace.cost.comparisons - base.cost.comparisons,
                trace.cost.moves - base.cost.moves,
            )
        )
    return tuple(output)
