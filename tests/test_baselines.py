import unittest

from core.baselines import BASELINES, pratt
from core.shellsort import validate_gaps


class BaselineTests(unittest.TestCase):
    def test_all_baselines_produce_valid_gaps(self) -> None:
        for n in (2, 3, 10, 100, 1000):
            for gap_fn in BASELINES.values():
                validate_gaps(gap_fn(n), n)

    def test_pratt_contains_products_of_two_and_three(self) -> None:
        gaps = set(pratt(20))
        self.assertTrue({1, 2, 3, 4, 6, 8, 9, 12, 16, 18} <= gaps)
