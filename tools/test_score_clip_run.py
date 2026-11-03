"""Authored data: reference clamping and hypothesis building for score_clip_run.py."""
import unittest

import score_clip_run


class ClampTests(unittest.TestCase):
    def reference(self):
        return {"recording_id": "x", "audio_sha256": "a" * 64, "audio_duration_ms": 1000,
                "text_segments": [{"start_ms": 0, "end_ms": 600, "speaker_id": "1", "text": "а"},
                                  {"start_ms": 600, "end_ms": 1003, "speaker_id": "2", "text": "б"}],
                "diarization": [{"start_ms": 600, "end_ms": 1003, "speaker_id": "2"}]}

    def test_end_past_the_audio_is_clamped_and_the_input_is_not_modified(self):
        original = self.reference()
        fixed = score_clip_run.clamp_reference(original)
        self.assertEqual(fixed["text_segments"][1]["end_ms"], 1000)
        self.assertEqual(fixed["diarization"][0]["end_ms"], 1000)
        self.assertEqual(original["text_segments"][1]["end_ms"], 1003)

    def test_a_segment_starting_after_the_end_keeps_a_valid_interval(self):
        reference = self.reference()
        reference["text_segments"][1]["start_ms"] = 1002
        fixed = score_clip_run.clamp_reference(reference)
        self.assertLess(fixed["text_segments"][1]["start_ms"], fixed["text_segments"][1]["end_ms"])

    def test_hypothesis_carries_the_reference_identity_and_only_scored_keys(self):
        export = {"audio_duration_ms": 1000, "segments": [{"start_ms": 0, "end_ms": 5, "speaker_id": "Speaker 1",
                                                           "text": "а", "overlapping_speech": False}]}
        hypothesis = score_clip_run.hypothesis_from_export(export, self.reference())
        self.assertEqual(hypothesis["audio_sha256"], "a" * 64)
        self.assertEqual(set(hypothesis["segments"][0]), {"start_ms", "end_ms", "speaker_id", "text"})


if __name__ == "__main__":
    unittest.main()
