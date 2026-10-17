import unittest

from core.fast_shellsort import benchmark_shellsort_trace
from core.sequence import GapSequence
from core.shellsort import shellsort
from core.trace import deletion_counterfactuals, shellsort_trace


class TraceV2Tests(unittest.TestCase):
    def test_trace_sums_to_reference_cost(self):
        values = [8, 3, 7, 1, 9, 2, 6, 5, 4, 0]
        gaps = (5, 2, 1)
        expected_values, expected_cost = shellsort(values, gaps)
        actual_values, trace = shellsort_trace(values, gaps)
        self.assertEqual(actual_values, expected_values)
        self.assertEqual(trace.cost, expected_cost)
        self.assertEqual(len(trace.passes), len(gaps))

    def test_numba_trace_matches_python_trace(self):
        values = list(range(100, 0, -1))
        gaps = (40, 13, 4, 1)
        _, reference = shellsort_trace(values, gaps, disorder=False)
        _, compiled = benchmark_shellsort_trace(values, gaps)
        self.assertEqual(compiled.cost, reference.cost)
        self.assertEqual(
            [(x.comparisons, x.moves) for x in compiled.passes],
            [(x.comparisons, x.moves) for x in reference.passes],
        )

    def test_counterfactuals_are_exact(self):
        values = list(range(50, 0, -1))
        sequence = GapSequence(50, (23, 8, 3, 1))
        values_before = list(values)
        result = deletion_counterfactuals(values, sequence)
        self.assertEqual(values, values_before)
        self.assertEqual(len(result), 3)

