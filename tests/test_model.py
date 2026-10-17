import unittest

import torch

from model import PolicyValueFeasibilityNet


class ModelTests(unittest.TestCase):
    def test_model_output_shapes(self) -> None:
        model = PolicyValueFeasibilityNet(vocab_size=32, action_size=11, hidden_size=32, layers=1)
        output = model(torch.randint(0, 32, (3, 7)))
        self.assertEqual(output.policy_logits.shape, (3, 11))
        self.assertEqual(output.value.shape, (3,))
        self.assertEqual(output.feasibility_logit.shape, (3,))
