import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch

from core.data import Task
from core.dsl import Expr, evaluate
from core.evaluation_v2 import AbsoluteBenchmark
from core.program_v3 import (
    GeneratorProgram,
    MUTATION_KINDS,
    Statement,
    mutate_program,
    random_program,
)
from core.search_v3 import ProgramSearchV3, SearchV3Config
from core.shellsort import validate_gaps
from model.program_model_v3 import GeneratorProgramNet, program_token_ids
from model.training_v3 import collate_v3, load_v3_checkpoint, save_v3_checkpoint, train_v3_step


class V3ProgramTests(unittest.TestCase):
    def test_power_saturates_before_constructing_a_huge_integer(self):
        integer_base = Expr("floor", (Expr.constant(1_000_000),))
        integer_exponent = Expr("floor", (Expr.constant(64),))
        expression = Expr("pow", (integer_base, integer_exponent))
        self.assertEqual(evaluate(expression, {}, bound=1_000_000), 1_000_000)

    def test_unified_program_can_emit_multiple_structures(self):
        n = Expr.variable("n")
        r0 = Expr.variable("r0")
        t = Expr.variable("t")
        program = GeneratorProgram(
            (Expr("div", (n, Expr.constant(2))),),
            (
                Statement("emit", r0),
                Statement("emit", Expr("pow", (Expr.constant(2), t))),
                Statement("assign", Expr("div", (r0, Expr.constant(2))), 0),
            ),
            fuel_base=1,
            fuel_log=2,
        )
        gaps = program.generate(100)
        self.assertEqual(gaps, validate_gaps(gaps, 100))
        self.assertIn(50, gaps)
        self.assertIn(64, gaps)
        self.assertEqual(GeneratorProgram.from_dict(program.to_dict()), program)

    def test_every_program_mutation_remains_executable(self):
        rng = random.Random(4)
        program = random_program(rng)
        for _ in range(500):
            program = mutate_program(program, rng.choice(MUTATION_KINDS), rng)
            for n in (32, 257, 4096):
                gaps = program.generate(n)
                self.assertEqual(gaps, validate_gaps(gaps, n))

    def test_program_tokens_are_stable(self):
        program = random_program(random.Random(3))
        self.assertEqual(program_token_ids(program), program_token_ids(GeneratorProgram.from_dict(program.to_dict())))

    def test_model_search_and_checkpoint_smoke(self):
        tasks = (Task(32, "random", 0), Task(64, "random", 0))
        with tempfile.TemporaryDirectory() as directory:
            benchmark = AbsoluteBenchmark(tasks, Path(directory) / "cache.sqlite")
            model = GeneratorProgramNet(hidden_size=32, layers=1, heads=4)
            optimizer = torch.optim.AdamW(model.parameters())
            search = ProgramSearchV3(
                model, benchmark, (32, 64), torch.device("cpu"), 2,
                SearchV3Config(population_size=4, elite_parents=2, children_per_parent=1),
            )
            record = search.step(1, lambda replay: None)
            self.assertGreater(record.replay_size, 0)
            sample = search.replay.sample(2, random.Random(1))
            metrics = train_v3_step(model, optimizer, collate_v3(sample, torch.device("cpu")))
            self.assertGreater(metrics["loss"], 0)
            state = search.state_dict()
            restored = ProgramSearchV3(
                model, benchmark, (32, 64), torch.device("cpu"), 9, search.config
            )
            restored.load_state_dict(state)
            self.assertEqual(len(restored.population), len(search.population))
            path = Path(directory) / "checkpoint.pt"
            save_v3_checkpoint(path, model, optimizer, 1, {"search": state})
            payload = load_v3_checkpoint(path, model, optimizer)
            self.assertEqual(payload["schema_version"], 3)

    def test_initialization_replaces_semantic_duplicate_without_leaving_unscored_program(self):
        n = Expr.variable("n")
        r0 = Expr.variable("r0")
        update = Statement("assign", Expr("div", (r0, Expr.constant(2))), 0)
        simple = GeneratorProgram(
            (Expr("div", (n, Expr.constant(2))),),
            (Statement("emit", r0), update),
            fuel_base=1,
            fuel_log=1,
        )
        complex_duplicate = GeneratorProgram(
            (Expr("div", (n, Expr.constant(2))), Expr.constant(123)),
            (Statement("emit", r0), update),
            fuel_base=1,
            fuel_log=1,
        )
        distinct = GeneratorProgram(
            (Expr("div", (n, Expr.constant(3))),),
            (Statement("emit", r0), update),
            fuel_base=1,
            fuel_log=1,
        )
        tasks = (Task(32, "random", 0),)
        with tempfile.TemporaryDirectory() as directory:
            benchmark = AbsoluteBenchmark(tasks, Path(directory) / "cache.sqlite")
            model = GeneratorProgramNet(hidden_size=32, layers=1, heads=4)
            search = ProgramSearchV3(
                model, benchmark, (32,), torch.device("cpu"), 0,
                SearchV3Config(population_size=2, elite_parents=1, children_per_parent=1),
            )
            with patch(
                "core.search_v3.random_program",
                side_effect=(complex_duplicate, simple, distinct),
            ):
                search.initialize()
            self.assertEqual(len(search.population), 2)
            self.assertIn(simple.program_hash, {x.program_hash for x in search.population})
            self.assertNotIn(complex_duplicate.program_hash, {x.program_hash for x in search.population})
            self.assertTrue(all(x.program_hash in search.scores for x in search.population))

    def test_export_always_contains_scalar_training_winner(self):
        tasks = (Task(32, "random", 0), Task(64, "random", 0))
        with tempfile.TemporaryDirectory() as directory:
            benchmark = AbsoluteBenchmark(tasks, Path(directory) / "cache.sqlite")
            model = GeneratorProgramNet(hidden_size=32, layers=1, heads=4)
            search = ProgramSearchV3(
                model, benchmark, (32, 64), torch.device("cpu"), 2,
                SearchV3Config(population_size=4, elite_parents=2, children_per_parent=1),
            )
            search.step(1, lambda replay: None)
            winner = search.best_program
            search.archive._items.pop(winner.program_hash, None)
            exported = {x[0].program_hash for x in search.candidate_items()}
            self.assertIn(winner.program_hash, exported)

    def test_full_population_initializes_for_every_experiment_seed(self):
        tasks = (Task(32, "random", 0),)
        with tempfile.TemporaryDirectory() as directory:
            benchmark = AbsoluteBenchmark(tasks, Path(directory) / "cache.sqlite")
            model = GeneratorProgramNet(hidden_size=32, layers=1, heads=4)
            for seed in range(5):
                search = ProgramSearchV3(
                    model, benchmark, (32,), torch.device("cpu"), seed,
                    SearchV3Config(population_size=48, elite_parents=12, children_per_parent=1),
                )
                search.initialize()
                self.assertEqual(len(search.population), 48, seed)
                self.assertTrue(all(x.program_hash in search.scores for x in search.population), seed)


if __name__ == "__main__":
    unittest.main()
