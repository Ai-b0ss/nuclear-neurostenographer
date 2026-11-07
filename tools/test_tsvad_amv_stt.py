import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tsvad_amv_stt.adapter import AmvOverlapResolverAdapter, from_amv_intervals, to_amv_intervals, verify_upstream
from tsvad_amv_stt.evaluate import evaluate_pair, score_activity
from tsvad_amv_stt.upstream.overlap_resolver import OverlapResolver


def turn(start, end, speaker):
    return {"start_ms": start, "end_ms": end, "speaker_id": speaker}


class FakeStream:
    def accept_waveform(self, sample_rate, waveform):
        self.sample_rate = sample_rate
        self.waveform = waveform

    def input_finished(self):
        pass


class FakeExtractor:
    def create_stream(self):
        return FakeStream()

    def compute(self, stream):
        if np.mean(stream.waveform) > 0.5:
            return np.array([0.0, 1.0], dtype=np.float32)
        return np.array([1.0, 0.0], dtype=np.float32)


class FakeTrajectoryResolver(OverlapResolver):
    def build_voiceprint_profiles(self, samples, sr, intervals, extractor):
        return {0: np.array([1.0, 0.0]), 1: np.array([0.0, 1.0])}

    def scan_multi_label_trajectory(self, samples, sr, start_sec, end_sec, profiles, extractor):
        return [(2.0, 3.0, {0: 0.1, 1: 0.9})]


class UpstreamAdapterTests(unittest.TestCase):
    def test_pinned_source_and_license_hashes(self):
        provenance = verify_upstream()
        self.assertEqual(provenance["commit"], "b063c273749b72002e7d498a2eb9a8e07e11721b")
        self.assertEqual(provenance["source_spdx"], "Apache-2.0 OR Commercial-License")

    def test_common_interval_conversion_round_trip(self):
        intervals = [turn(0, 700, "A"), turn(150, 850, "B")]
        self.assertEqual(from_amv_intervals(to_amv_intervals(intervals)), intervals)
        with self.assertRaises(ValueError):
            to_amv_intervals([turn(10, 10, "A")])
        with self.assertRaises(ValueError):
            to_amv_intervals([turn(0, 10, None)])

    def test_fake_extractor_produces_profiles_and_trajectory(self):
        sample_rate = 16000
        samples = np.zeros(sample_rate * 8, dtype=np.float32)
        samples[int(3.2 * sample_rate):int(4.0 * sample_rate)] = 1.0
        samples[int(6.0 * sample_rate):] = 1.0
        resolver = OverlapResolver()
        extractor = FakeExtractor()
        profiles = resolver.build_voiceprint_profiles(
            samples, sample_rate, [(0.0, 6.0, 0), (6.0, 8.0, 1)], extractor
        )
        self.assertEqual(set(profiles), {0, 1})
        trajectory = resolver.scan_multi_label_trajectory(
            samples, sample_rate, 0.0, 6.0, profiles, extractor
        )
        self.assertTrue(trajectory)
        self.assertTrue(any(scores[1] > scores[0] for _, _, scores in trajectory))

    def test_fake_trajectory_changes_only_intervals(self):
        document = {
            "audio_duration_ms": 7000,
            "diarization": [turn(0, 5000, 0), turn(5000, 7000, 1)],
            "segments": [dict(turn(0, 5000, 0), text="unchanged")],
        }
        original = copy.deepcopy(document)
        samples = np.arange(7000 * 16, dtype=np.float32)
        samples_before = samples.copy()
        output = AmvOverlapResolverAdapter(resolver=FakeTrajectoryResolver()).resolve(
            document, samples, 16000, object()
        )
        self.assertEqual(document, original)
        self.assertEqual(output["segments"], document["segments"])
        self.assertEqual(
            output["diarization"],
            [turn(0, 2000, 0), turn(2000, 3000, 1), turn(3000, 5000, 0), turn(5000, 7000, 1)],
        )
        np.testing.assert_array_equal(samples, samples_before)
        self.assertNotIn("samples", output)
        self.assertNotIn("tracks", output)

    def test_short_interval_is_unchanged(self):
        document = {"diarization": [turn(0, 1000, 0), turn(1000, 2000, 1)]}
        output = AmvOverlapResolverAdapter().resolve(
            document, np.zeros(32000, dtype=np.float32), 16000, FakeExtractor()
        )
        self.assertEqual(output["diarization"], document["diarization"])


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.reference = {
            "annotation_source": "manual common reference",
            "audio_duration_ms": 6000,
            "diarization": [turn(0, 4000, "A"), turn(2000, 6000, "B")],
        }

    def test_perfect_candidate_has_zero_activity_error(self):
        score = score_activity(self.reference, self.reference)
        self.assertEqual(score["miss_ms"], 0)
        self.assertEqual(score["false_alarm_ms"], 0)
        self.assertEqual(score["activity_error_rate"], 0.0)
        self.assertEqual(score["overlap_recall"], 1.0)
        self.assertEqual(score["overlap_precision"], 1.0)

    def test_activity_and_overlap_counts(self):
        hypothesis = {
            "audio_duration_ms": 6000,
            "diarization": [turn(0, 5000, "A"), turn(3000, 5000, "B")],
        }
        score = score_activity(self.reference, hypothesis)
        self.assertEqual(score["reference_speech_ms"], 6000)
        self.assertEqual(score["hypothesis_speech_ms"], 5000)
        self.assertEqual(score["miss_ms"], 1000)
        self.assertEqual(score["false_alarm_ms"], 0)
        self.assertEqual(score["reference_overlap_ms"], 2000)
        self.assertEqual(score["hypothesis_overlap_ms"], 2000)
        self.assertEqual(score["overlap_both_ms"], 1000)
        self.assertEqual(score["overlap_recall"], 0.5)
        self.assertEqual(score["overlap_precision"], 0.5)
        self.assertAlmostEqual(score["activity_error_rate"], 1 / 6)

    def test_pair_reports_candidate_delta(self):
        baseline = {"audio_duration_ms": 6000, "diarization": [turn(0, 4000, "A")]}
        report = evaluate_pair(self.reference, baseline, self.reference)
        self.assertEqual(report["baseline"]["overlap_recall"], 0.0)
        self.assertEqual(report["candidate_minus_baseline"]["overlap_recall"], 1.0)
        self.assertEqual(report["candidate_minus_baseline"]["activity_error_rate"], -1 / 3)

    def test_non_manual_reference_is_rejected(self):
        reference = dict(self.reference, annotation_source="automatic VAD")
        with self.assertRaises(ValueError):
            score_activity(reference, reference)

    def test_cli_scores_common_schema_documents(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            baseline = {"audio_duration_ms": 6000, "diarization": [turn(0, 4000, "A")]}
            for name, value in (("reference", self.reference), ("baseline", baseline), ("candidate", self.reference)):
                (root / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")
            env = dict(os.environ)
            env["PYTHONPATH"] = str(Path(__file__).resolve().parent)
            subprocess.run(
                [sys.executable, "-m", "tsvad_amv_stt.evaluate", "--reference", str(root / "reference.json"),
                 "--baseline", str(root / "baseline.json"), "--candidate", str(root / "candidate.json"),
                 "--output", str(root / "score.json")],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            report = json.loads((root / "score.json").read_text(encoding="utf-8"))
            self.assertEqual(report["candidate"]["status"], "SCORED")
            self.assertEqual(report["candidate"]["activity_error_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
