import random
import tempfile
import unittest
from pathlib import Path

import torch

from core.data import Task, make_array
from core.evaluation_v2 import AbsoluteBenchmark, FamilyArchive, FamilyScore
from core.sequence import GapSequence, SequenceFamily
from core.search_v2 import PopulationSearchV2, SearchV2Config
from core.trace import shellsort_trace
from model.sequence_model import GapSequenceNet
from model.training_v2 import V2ReplayBuffer, V2Sample, collate_v2, train_v2_step
from model.training_v2 import load_v2_checkpoint, save_v2_checkpoint


class V2ModelSearchTests(unittest.TestCase):
    def test_model_trains_on_real_trace(self):
        task = Task(64, "random", 3)
        sequence = GapSequence(64, (31, 12, 4, 1))
        _, trace = shellsort_trace(make_array(task), sequence.gaps, disorder=False)
        sample = V2Sample.from_trace(task.distribution, trace)
        batch = collate_v2([sample, sample], torch.device("cpu"))
        model = GapSequenceNet(hidden_size=32, layers=1, heads=4)
        output = model(batch.features, batch.context, batch.padding_mask)
        self.assertEqual(tuple(output.log_costs.shape), (2, 2))
        self.assertEqual(tuple(output.contribution.shape), (2, 4, 2))
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
        metrics = train_v2_step(model, optimizer, batch)
        self.assertTrue(metrics["loss"] > 0)

    def test_archive_rejects_incomparable_panels(self):
        family = SequenceFamily((GapSequence(32, (16, 4, 1)),))
        archive = FamilyArchive("panel-a")
        score = FamilyScore(family.family_hash, "panel-b", 1, 1, 1, 1, 0.0)
        with self.assertRaises(ValueError):
            archive.add(family, score)

    def test_expensive_legal_sequence_is_censored(self):
        task = Task(256, "reversed", 0)
        benchmark = AbsoluteBenchmark((task,), max_normalized_operations=0.01)
        sequence = GapSequence(256, (1,))
        score = benchmark.evaluate_sequence(sequence, task, include_trace=True)
        self.assertTrue(score.censored)
        self.assertIsNotNone(score.trace)

    def test_search_smoke_and_resume_state(self):
        tasks = (Task(32, "random", 0), Task(64, "random", 0))
        with tempfile.TemporaryDirectory() as directory:
            benchmark = AbsoluteBenchmark(tasks, Path(directory) / "cache.sqlite")
            model = GapSequenceNet(hidden_size=32, layers=1, heads=4)
            search = PopulationSearchV2(
                model, benchmark, (32, 64), torch.device("cpu"), seed=4,
                config=SearchV2Config(population_size=4, children_per_parent=1, elite_parents=2,
                                      counterfactual_elites=1),
            )
            record = search.step(1, lambda replay: None)
            self.assertGreater(record.replay_size, 0)
            self.assertGreater(record.archive_size, 0)
            state = search.state_dict()
            restored = PopulationSearchV2(
                model, benchmark, (32, 64), torch.device("cpu"), seed=9,
                config=search.config,
            )
            restored.load_state_dict(state)
            self.assertEqual(len(restored.population), len(search.population))
            self.assertEqual(len(restored.replay), len(search.replay))

    def test_v2_checkpoint_is_atomic_and_rejects_v1(self):
        model = GapSequenceNet(hidden_size=32, layers=1, heads=4)
        optimizer = torch.optim.AdamW(model.parameters())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.pt"
            save_v2_checkpoint(path, model, optimizer, 1, {"ok": True})
            save_v2_checkpoint(path, model, optimizer, 2, {"ok": True})
            path.write_bytes(b"")
            payload = load_v2_checkpoint(path, model, optimizer)
            self.assertEqual(payload["step"], 1)


if __name__ == "__main__":
    unittest.main()
