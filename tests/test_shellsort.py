import unittest

from core.shellsort import shellsort, validate_gaps


class ShellsortTests(unittest.TestCase):
    def test_shellsort_sorts_and_counts_deterministically(self) -> None:
        result, cost = shellsort([3, 1, 2], (1,))
        self.assertEqual(result, [1, 2, 3])
        self.assertEqual((cost.comparisons, cost.moves), (3, 4))

    def test_invalid_gaps_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_gaps((2, 2, 1), 10)

    def test_empty_array_needs_no_gaps(self) -> None:
        self.assertEqual(shellsort([], ())[0], [])
