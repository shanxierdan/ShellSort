import json
import tempfile
import unittest
from pathlib import Path

from core.discovery import FrozenCandidate, load_candidates, save_candidates, stage_tasks
from core.data import COMPACT_ARRAYS_AVAILABLE, Task, make_compact_array
from core.dsl import Expr
from core.evaluation import CandidateScore
from core.generators import RecursiveGenerator


class DiscoveryTests(unittest.TestCase):
    def test_candidate_round_trip_and_hash_verification(self) -> None:
        generator = RecursiveGenerator(
            Expr("floor", (Expr("div", (Expr.variable("n"), Expr.constant(2))),)),
            Expr("floor", (Expr("div", (Expr.variable("h"), Expr.constant(2))),)),
        )
        score = CandidateScore("ignored", 0.0, 0.0, 0, 0, 1, generator.complexity)
        frozen = FrozenCandidate.create(generator, score)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidates.json"
            save_candidates(path, [frozen])
            self.assertEqual(load_candidates(path)[0].verify().generate(20), (10, 5, 2, 1))

    def test_final_test_requires_explicit_permission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps({"final_test": {"min_n": 10, "max_n": 20, "seeds": [1]}}))
            with self.assertRaises(PermissionError):
                stage_tasks(path, "final_test")

    def test_final_test_uses_explicit_closed_interval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps({
                "final_test": {"min_n": 10, "max_n": 100, "seeds": [9]}
            }))
            tasks = stage_tasks(
                path, "final_test", ("random",), allow_final_test=True, points=3
            )
            self.assertEqual([task.n for task in tasks], [10, 32, 100])

    @unittest.skipUnless(COMPACT_ARRAYS_AVAILABLE, "numpy/numba unavailable")
    def test_compact_arrays_are_deterministic_and_well_formed(self) -> None:
        for distribution in ("random", "reversed", "nearly_sorted", "blocks"):
            task = Task(257, distribution, 17)
            first = make_compact_array(task)
            second = make_compact_array(task)
            self.assertEqual(first.dtype.name, "int64")
            self.assertTrue((first == second).all())
            self.assertEqual(sorted(first.tolist()), list(range(task.n)))
        duplicates = make_compact_array(Task(257, "duplicates", 17))
        self.assertGreaterEqual(int(duplicates.min()), 0)
        self.assertLess(int(duplicates.max()), int(257**0.5))
