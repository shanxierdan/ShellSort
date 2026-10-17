"""Optional Numba backend for integer benchmark arrays."""

from __future__ import annotations

from collections.abc import Sequence

from .shellsort import OperationLimitExceeded, SortCost, shellsort, validate_gaps

try:
    import numpy as np
    from numba import njit

    @njit(cache=True)
    def _compiled_shellsort(array, gaps, maximum):
        comparisons = 0
        moves = 0
        for gap in gaps:
            for index in range(gap, len(array)):
                value = array[index]
                cursor = index
                while cursor >= gap:
                    comparisons += 1
                    if maximum >= 0 and comparisons + moves > maximum:
                        return comparisons, moves, True
                    if array[cursor - gap] <= value:
                        break
                    array[cursor] = array[cursor - gap]
                    moves += 1
                    if maximum >= 0 and comparisons + moves > maximum:
                        return comparisons, moves, True
                    cursor -= gap
                if cursor != index:
                    array[cursor] = value
                    moves += 1
                    if maximum >= 0 and comparisons + moves > maximum:
                        return comparisons, moves, True
        return comparisons, moves, False

    @njit(cache=True)
    def _compiled_shellsort_trace(array, gaps, maximum):
        pass_comparisons = np.zeros(len(gaps), dtype=np.int64)
        pass_moves = np.zeros(len(gaps), dtype=np.int64)
        total = 0
        for pass_index in range(len(gaps)):
            gap = gaps[pass_index]
            for index in range(gap, len(array)):
                value = array[index]
                cursor = index
                while cursor >= gap:
                    pass_comparisons[pass_index] += 1
                    total += 1
                    if maximum >= 0 and total > maximum:
                        return pass_comparisons, pass_moves, True
                    if array[cursor - gap] <= value:
                        break
                    array[cursor] = array[cursor - gap]
                    pass_moves[pass_index] += 1
                    total += 1
                    if maximum >= 0 and total > maximum:
                        return pass_comparisons, pass_moves, True
                    cursor -= gap
                if cursor != index:
                    array[cursor] = value
                    pass_moves[pass_index] += 1
                    total += 1
                    if maximum >= 0 and total > maximum:
                        return pass_comparisons, pass_moves, True
        return pass_comparisons, pass_moves, False

    NUMBA_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised on minimal installations
    np = None
    NUMBA_AVAILABLE = False


def benchmark_shellsort(
    values: Sequence[int],
    gaps: Sequence[int],
    max_operations: int | None = None,
) -> tuple[list[int], SortCost]:
    """Use compiled integer counting when available, otherwise pure Python."""
    if not NUMBA_AVAILABLE:
        return shellsort(values, gaps, max_operations=max_operations)
    valid_gaps = validate_gaps(gaps, len(values))
    array = np.asarray(values, dtype=np.int64).copy()
    gap_array = np.asarray(valid_gaps, dtype=np.int64)
    maximum = -1 if max_operations is None else max_operations
    comparisons, moves, exceeded = _compiled_shellsort(array, gap_array, maximum)
    if exceeded:
        raise OperationLimitExceeded("Shellsort operation budget exceeded")
    return array.tolist(), SortCost(int(comparisons), int(moves))


def benchmark_shellsort_cost(
    values: Sequence[int],
    gaps: Sequence[int],
    max_operations: int | None = None,
    *,
    copy_values: bool = True,
) -> SortCost:
    """Return exact counts without materializing the sorted output list."""
    if not NUMBA_AVAILABLE:
        return shellsort(values, gaps, max_operations=max_operations)[1]
    valid_gaps = validate_gaps(gaps, len(values))
    array = np.asarray(values, dtype=np.int64)
    if copy_values or not array.flags.c_contiguous or not array.flags.writeable:
        array = array.copy()
    gap_array = np.asarray(valid_gaps, dtype=np.int64)
    maximum = -1 if max_operations is None else max_operations
    comparisons, moves, exceeded = _compiled_shellsort(array, gap_array, maximum)
    if exceeded:
        raise OperationLimitExceeded("Shellsort operation budget exceeded")
    return SortCost(int(comparisons), int(moves))


def benchmark_shellsort_trace(
    values: Sequence[int],
    gaps: Sequence[int],
    max_operations: int | None = None,
):
    """Return a fast exact per-pass trace; disorder summaries are omitted."""
    from .trace import PassTrace, SortTrace, shellsort_trace

    if not NUMBA_AVAILABLE:
        return shellsort_trace(values, gaps, max_operations=max_operations, disorder=False)
    valid_gaps = validate_gaps(gaps, len(values))
    array = np.asarray(values, dtype=np.int64).copy()
    gap_array = np.asarray(valid_gaps, dtype=np.int64)
    maximum = -1 if max_operations is None else max_operations
    comparisons, moves, exceeded = _compiled_shellsort_trace(array, gap_array, maximum)
    if exceeded:
        raise OperationLimitExceeded("Shellsort operation budget exceeded")
    passes = tuple(
        PassTrace(int(gap), int(comparisons[i]), int(moves[i]), 0, 0)
        for i, gap in enumerate(valid_gaps)
    )
    return array.tolist(), SortTrace(len(values), valid_gaps, passes)
