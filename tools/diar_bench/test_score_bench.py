"""Arithmetic tests for the metrics added by score_bench.py; no audio or model output."""
import unittest

from score_bench import bootstrap, overlap_stats, recurrence


def turn(start, end, speaker):
    return {"start_ms": start, "end_ms": end, "speaker_id": speaker}


class Metrics(unittest.TestCase):
    def test_recurrence_passes_aba_with_any_cluster_names(self):
        reference = [turn(0, 2000, "A"), turn(2000, 4000, "B"), turn(4000, 6000, "A")]
        result = recurrence(reference, [(0, 2000, 7), (2000, 4000, 3), (4000, 6000, 7)])
        self.assertEqual((result["same_correct"], result["same_pairs"]), (1, 1))
        self.assertEqual((result["different_correct"], result["different_pairs"]), (2, 2))

    def test_new_cluster_on_return_is_a_failure(self):
        reference = [turn(0, 2000, "A"), turn(2000, 4000, "B"), turn(4000, 6000, "A")]
        self.assertEqual(recurrence(reference, [(0, 2000, 0), (2000, 4000, 1), (4000, 6000, 2)])["same_correct"], 0)

    def test_collapsed_voices_fail_the_different_check(self):
        reference = [turn(0, 2000, "A"), turn(2000, 4000, "B")]
        self.assertEqual(recurrence(reference, [(0, 4000, 0)])["different_correct"], 0)

    def test_missing_speech_never_counts_as_correct(self):
        reference = [turn(0, 2000, "A"), turn(2000, 4000, "B"), turn(4000, 6000, "A")]
        result = recurrence(reference, [])
        self.assertEqual((result["same_correct"], result["different_correct"]), (0, 0))

    def test_overlap_recall_and_precision_counts(self):
        reference = [turn(0, 2000, "A"), turn(1000, 3000, "B")]
        result = overlap_stats(reference, [(0, 1500, 0), (500, 3000, 1)], 3000)
        self.assertEqual(result, {"reference_overlap_ms": 1000, "hypothesis_overlap_ms": 1000, "overlap_both_ms": 500})

    def test_bootstrap_of_constant_difference_is_exact(self):
        low, high = bootstrap([(10, 20, 100), (10, 20, 100), (10, 20, 100)])
        self.assertAlmostEqual(low, 0.1)
        self.assertAlmostEqual(high, 0.1)


if __name__ == "__main__":
    unittest.main()
