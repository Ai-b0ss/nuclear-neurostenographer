from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import wave

import numpy as np

from adapter import (
    AdapterError,
    LOCK,
    ROOT,
    dvector_windows,
    main_mel_projection,
    mel_basis,
    prepare_enrollment,
    prepare_mixture,
    read_wav,
    resample_16k,
    stack_left,
    verify_models,
    write_wav_atomic,
)
from infer import enhance_files
from provision import provision_file


def write_pcm16(path: Path, samples: np.ndarray, sample_rate: int = 16000, channels: int = 1) -> None:
    values = np.asarray(samples)
    if values.ndim == 1:
        values = values[:, None]
    pcm = np.clip(np.rint(values * 32767.0), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(channels)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        stream.writeframes(pcm.tobytes())


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary_root = ROOT / ".local" / "voicefilter-lite" / "test-tmp"
        self.temporary_root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=self.temporary_root)
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)

    def test_lock_has_full_commit_and_actual_model_sizes(self):
        self.assertEqual(len(LOCK["upstream"]["commit"]), 40)
        self.assertEqual(LOCK["files"]["voicefilter_lite.int8.onnx"]["size_bytes"], 6827972)
        self.assertEqual(LOCK["files"]["embedder.int8.onnx"]["size_bytes"], 12199675)
        for spec in LOCK["files"].values():
            self.assertEqual(len(spec["sha256"]), 64)

    def test_read_stereo_and_resample(self):
        path = self.folder / "stereo.wav"
        left = np.full(8000, 0.25, dtype=np.float32)
        right = np.full(8000, -0.25, dtype=np.float32)
        write_pcm16(path, np.stack([left, right], axis=1), sample_rate=8000, channels=2)
        audio = read_wav(path)
        self.assertEqual(audio.source_frames, 8000)
        self.assertEqual(audio.source_channels, 2)
        self.assertAlmostEqual(float(np.mean(audio.samples)), 0.0, places=6)
        self.assertEqual(resample_16k(audio.samples, audio.sample_rate).shape, (16000,))

    def test_invalid_wav_and_duration_are_rejected(self):
        path = self.folder / "bad.wav"
        path.write_bytes(b"not a wav")
        with self.assertRaises(AdapterError):
            read_wav(path)
        valid = self.folder / "valid.wav"
        write_pcm16(valid, np.ones(16000, dtype=np.float32) * 0.1)
        with self.assertRaisesRegex(AdapterError, "exceeds limit"):
            read_wav(valid, max_duration_seconds=0.5)

    def test_enrollment_requires_three_seconds_and_uses_only_three(self):
        samples = np.linspace(-0.2, 0.2, 64000, dtype=np.float32)
        selected = prepare_enrollment(samples)
        self.assertEqual(selected.shape, (48000,))
        np.testing.assert_array_equal(selected, samples[:48000])
        with self.assertRaisesRegex(AdapterError, "at least 3"):
            prepare_enrollment(samples[:47999])
        with self.assertRaisesRegex(AdapterError, "silence"):
            prepare_enrollment(np.zeros(48000, dtype=np.float32))

    def test_mixture_minimum_and_shape(self):
        with self.assertRaises(AdapterError):
            prepare_mixture(np.zeros(159, dtype=np.float32))
        with self.assertRaises(AdapterError):
            prepare_mixture(np.zeros((160, 2), dtype=np.float32))
        self.assertEqual(prepare_mixture(np.zeros(160, dtype=np.float32)).shape, (160,))

    def test_dvector_windows_have_pinned_shape(self):
        config = {"n_fft": 512, "win_length": 400, "hop_length": 160, "n_mels": 40, "window": 80, "stride": 40}
        samples = np.sin(2 * np.pi * 220 * np.arange(48000) / 16000).astype(np.float32)
        windows = dvector_windows(samples, config)
        self.assertEqual(windows.shape, (6, 80, 40))
        self.assertEqual(windows.dtype, np.float32)
        self.assertTrue(np.isfinite(windows).all())

    def test_mel_basis_and_left_context(self):
        basis = mel_basis(16000, 1200, 128)
        self.assertEqual(basis.shape, (128, 601))
        self.assertTrue(np.isfinite(basis).all())
        self.assertTrue(np.all(basis >= 0))
        self.assertTrue(np.all(basis.sum(axis=1) > 0))
        forward, inverse = main_mel_projection(16000, 1200, 128)
        self.assertEqual(forward.shape, (601, 128))
        self.assertEqual(inverse.shape, (601, 128))
        self.assertEqual((forward.T @ np.ones(601, dtype=np.float32)).shape, (128,))
        context = []
        first = stack_left(np.ones(2, dtype=np.float32), context, 4, 2)
        np.testing.assert_array_equal(first.reshape(4, 2), [[0, 0], [0, 0], [0, 0], [1, 1]])
        second = stack_left(np.full(2, 2, dtype=np.float32), context, 4, 2)
        np.testing.assert_array_equal(second.reshape(4, 2), [[0, 0], [0, 0], [1, 1], [2, 2]])

    def test_atomic_wav_output_and_input_collision(self):
        output = self.folder / "enhanced.wav"
        result = write_wav_atomic(output, np.array([0.0, 0.5, -0.5], dtype=np.float32))
        audio = read_wav(output)
        self.assertEqual(audio.samples.shape, (3,))
        self.assertEqual(audio.sample_rate, 16000)
        self.assertEqual(len(result["output_sha256"]), 64)
        self.assertFalse(output.with_name(output.name + ".part").exists())
        with self.assertRaisesRegex(AdapterError, "must not overwrite"):
            enhance_files(self.folder / "enroll.wav", output, output)

    def test_model_verification_rejects_wrong_hash_and_size(self):
        content = b"small authored fixture"
        spec = {"fixture.onnx": {"size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}}
        (self.folder / "fixture.onnx").write_bytes(content)
        verified = verify_models(self.folder, spec)
        self.assertEqual(verified["fixture.onnx"]["size_bytes"], len(content))
        (self.folder / "fixture.onnx").write_bytes(b"corrupt")
        with self.assertRaisesRegex(AdapterError, "integrity mismatch"):
            verify_models(self.folder, spec)
        with self.assertRaisesRegex(AdapterError, "Missing pinned model"):
            verify_models(self.folder, {"missing.onnx": spec["fixture.onnx"]})

    def test_failed_provision_preserves_previous_file(self):
        source = self.folder / "source.onnx"
        destination = self.folder / "destination.onnx"
        source.write_bytes(b"corrupt")
        destination.write_bytes(b"previous")
        spec = {"size_bytes": 7, "sha256": hashlib.sha256(b"correct").hexdigest()}
        with self.assertRaisesRegex(ValueError, "integrity mismatch"):
            provision_file("https://example.invalid", source, destination, spec)
        self.assertEqual(destination.read_bytes(), b"previous")
        self.assertFalse(destination.with_name(destination.name + ".part").exists())

    def test_inference_report_schema_is_serializable_without_running_models(self):
        report = {
            "baseline_wer": "NOT_RUN",
            "candidate_wer": "NOT_RUN",
            "pss_status": "NOT_RUN",
        }
        self.assertEqual(json.loads(json.dumps(report))["candidate_wer"], "NOT_RUN")


if __name__ == "__main__":
    unittest.main()
