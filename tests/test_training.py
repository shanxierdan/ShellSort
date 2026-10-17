import random
import tempfile
import unittest
from pathlib import Path

import torch

from core.grammar import PRODUCTIONS, VOCAB_SIZE
from model.network import PolicyValueFeasibilityNet
from model.pretrain import curated_samples
from model.training import collate, load_checkpoint, save_checkpoint, train_step
from model.policy_iteration import PolicyIteration
from core.data import Task
from core.evaluation import Benchmark


class TrainingTests(unittest.TestCase):
    def test_curated_samples_train_and_checkpoint(self) -> None:
        samples = curated_samples()
        model = PolicyValueFeasibilityNet(VOCAB_SIZE, len(PRODUCTIONS), hidden_size=32, layers=1)
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
        batch = collate(random.Random(0).sample(samples, 4), torch.device("cpu"))
        metrics = train_step(model, optimizer, batch)
        self.assertTrue(metrics["loss"] > 0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.pt"
            save_checkpoint(path, model, optimizer, step=1)
            payload = load_checkpoint(path, model, optimizer)
            self.assertEqual(payload["step"], 1)

    def test_replay_migration_clamps_value_targets(self) -> None:
        model = PolicyValueFeasibilityNet(VOCAB_SIZE, len(PRODUCTIONS), hidden_size=32, layers=1)
        trainer = PolicyIteration(model, Benchmark([Task(8, "random", 0)]), device="cpu")
        sample = curated_samples()[0]
        trainer.load_state_dict({"replay_samples": [sample.__class__(sample.tokens, sample.policy, -5.0, 0.0, sample.legal_actions)]})
        self.assertEqual(trainer.replay.samples[0].value, -1.0)

    def test_checkpoint_falls_back_to_previous_copy(self) -> None:
        model = PolicyValueFeasibilityNet(VOCAB_SIZE, len(PRODUCTIONS), hidden_size=32, layers=1)
        optimizer = torch.optim.AdamW(model.parameters())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.pt"
            save_checkpoint(path, model, optimizer, step=1)
            save_checkpoint(path, model, optimizer, step=2)
            path.write_bytes(b"")
            payload = load_checkpoint(path, model)
            self.assertEqual(payload["step"], 1)
