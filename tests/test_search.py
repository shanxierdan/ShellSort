import unittest
import tempfile
from pathlib import Path

from core.data import Task
from core.dsl import Expr
from core.evaluation import Benchmark, CandidateScore, StagedBenchmark
from core.generators import RecursiveGenerator
from core.search import ParetoArchive


def score(name: str, loss: float, size: int, depth: int) -> CandidateScore:
    return CandidateScore(name, loss, -loss, 0, 0, 1, (size, depth))


class SearchTests(unittest.TestCase):
    def test_pareto_archive_removes_dominated_candidates(self) -> None:
        archive = ParetoArchive()
        self.assertTrue(archive.add(score("a", 0.2, 10, 4)))
        self.assertTrue(archive.add(score("b", 0.1, 12, 4)))
        self.assertFalse(archive.add(score("c", 0.3, 15, 5)))
        self.assertEqual({item["program_id"] for item in archive.records()}, {"a", "b"})

    def test_staged_benchmark_can_stop_before_full_stage(self) -> None:
        generator = RecursiveGenerator(Expr.constant(1), Expr.constant(1))
        screen = Benchmark([Task(8, "reversed", 0)])
        full = Benchmark([Task(16, "reversed", 0)])
        score_record = StagedBenchmark(
            (("screen", screen), ("full", full)), promotion_losses=(-100.0,)
        ).evaluate(generator)
        self.assertEqual(score_record.fidelity, "screen")

    def test_sqlite_baseline_cache_is_reusable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "baseline.sqlite"
            tasks = [Task(16, "random", 7)]
            first = Benchmark(tasks, baseline_cache=cache)
            second = Benchmark(tasks, baseline_cache=cache)
            self.assertEqual(first._baseline_costs, second._baseline_costs)
            self.assertTrue(cache.exists())
