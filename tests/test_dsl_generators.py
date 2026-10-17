import unittest
import math

from core.dsl import Expr, evaluate
from core.generators import EnumerativeGenerator, RecursiveGenerator


class DslGeneratorTests(unittest.TestCase):
    def test_protected_division_is_finite(self) -> None:
        expr = Expr("div", (Expr.constant(1), Expr.constant(0)))
        self.assertTrue(math.isclose(evaluate(expr, {}), 1e9, rel_tol=1e-12))

    def test_recursive_shell_generator(self) -> None:
        init = Expr("floor", (Expr("div", (Expr.variable("n"), Expr.constant(2))),))
        next_gap = Expr("floor", (Expr("div", (Expr.variable("h"), Expr.constant(2))),))
        self.assertEqual(RecursiveGenerator(init, next_gap).generate(20), (10, 5, 2, 1))

    def test_enumerative_pratt_generator(self) -> None:
        two_a = Expr("pow", (Expr.constant(2), Expr.variable("a")))
        three_b = Expr("pow", (Expr.constant(3), Expr.variable("b")))
        generator = EnumerativeGenerator(4, 3, Expr("mul", (two_a, three_b)))
        self.assertEqual(generator.generate(20), (18, 16, 12, 9, 8, 6, 4, 3, 2, 1))
