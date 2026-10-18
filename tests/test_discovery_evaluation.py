import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.baselines import BASELINES
from core.data import Task, make_array
from core.dsl import Expr
from core.evaluation import EvaluationCostCache
from core.fast_shellsort import benchmark_shellsort
from core.program import GeneratorProgram, Statement
from scripts.select_discovery import selection_key


def simple_program(divisor: float) -> GeneratorProgram:
    n = Expr.variable("n")
    r0 = Expr.variable("r0")
    return GeneratorProgram(
        (Expr("div", (n, Expr.constant(divisor))),),
        (
            Statement("emit", r0),
            Statement("assign", Expr("div", (r0, Expr.constant(2))), 0),
        ),
        fuel_base=1,
        fuel_log=2,
    )


class DiscoveryEvaluationTests(unittest.TestCase):
    def test_shared_cost_cache_reuses_exact_result_and_records_censoring(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cost.sqlite"
            task = Task(64, "random", 0)
            with EvaluationCostCache(path) as cache:
                first = cache.evaluate(task, (32, 8, 1))
                second = cache.evaluate(task, (32, 8, 1))
                censored = cache.evaluate(task, (1,), max_normalized_operations=0.001)
                self.assertEqual(first, second)
                self.assertEqual((cache.misses, cache.hits), (2, 1))
                self.assertTrue(censored.censored)
            with EvaluationCostCache(path) as restored:
                self.assertEqual(restored.evaluate(task, (32, 8, 1)), first)
                self.assertEqual((restored.hits, restored.misses), (1, 0))

    def test_cli_output_has_schema_and_second_run_skips_completed_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "validation": {"min_n": 64, "max_n": 64, "seeds": [0]}
            }))
            programs = [simple_program(2), simple_program(3)]
            candidates = root / "candidates.json"
            candidates.write_text(json.dumps({
                "schema_version": 3,
                "train_best_program_hash": programs[0].program_hash,
                "candidates": [
                    {
                        "program_hash": program.program_hash,
                        "program": program.to_dict(),
                        "selection_roles": ["train_best"] if index == 0 else ["pareto"],
                    }
                    for index, program in enumerate(programs)
                ],
            }))
            output = root / "validation.json"
            command = [
                sys.executable, "scripts/evaluate_discovery.py", str(candidates),
                "--stage", "validation", "--manifest", str(manifest),
                "--points", "1", "--distributions", "random",
                "--cache", str(root / "cost.sqlite"), "--output", str(output),
            ]
            first = subprocess.run(command, check=True, capture_output=True, text=True)
            result = json.loads(output.read_text())
            self.assertEqual(result["evaluator_version"], 3)
            self.assertEqual(len(result["reports"]), 2)
            self.assertTrue(result["evaluation_signature"])
            self.assertEqual(len(result["reports"][0]["task_results"]), 1)
            self.assertFalse(output.with_suffix(".json.progress").exists())
            task = Task(64, "random", 0)
            values = make_array(task)
            candidate_cost = benchmark_shellsort(values, programs[0].generate(task.n))[1]
            for name, baseline in BASELINES.items():
                baseline_cost = benchmark_shellsort(values, baseline(task.n))[1]
                expected = math.log((candidate_cost.total + 1) / (baseline_cost.total + 1))
                actual = result["reports"][0]["fixed_baseline_log_ratios"][name]
                self.assertAlmostEqual(actual, expected)
            second = subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertIn("already complete", second.stdout)
            self.assertNotIn("already complete", first.stdout)

    def test_validation_selection_prefers_uncensored_worst_case_winner(self):
        def report(program_hash, ratios, censored=0):
            return {
                "program_hash": program_hash,
                "fixed_baseline_log_ratios": ratios,
                "censored_tasks": censored,
                "comparisons": 10,
                "moves": 10,
                "complexity": [9, 2],
            }

        apparently_fast_but_censored = report(
            "a", {"sedgewick": -1.0, "tokuda": -1.0, "ciura": -1.0}, 1
        )
        robust = report(
            "b", {"sedgewick": -0.02, "tokuda": -0.01, "ciura": -0.03}
        )
        self.assertLess(selection_key(robust), selection_key(apparently_fast_but_censored))

    def test_selector_freezes_one_validation_winner_per_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = set()
            for seed in range(5):
                seed_dir = root / f"seed-{seed}"
                seed_dir.mkdir()
                programs = [simple_program(seed + 2), simple_program(seed + 2.5)]
                expected.add(programs[1].program_hash)
                (seed_dir / "candidates.json").write_text(json.dumps({
                    "schema_version": 3,
                    "candidates": [
                        {"program_hash": program.program_hash, "program": program.to_dict()}
                        for program in programs
                    ],
                }))
                reports = []
                for index, program in enumerate(programs):
                    ratio = 0.1 if index == 0 else -0.01
                    reports.append({
                        "program_hash": program.program_hash,
                        "fixed_baseline_log_ratios": {
                            "sedgewick": ratio, "tokuda": ratio, "ciura": ratio,
                        },
                        "censored_tasks": 0,
                        "comparisons": 100 + index,
                        "moves": 100,
                        "complexity": list(program.complexity),
                    })
                (seed_dir / "validation.json").write_text(json.dumps({
                    "schema_version": 3,
                    "evaluator_version": 2,
                    "stage": "validation",
                    "evaluation_signature": f"signature-{seed}",
                    "reports": reports,
                }))
            output = root / "selected-programs.json"
            subprocess.run([
                sys.executable, "scripts/select_discovery.py", "--run-root", str(root),
                "--output", str(output),
            ], check=True, capture_output=True, text=True)
            selected = json.loads(output.read_text())
            self.assertEqual(
                {item["program_hash"] for item in selected["candidates"]}, expected
            )
            self.assertEqual(len(selected["validation_selected_program_hashes"]), 5)


if __name__ == "__main__":
    unittest.main()
