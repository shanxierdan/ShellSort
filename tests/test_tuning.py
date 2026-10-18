import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.data import Task
from core.evaluation import EvaluationCostCache
from core.tuning import (
    TunedCandidate,
    PrefixTuner,
    TuningConfig,
    geometric_gaps_below,
)


class TuningTests(unittest.TestCase):
    def test_exact_symbolic_backbone_has_recorded_prefix(self):
        self.assertEqual(
            geometric_gaps_below(100_000),
            (1, 3, 8, 20, 47, 111, 260, 607, 1416, 3303, 7703, 17963, 41887, 97670),
        )
        base = TunedCandidate.base()
        self.assertEqual(
            base.generate(100_000),
            tuple(reversed(geometric_gaps_below(100_000))),
        )

    def test_tuning_changes_only_a_finite_prefix(self):
        base = TunedCandidate.base()
        tuned = TunedCandidate((1, 4, 9, 21, 49, 114, 265, 612))
        n = 1_000_000
        immutable_tail = set(geometric_gaps_below(n)[base.prefix_terms :])
        self.assertEqual(set(tuned.generate(n)) - set(tuned.prefix), immutable_tail)
        self.assertEqual(
            [gap for gap in tuned.generate(n) if gap >= 1416],
            [gap for gap in base.generate(n) if gap >= 1416],
        )
        restored = TunedCandidate.from_dict(tuned.to_dict())
        self.assertEqual(restored, tuned)
        self.assertEqual(restored.candidate_hash, tuned.candidate_hash)

    def test_tail_or_order_changes_are_rejected(self):
        with self.assertRaises(ValueError):
            TunedCandidate((1, 4, 4, 20, 47, 111, 260, 607))
        with self.assertRaises(ValueError):
            TunedCandidate((1, 4, 9, 20, 47, 111, 260, 1416))
        payload = TunedCandidate.base().to_dict()
        payload["tail"]["ratio_numerator"] += 1
        with self.assertRaises(ValueError):
            TunedCandidate.from_dict(payload)

    def test_search_is_self_supervised_and_json_resumable(self):
        tasks = (Task(64, "random", 300), Task(128, "reversed", 300))
        config = TuningConfig(
            population_size=4,
            elite_parents=2,
            children_per_parent=1,
            random_fraction=0.25,
        )
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "cost.sqlite"
            with EvaluationCostCache(cache_path) as cache:
                search = PrefixTuner(tasks, cache, seed=7, config=config)
                record = search.step()
                self.assertEqual(record["iteration"], 1)
                self.assertGreaterEqual(len(search.scores), 4)
                state = json.loads(json.dumps(search.state_dict()))
            with EvaluationCostCache(cache_path) as cache:
                restored = PrefixTuner(tasks, cache, seed=999, config=config)
                restored.load_state_dict(state)
                self.assertEqual(restored.best_candidate, search.best_candidate)
                self.assertEqual(restored.iteration, 1)
                before = restored.best_score.selection_key
                restored.step()
                self.assertLessEqual(restored.best_score.selection_key, before)

    def test_mutations_preserve_all_proof_constraints(self):
        tasks = (Task(64, "random", 300),)
        with tempfile.TemporaryDirectory() as directory:
            with EvaluationCostCache(Path(directory) / "cost.sqlite") as cache:
                search = PrefixTuner(tasks, cache, seed=2)
                candidate = TunedCandidate.base()
                for _ in range(200):
                    candidate = search._mutate(candidate, 0.25)
                    self.assertEqual(candidate.prefix[0], 1)
                    self.assertEqual(tuple(sorted(set(candidate.prefix))), candidate.prefix)
                    self.assertLess(candidate.prefix[-1], 1416)

    def test_new_test_panel_is_sealed_and_immutable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = TunedCandidate.base()
            candidates = root / "final_selected.json"
            candidates.write_text(json.dumps({
                "schema_version": 1,
                "artifact_type": "final_selected",
                "selection_stage": "validation",
                "source_program_hash": candidate.to_dict()["source_program_hash"],
                "primary_candidate_hash": candidate.candidate_hash,
                "candidates": [{
                    "candidate_hash": candidate.candidate_hash,
                    "candidate": candidate.to_dict(),
                    "selection_roles": ["validation_winner"],
                }],
            }))
            manifest = root / "experiment_manifest.json"
            protocol = {
                "min_n": 64,
                "max_n": 64,
                "points": 1,
                "seeds": [1999],
                "distributions": ["random"],
                "baselines": ["untuned", "sedgewick", "tokuda", "ciura"],
            }
            manifest.write_text(json.dumps({"test": protocol}))
            output = root / "test.json"
            command = [
                sys.executable,
                "scripts/evaluate_final.py",
                str(candidates),
                "--manifest",
                str(manifest),
                "--stage",
                "test",
                "--cache",
                str(root / "test.sqlite"),
                "--output",
                str(output),
            ]
            denied = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(denied.returncode, 0)
            completed = subprocess.run(
                command + ["--allow-test"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("complete", completed.stdout)
            result = json.loads(output.read_text())
            self.assertIn("test_decision", result)
            protocol["seeds"] = [2000]
            manifest.write_text(json.dumps({"test": protocol}))
            changed = subprocess.run(
                command + ["--allow-test"], capture_output=True, text=True
            )
            self.assertNotEqual(changed.returncode, 0)
            self.assertIn("refusing to overwrite", changed.stderr)


if __name__ == "__main__":
    unittest.main()
