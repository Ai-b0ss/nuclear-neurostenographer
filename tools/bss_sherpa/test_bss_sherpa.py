import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import wave

import numpy as np

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("bss_sherpa_run", HERE / "run.py")
bss = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bss)


def write_pcm16(path, sample_rate=44100, channels=2, frames=128, sample_width=2):
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(channels)
        stream.setsampwidth(sample_width)
        stream.setframerate(sample_rate)
        stream.writeframes(bytes(frames * channels * sample_width))


class BssSherpaTests(unittest.TestCase):
    def test_lock_is_complete_and_weights_are_not_committed(self):
        lock = bss.load_lock()
        self.assertEqual(lock["runtime"]["source_commit"], "174f8684fa9a0e188ba9b9f3ac04b17cfd44379b")
        self.assertEqual(len(lock["model"]["sha256"]), 64)
        self.assertFalse(lock["model"]["weights_committed"])
        self.assertFalse(lock["runtime"]["production_runtime_changed"])
        self.assertEqual(lock["model"]["domain"], "MUSIC_VOCALS_NOT_MEETING_SPEAKER_SEPARATION")
        self.assertFalse(lock["capabilities"]["sepformer"])
        self.assertFalse(lock["capabilities"]["mossformer2"])
        self.assertFalse(lock["capabilities"]["speaker_separation"])

    def test_verify_file_fails_closed_on_hash_and_size(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "model"
            path.write_bytes(b"expected")
            expected = {"bytes": 8, "sha256": bss.sha256(path)}
            self.assertEqual(bss.verify_file(path, expected)["bytes"], 8)
            with self.assertRaises(ValueError):
                bss.verify_file(path, expected | {"sha256": "0" * 64})
            with self.assertRaises(ValueError):
                bss.verify_file(path, expected | {"bytes": 9})

    def test_wav_input_requires_pcm16_44100_and_duplicates_mono(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.wav"
            write_pcm16(path, channels=1)
            samples, rate = bss.read_wav(path)
            self.assertEqual((samples.shape, samples.dtype, rate), ((2, 128), np.float32, 44100))
            write_pcm16(path, sample_rate=16000)
            with self.assertRaisesRegex(ValueError, "44100"):
                bss.read_wav(path)
            write_pcm16(path, sample_width=1)
            with self.assertRaisesRegex(ValueError, "PCM16"):
                bss.read_wav(path)

    def test_track_round_trip_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.wav"
            write_pcm16(source)
            output = root / "tracks"
            output.mkdir()
            samples = np.zeros((2, 128), dtype=np.float32)
            for name in bss.TRACK_NAMES:
                bss.write_wav(output / f"{name}.wav", samples, 44100)
            manifest = bss.tracks_manifest(output, source, 0.25)
            (output / "tracks.json").write_text(json.dumps(manifest), encoding="utf-8")
            result = bss.validate_tracks(output)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["decision"], "A3_HANDOFF_READY_NOT_RUN")
            self.assertIsNone(manifest["a3"]["wer"])
            (output / "vocals.wav").write_bytes(b"tampered")
            with self.assertRaises(ValueError):
                bss.validate_tracks(output)

    def test_track_validation_rejects_speaker_or_metric_claims(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.wav"
            write_pcm16(source)
            output = root / "tracks"
            output.mkdir()
            for name in bss.TRACK_NAMES:
                bss.write_wav(output / f"{name}.wav", np.zeros((2, 128), dtype=np.float32), 44100)
            manifest = bss.tracks_manifest(output, source, 0.25)
            manifest["kind"] = "SPEAKER_SEPARATION"
            (output / "tracks.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not speaker separation"):
                bss.validate_tracks(output)
            manifest = bss.tracks_manifest(output, source, 0.25)
            manifest["a3"]["wer"] = 0.0
            (output / "tracks.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsubstantiated"):
                bss.validate_tracks(output)

    def test_generated_fixture_is_deterministic_and_not_speech(self):
        with tempfile.TemporaryDirectory() as temp:
            first = bss.make_fixture(Path(temp) / "first.wav")
            second = bss.make_fixture(Path(temp) / "second.wav")
            self.assertEqual(first["sha256"], second["sha256"])
            self.assertEqual(first["sha256"], "ea1ec37e83998137f9deaa3efcd9a3ea3af6c0d1e3cf144788264058fbff0941")
            self.assertEqual(first["kind"], "GENERATED_NUMERIC_TONES_NOT_SPEECH")

    def test_native_model_path_preserves_existing_unicode_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "модель" / "model.onnx"
            path.parent.mkdir()
            path.write_bytes(b"model")
            native = bss.native_model_path(path)
            self.assertTrue(Path(native).is_file())
            self.assertTrue(native.isascii())

    def test_preflight_missing_model_does_not_import_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            result = bss.preflight(Path(temp) / "missing.onnx")
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["decision"], "BLOCKED")
            self.assertNotIn("runtime", result["checks"])

    def test_evidence_uses_common_schema_and_has_no_invented_quality_metrics(self):
        evidence = HERE.parents[1] / "docs/evidence/issue10-bss-sherpa"
        score = json.loads((evidence / "score.json").read_text(encoding="utf-8"))
        fixtures = json.loads((evidence / "fixture-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(score["schema_version"], bss.SCHEMA)
        self.assertEqual(fixtures["schema_version"], bss.SCHEMA)
        self.assertTrue(all(value is None for value in score["metrics"].values()))
        self.assertEqual(score["checks"]["datahive_a3"]["status"], "NOT_RUN")
        self.assertEqual(score["checks"]["honor_android"]["status"], "NOT_RUN")
        self.assertEqual(score["quality_decision"]["status"], "NOT_RUN")
        self.assertEqual(score["upstream_lock"]["sha256"], bss.sha256(bss.LOCK_PATH))
        for record in fixtures["fixtures"] + fixtures["smoke_outputs"]:
            self.assertFalse(record["committed"])

    def test_output_writer_rejects_non_finite_samples(self):
        with tempfile.TemporaryDirectory() as temp:
            samples = np.zeros((2, 128), dtype=np.float32)
            samples[0, 0] = np.nan
            with self.assertRaisesRegex(ValueError, "non-finite"):
                bss.write_wav(Path(temp) / "bad.wav", samples, 44100)


if __name__ == "__main__":
    unittest.main()
