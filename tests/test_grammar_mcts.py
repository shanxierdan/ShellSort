import unittest

from core.data import Task
from core.evaluation import Benchmark
from core.grammar import ACTION_BY_NAME, SearchState, VOCAB_SIZE
from core.mcts import PUCTSearch


class GrammarMctsTests(unittest.TestCase):
    def test_recursive_program_builds_from_actions(self) -> None:
        state = SearchState(max_nodes=8)
        names = (
            "template_recursive",
            "floor", "div", "var_n", "const_2",
            "floor", "div", "var_h", "const_2",
        )
        for name in names:
            state = state.apply(ACTION_BY_NAME[name])
        self.assertTrue(state.terminal)
        self.assertEqual(state.build().generate(20), (10, 5, 2, 1))
        self.assertTrue(all(0 <= token < VOCAB_SIZE for token in state.token_ids()))

    def test_action_mask_rejects_context_invalid_variable(self) -> None:
        state = SearchState().apply(ACTION_BY_NAME["template_recursive"])
        self.assertNotIn(ACTION_BY_NAME["var_h"], state.legal_actions())
        self.assertIn(ACTION_BY_NAME["var_n"], state.legal_actions())

    def test_enumerative_program_has_typed_keep_predicate(self) -> None:
        state = SearchState(max_nodes=12)
        names = (
            "template_enumerative", "bound_4", "bound_4",
            "mul", "pow", "const_2", "var_a", "pow", "const_3", "var_b",
            "lt", "var_g", "var_n",
        )
        for name in names:
            state = state.apply(ACTION_BY_NAME[name])
        self.assertTrue(state.terminal)
        self.assertEqual(state.build().generate(20), (18, 16, 12, 9, 8, 6, 4, 3, 2, 1))

    def test_uniform_puct_completes_a_program(self) -> None:
        benchmark = Benchmark([Task(16, "random", 0)])
        search = PUCTSearch(benchmark, simulations=8, seed=0)
        state = SearchState(max_nodes=4)
        for _ in range(20):
            if state.terminal:
                break
            policy = search.policy(state)
            self.assertAlmostEqual(sum(policy), 1.0)
            state = state.apply(search.sample_action(policy))
        self.assertTrue(state.terminal)
