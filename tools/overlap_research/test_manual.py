"""Authored structural tests with temporary PCM; no real-data accuracy claims."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from common import LOCAL, sha
from make_dev import write_wav
from manual_manifest import KIND, adapt, validate
from manual_metrics import word_recovery
from export_manual import export


class ManualFixture(unittest.TestCase):
    def setUp(self):
        LOCAL.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=LOCAL)
        self.root = Path(self.temporary.name)
        self.audio = self.root / "fragment.wav"
        write_wav(self.audio, np.full(80000, 0.01, np.float32))
        self.enroll_a = self.root / "enroll-a.wav"
        self.enroll_b = self.root / "enroll-b.wav"
        write_wav(self.enroll_a, np.full(48000, 0.1, np.float32))
        write_wav(self.enroll_b, np.full(48000, 0.2, np.float32))
        self.reference = dict(
            schema_version=1, recording_id="unit-real", kind=KIND,
            annotation_source="authored structural unit test", license="test",
            audio_sha256=sha(self.audio), audio_duration_ms=5000,
            text_segments=[dict(start_ms=1000, end_ms=1100, speaker_id="caller", text="alpha"),
                           dict(start_ms=1050, end_ms=1150, speaker_id="callee", text="beta"),
                           dict(start_ms=2000, end_ms=2100, speaker_id="caller", text="gamma")],
            diarization=[dict(start_ms=500, end_ms=2500, speaker_id="caller"),
                         dict(start_ms=900, end_ms=1800, speaker_id="callee")])
        self.reference_path = self.root / "reference.json"
        self.reference_path.write_text(json.dumps(self.reference), encoding="utf-8")
        self.manifest_path = self.root / "input.json"
        self.manifest_path.write_text(json.dumps(self.manifest()), encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def manifest(self):
        return dict(schema_version=1, kind=KIND, enrollment_mode="manual", cases=[dict(
            id="unit-real", audio_path="fragment.wav", audio_sha256=sha(self.audio),
            reference_path="reference.json", reference_sha256=sha(self.reference_path),
            enrollments=[dict(speaker_id="caller", selection="manual", wav_path="enroll-a.wav", sha256=sha(self.enroll_a)),
                         dict(speaker_id="callee", selection="manual", wav_path="enroll-b.wav", sha256=sha(self.enroll_b))])])

    def rewrite(self, manifest):
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def test_valid_adapter_is_hash_bound_and_immutable(self):
        output = self.root / "adapted"
        normalized = adapt(self.manifest_path, output)
        self.assertEqual(normalized["enrollment_mode"], "manual")
        self.assertEqual(len(normalized["cases"][0]["enrollments"]), 2)
        self.assertTrue(Path(normalized["cases"][0]["audio_path"]).is_absolute())
        self.assertNotIn("alpha", (output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(validate(output / "manifest.json")["cases"], normalized["cases"])
        with self.assertRaisesRegex(ValueError, "already exists"):
            adapt(self.manifest_path, output)

    def test_automatic_or_synthetic_manifest_is_rejected(self):
        for key, value in (("enrollment_mode", "strict-c2"), ("kind", "SYNTHETIC_DEV_FROM_ACTED_SOURCES")):
            with self.subTest(key=key):
                manifest = self.manifest()
                manifest[key] = value
                self.rewrite(manifest)
                with self.assertRaises(ValueError):
                    validate(self.manifest_path)

    def test_missing_short_and_duplicate_enrollment_have_no_fallback(self):
        manifest = self.manifest()
        manifest["cases"][0]["enrollments"] = []
        self.rewrite(manifest)
        with self.assertRaisesRegex(ValueError, "exactly two"):
            validate(self.manifest_path)
        write_wav(self.enroll_a, np.full(47999, 0.1, np.float32))
        manifest = self.manifest()
        self.rewrite(manifest)
        with self.assertRaisesRegex(ValueError, "48000"):
            validate(self.manifest_path)
        write_wav(self.enroll_a, np.full(48000, 0.2, np.float32))
        manifest = self.manifest()
        self.rewrite(manifest)
        with self.assertRaisesRegex(ValueError, "identical enrollment"):
            validate(self.manifest_path)

    def test_hash_and_manual_overlap_guards(self):
        manifest = self.manifest()
        manifest["cases"][0]["audio_sha256"] = "0" * 64
        self.rewrite(manifest)
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            validate(self.manifest_path)
        self.reference["diarization"][1] = dict(start_ms=3000, end_ms=3500, speaker_id="callee")
        self.reference_path.write_text(json.dumps(self.reference), encoding="utf-8")
        self.rewrite(self.manifest())
        with self.assertRaisesRegex(ValueError, "no speaker overlap"):
            validate(self.manifest_path)

    def test_word_recovery_is_one_to_one_and_identity_agnostic(self):
        reference = self.reference
        baseline = [dict(start_ms=990, end_ms=1110, speaker_id=None, text="alpha")]
        candidate = [dict(start_ms=990, end_ms=1110, speaker_id=None, text="alpha"),
                     dict(start_ms=1040, end_ms=1160, speaker_id=None, text="beta"),
                     dict(start_ms=1050, end_ms=1170, speaker_id=None, text="beta")]
        result = word_recovery(reference, baseline, candidate)
        self.assertEqual(result["reference_overlap_words"], 2)
        self.assertEqual(result["baseline_correct_words"], 1)
        self.assertEqual(result["candidate_correct_words"], 2)
        self.assertEqual(result["recovered_correct_words"], 1)
        self.assertEqual(word_recovery(reference, candidate, baseline)["recovered_correct_words"], -1)

    def test_exporter_schema_and_honor_not_run(self):
        adapted = self.root / "for-export"
        adapt(self.manifest_path, adapted)
        fixture_path = adapted / "manifest.json"
        run = dict(status="COMPLETE", protocol=dict(fixture_manifest_sha256=sha(fixture_path), enrollment_mode="manual"),
                   rows=[dict(case="unit-real",
                              baseline=dict(wer=dict(status="SCORED", errors=2, reference_words=3, rate=2 / 3), unknown_words=1),
                              candidate=dict(wer=dict(status="SCORED", errors=1, reference_words=3, rate=1 / 3), unknown_words=2),
                              word_recovery=dict(recovered_correct_words=1),
                              host=dict(baseline_wall_rtf=1.0, candidate_wall_rtf=2.0))])
        run_path = self.root / "summary.json"
        run_path.write_text(json.dumps(run), encoding="utf-8")
        score_path = self.root / "score.json"
        fixture_output = self.root / "fixture-manifest.json"
        report = export(fixture_path, run_path, score_path, fixture_output)
        self.assertEqual(report["baseline"]["wer"]["errors"], 2)
        self.assertEqual(report["candidate"]["wer"]["errors"], 1)
        self.assertEqual(report["recovered_correct_words"], 1)
        self.assertEqual((report["unknown_words_before"], report["unknown_words_after"]), (1, 2))
        self.assertEqual(report["host"]["pss_status"], "NOT_MEASURED")
        self.assertEqual(report["honor"]["status"], "NOT_RUN")
        self.assertNotIn("audio_path", fixture_output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
