"""No-network tests for research input integrity and adapter determinism."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import wave

import research


def write_wav(path, frames=(0, 1000, -1000, 2000), sample_width=2, channels=1):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(sample_width)
        output.setframerate(16000)
        if sample_width == 2:
            import struct
            payload = b"".join(struct.pack("<h", frame) for frame in frames)
        else:
            payload = bytes(frame & 255 for frame in frames)
        output.writeframes(payload)


class ResearchTests(unittest.TestCase):
    def setUp(self):
        research.LOCAL_ROOT.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=research.LOCAL_ROOT)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.mixture = self.root / "mixture.wav"
        self.enrollment = self.root / "enrollment.wav"
        write_wav(self.mixture)
        write_wav(self.enrollment, frames=(100, 200, 300, 400))

    def test_wav_validation_and_metadata(self):
        info = research.validate_wav(self.mixture, "mixture")
        self.assertEqual(info["channels"], 1)
        self.assertEqual(info["sample_rate_hz"], 16000)
        self.assertEqual(info["frames"], 4)
        self.assertEqual(info["sha256"], research.sha256(self.mixture))
        with self.assertRaisesRegex(research.ResearchError, "non-zero duration"):
            write_wav(self.root / "empty.wav", frames=())
            research.validate_wav(self.root / "empty.wav")
        invalid = self.root / "invalid.wav"
        invalid.write_bytes(b"not audio")
        with self.assertRaisesRegex(research.ResearchError, "readable PCM WAV"):
            research.validate_wav(invalid)
        with self.assertRaisesRegex(research.ResearchError, "PCM16"):
            write_wav(self.root / "pcm8.wav", sample_width=1)
            research.validate_wav(self.root / "pcm8.wav")

    def test_output_is_local_and_never_an_input(self):
        with self.assertRaisesRegex(research.ResearchError, "inside"):
            research.validate_output(self.root.parent.parent / "outside.wav", self.mixture, self.enrollment)
        with self.assertRaisesRegex(research.ResearchError, "overwrite"):
            research.validate_output(self.mixture, self.mixture, self.enrollment)
        with self.assertRaisesRegex(research.ResearchError, ".wav"):
            research.validate_output(self.root / "output.bin", self.mixture, self.enrollment)

    def test_command_is_deterministic_and_pinned(self):
        arguments = ("python", Path("upstream"), Path("checkpoint/best_model.pth"),
                     self.mixture, self.enrollment, self.root / "a3.wav")
        first = research.build_command(*arguments)
        second = research.build_command(*arguments)
        self.assertEqual(first, second)
        self.assertEqual(first[:2], ["python", str(Path("upstream") / "inference.py")])
        self.assertEqual(first[first.index("--checkpoint_dir") + 1], "checkpoint")
        self.assertEqual(first[-2:], ["--sample_rate", "16000"])

    def test_corrupt_download_preserves_previous_checkpoint(self):
        destination = self.root / "best_model.pth"
        destination.write_bytes(b"previous")
        expected = hashlib.sha256(b"correct").hexdigest()

        def corrupt(_url, temporary):
            Path(temporary).write_bytes(b"corrupt")

        with patch("urllib.request.urlretrieve", corrupt):
            with self.assertRaises(research.ResearchError):
                research.download("https://example.invalid", destination, expected)
        self.assertEqual(destination.read_bytes(), b"previous")
        self.assertFalse(destination.with_suffix(".pth.part").exists())

    def make_upstream(self):
        upstream = self.root / "upstream"
        for name in ("inference.py", "LICENSE", "model/__init__.py", "tools/__init__.py"):
            path = upstream / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("pinned test double\n", encoding="utf-8")
        return upstream

    def test_preflight_rejects_wrong_revision_and_checkpoint(self):
        upstream = self.make_upstream()
        checkpoint = self.root / "best_model.pth"
        checkpoint.write_bytes(b"authored checkpoint test double")
        versions = {"torch": "test", "torchaudio": "test", "asteroid": "test",
                    "einops": "test", "resemblyzer": "test", "numpy": "test"}
        with patch.object(research, "CHECKPOINT_SIZE", checkpoint.stat().st_size), \
             patch.object(research, "CHECKPOINT_SHA256", research.sha256(checkpoint)), \
             patch.object(research, "dependency_versions", return_value=versions), \
             patch.object(research, "upstream_revision", return_value=research.UPSTREAM_COMMIT):
            report = research.preflight(upstream, checkpoint, "python")
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(json.loads(json.dumps(report)), report)
        with patch.object(research, "upstream_revision", return_value="wrong"), \
             patch.object(research, "dependency_versions", return_value=versions):
            report = research.preflight(upstream, checkpoint, "python")
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["checks"]["upstream"]["status"], "FAIL")
        self.assertEqual(report["checks"]["checkpoint"]["status"], "FAIL")

    def test_fake_upstream_run_is_atomic_and_repeatable(self):
        output_one = self.root / "a3-one.wav"
        output_two = self.root / "a3-two.wav"

        def fake_runner(command, **kwargs):
            self.assertEqual(kwargs, {"check": True, "capture_output": True, "text": True, "timeout": 900})
            destination = Path(command[command.index("--output") + 1])
            destination.write_bytes(self.mixture.read_bytes())
            return subprocess.CompletedProcess(command, 0, stdout="upstream smoke\n", stderr="")

        with patch.object(research, "require_preflight", return_value={"status": "PASS"}):
            first = research.run_inference(self.mixture, self.enrollment, output_one,
                                           self.root / "upstream", self.root / "checkpoint.pth",
                                           "python", runner=fake_runner)
            second = research.run_inference(self.mixture, self.enrollment, output_two,
                                            self.root / "upstream", self.root / "checkpoint.pth",
                                            "python", runner=fake_runner)
        self.assertEqual(first["a3_output"]["sha256"], second["a3_output"]["sha256"])
        self.assertEqual(output_one.read_bytes(), output_two.read_bytes())
        self.assertFalse((self.root / "a3-one.partial.wav").exists())

    def test_failed_run_preserves_previous_output(self):
        output = self.root / "a3.wav"
        output.write_bytes(b"previous output")

        def fail(_command, **_kwargs):
            raise subprocess.CalledProcessError(1, "inference", stderr="model failed")

        with patch.object(research, "require_preflight", return_value={"status": "PASS"}):
            with self.assertRaisesRegex(research.ResearchError, "model failed"):
                research.run_inference(self.mixture, self.enrollment, output,
                                       self.root / "upstream", self.root / "checkpoint.pth",
                                       "python", runner=fail)
        self.assertEqual(output.read_bytes(), b"previous output")
        self.assertFalse((self.root / "a3.partial.wav").exists())


if __name__ == "__main__":
    unittest.main()
