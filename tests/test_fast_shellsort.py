import unittest

from core.fast_shellsort import benchmark_shellsort, benchmark_shellsort_cost
from core.shellsort import OperationLimitExceeded, shellsort


class FastShellsortTests(unittest.TestCase):
    def test_compiled_backend_matches_reference_counts(self) -> None:
        values = [8, 1, 6, 3, 5, 2, 7, 4]
        gaps = (4, 2, 1)
        expected = shellsort(values, gaps)
        actual = benchmark_shellsort(values, gaps)
        self.assertEqual(actual, expected)
        self.assertEqual(benchmark_shellsort_cost(values, gaps), expected[1])

    def test_operation_limit_stops_bad_candidate(self) -> None:
        with self.assertRaises(OperationLimitExceeded):
            benchmark_shellsort(list(range(100, 0, -1)), (1,), max_operations=10)
