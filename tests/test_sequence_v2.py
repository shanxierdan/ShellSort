import random
import unittest

from core.sequence import EditAction, GapSequence, SequenceFamily
from core.shellsort import validate_gaps
from core.generator_v2 import LogPositionGenerator


class GapSequenceV2Tests(unittest.TestCase):
    def test_log_position_round_trip_is_legal(self):
        sequence = GapSequence.from_log_positions(1000, [0.9, 0.5, 0.2, 0.2])
        self.assertEqual(sequence.gaps[-1], 1)
        self.assertEqual(sequence.gaps, validate_gaps(sequence.gaps, 1000))
        rebuilt = GapSequence.from_dict(sequence.to_dict())
        self.assertEqual(rebuilt, sequence)
        self.assertEqual(rebuilt.semantic_hash, sequence.semantic_hash)

    def test_all_random_edits_remain_legal(self):
        rng = random.Random(7)
        sequence = GapSequence.random(4096, rng)
        for _ in range(2000):
            _, sequence = sequence.random_edit(rng, max_gaps=32)
            self.assertEqual(sequence.gaps, validate_gaps(sequence.gaps, sequence.n))

    def test_family_edit_applies_across_sizes(self):
        family = SequenceFamily.from_positions((64, 1024), (0.8, 0.5, 0.2))
        child = family.edit(EditAction("insert", value=0.35))
        self.assertNotEqual(family.family_hash, child.family_hash)
        self.assertEqual(tuple(x.n for x in child.sequences), (64, 1024))

    def test_distilled_generator_is_dynamic(self):
        family = SequenceFamily.from_positions((64, 1024), (0.85, 0.55, 0.25))
        generator = LogPositionGenerator.from_family(family)
        self.assertEqual(generator, LogPositionGenerator.from_dict(generator.to_dict()))
        self.assertNotEqual(generator.generate(1024), generator.generate(1_000_000))
        self.assertEqual(generator.generate(1_000_000)[-1], 1)
