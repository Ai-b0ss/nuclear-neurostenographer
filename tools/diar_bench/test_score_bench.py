"""Tests for score_bench.py, fingerprints and the reference check; no real audio or model output."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from build_corpus import der_reference_problem
from provenance import digest_of, run_fingerprint
from run_bench import is_current
import score_bench
from score_bench import StaleEvidence, aggregate, bootstrap, overlap_stats, recurrence, score_row, verify_case, verify_environment, verify_run


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


class Failures(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.case = {"id": "x", "group": "t", "scenario": "s", "speakers": 2, "duration_ms": 4000, "audio_sha256": "a" * 64}
        self.reference = {"schema_version": 1, "recording_id": "x", "annotation_source": "unit", "license": "unit", "kind": "UNIT",
                          "audio_sha256": "a" * 64, "audio_duration_ms": 4000, "diarization": [turn(0, 2000, "A"), turn(2000, 4000, "B")],
                          "text_segments": [dict(turn(0, 2000, "A"), text="раз два"), dict(turn(2000, 4000, "B"), text="три")]}
        self.reference_path = self.root / "ref.json"
        self.reference_path.write_text(json.dumps(self.reference, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        self.folder.cleanup()

    def row(self, status, runs=None):
        run = {"status": status, "wall_ms": 5}
        row = {"status": status, "scenario": "s", "system": "C0"}
        return score_row(row, self.case, run, self.root, self.reference_path, self.reference, runs or {}, "C0/x")

    def test_timeout_and_crash_are_scored_as_total_miss(self):
        for status in ("TIMEOUT", "FAIL", "FAIL_NATIVE", "FAIL_NO_OUTPUT", "NOT_RUN"):
            row = self.row(status)
            self.assertTrue(row["scored_as_empty_hypothesis"])
            self.assertEqual(row["der"]["collar0_overlap"]["rate"], 1.0)
            self.assertEqual(row["cpwer"]["deletions"], 3)
            self.assertNotIn("recurrence", row)

    def test_failed_file_stays_in_the_aggregate(self):
        good = {"status": "OK", "der": {"p": {"status": "SCORED", "miss_ms": 0, "false_alarm_ms": 0, "confusion_ms": 0, "reference_speaker_ms": 1000}}}
        bad = {"status": "TIMEOUT", "der": {"p": {"status": "SCORED", "miss_ms": 1000, "false_alarm_ms": 0, "confusion_ms": 0, "reference_speaker_ms": 1000}}}
        result = aggregate([good, bad], "p")
        self.assertEqual((result["n"], result["failed"], result["der"]), (2, 1, 0.5))

    def test_output_changed_after_the_run_is_refused(self):
        turns = self.root / "x.tsv"
        turns.write_text("0\t1000\t0\n", encoding="ascii")
        with self.assertRaises(StaleEvidence):
            verify_run({"fingerprint": "f", "turns_sha256": "0" * 64}, turns)
        with self.assertRaises(StaleEvidence):
            verify_run({"turns_sha256": score_bench.sha256_file(turns)}, turns)
        verify_run({"fingerprint": "f", "turns_sha256": score_bench.sha256_file(turns)}, turns)

    def test_changed_reference_or_audio_is_refused(self):
        (self.root / "x.wav").write_bytes(b"audio")
        (self.root / "x.ref.json").write_bytes(b"reference")
        case = {"id": "x", "audio_sha256": score_bench.sha256_file(self.root / "x.wav"), "reference_sha256": score_bench.sha256_file(self.root / "x.ref.json")}
        verify_case(case, self.root)
        (self.root / "x.ref.json").write_bytes(b"edited reference")
        with self.assertRaises(StaleEvidence):
            verify_case(case, self.root)


class Fingerprints(unittest.TestCase):
    base = {"system": "C0", "threshold": "0.8", "runtime": {"onnxruntime": "1.17.1"}, "models": {"m": "1"}, "code": {"c": "1"}}

    def test_every_input_changes_the_fingerprint(self):
        reference = run_fingerprint(self.base, "a" * 64)
        changes = [dict(self.base, threshold="0.9"), dict(self.base, models={"m": "2"}), dict(self.base, code={"c": "2"}), dict(self.base, runtime={"onnxruntime": "1.31"})]
        for config in changes:
            self.assertFalse(is_current({"fingerprint": reference}, run_fingerprint(config, "a" * 64)))
        self.assertFalse(is_current({"fingerprint": reference}, run_fingerprint(self.base, "b" * 64)))
        self.assertTrue(is_current({"fingerprint": reference}, run_fingerprint(self.base, "a" * 64)))

    def test_old_record_without_fingerprint_is_stale(self):
        self.assertFalse(is_current({"status": "OK"}, digest_of({})))
        self.assertFalse(is_current(None, digest_of({})))
        with self.assertRaises(StaleEvidence):
            verify_environment({"fingerprint": "old"}, "new")


class ReferenceCheck(unittest.TestCase):
    rate = 16000

    def signal(self, active_seconds, total_seconds):
        audio = np.zeros(total_seconds * self.rate, dtype=np.float32)
        audio[: active_seconds * self.rate] = 0.3 * np.sin(np.arange(active_seconds * self.rate) / 5)
        return audio

    def test_labels_covering_silence_are_rejected(self):
        problem = der_reference_problem([turn(0, 40000, "A")], self.signal(16, 40), self.rate)
        self.assertIn("covers", problem)

    def test_labels_that_follow_the_energy_pass(self):
        self.assertIsNone(der_reference_problem([turn(0, 16000, "A")], self.signal(16, 40), self.rate))

    def test_empty_reference_is_not_a_der_reference(self):
        self.assertIsNotNone(der_reference_problem([], self.signal(16, 40), self.rate))


if __name__ == "__main__":
    unittest.main()
