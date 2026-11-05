"""Authored data: reference clamping and hypothesis building for score_clip_run.py."""
import unittest
import hashlib
from pathlib import Path
import tempfile
import json
import subprocess
import sys

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

    def test_unreliable_attribution_survives_export_adapter(self):
        export={"audio_duration_ms":1000,"segments":[{"start_ms":0,"end_ms":500,"speaker_id":"Speaker 1",
                "text":"word","attribution_reliable":False}]}
        hyp=score_clip_run.hypothesis_from_export(export,self.reference())
        self.assertIs(hyp['segments'][0]['attribution_reliable'],False)

    def test_audio_identity_requires_actual_matching_bytes(self):
        ref=self.reference();export=dict(audio_duration_ms=1000,segments=[])
        self.assertIn('NOT_INDEPENDENTLY_VERIFIED',score_clip_run.hypothesis_from_export(export,ref)['audio_identity_verification'])
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'trusted-input.wav';p.write_bytes(b'authored unit fixture, not audio')
            with self.assertRaises(ValueError):score_clip_run.hypothesis_from_export(export,ref,p)
            ref['audio_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertEqual(score_clip_run.hypothesis_from_export(export,ref,p)['audio_identity_verification'],'WAV_HASH_VERIFIED')
            with self.assertRaises(ValueError):score_clip_run.hypothesis_from_export(dict(export,audio_sha256='0'*64),ref,p)

    def test_cli_hash_error_tombstones_previous_favorable_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'ref.json').write_text(json.dumps(self.reference()),encoding='utf-8')
            (p/'export.json').write_text(json.dumps(dict(audio_duration_ms=1000,segments=[])),encoding='utf-8')
            (p/'input.wav').write_bytes(b'authored wrong bytes, not audio')
            (p/'export.score.json').write_text('{"wer":{"rate":0}}',encoding='utf-8')
            r=subprocess.run([sys.executable,str(Path(score_clip_run.__file__)),'--reference',str(p/'ref.json'),
                '--export',str(p/'export.json'),'--audio',str(p/'input.wav'),'--out-dir',str(p)],capture_output=True)
            self.assertNotEqual(r.returncode,0)
            self.assertEqual(json.loads((p/'export.score.json').read_text())['status'],'ERROR')


if __name__ == "__main__":
    unittest.main()
