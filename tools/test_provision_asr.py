"""No-network negative test of pinned-download integrity and cache replacement."""
import hashlib
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch
import provision_asr


def main():
    (provision_asr.ROOT / ".local").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=provision_asr.ROOT / ".local") as tmp:
        path = Path(tmp) / "model.onnx"
        path.write_bytes(b"previous")
        expected = hashlib.sha256(b"correct").hexdigest()

        def corrupt(_url, dest):
            Path(dest).write_bytes(b"corrupted download")

        with patch("urllib.request.urlretrieve", corrupt):
            try:
                provision_asr.download("https://example.invalid/model", path, expected)
                raise AssertionError("Corrupt download accepted")
            except ValueError:
                pass
        assert path.read_bytes() == b"previous"
        assert not path.with_suffix(".onnx.part").exists()

        def valid(_url, dest):
            Path(dest).write_bytes(b"correct")

        with patch("urllib.request.urlretrieve", valid):
            provision_asr.download("https://example.invalid/model", path, expected)
        assert path.read_bytes() == b"correct"
        with patch("urllib.request.urlretrieve", side_effect=AssertionError("Cache redownloaded")):
            provision_asr.download("https://example.invalid/model", path, expected)
    print("PASS pinned download: corruption rejected, previous file retained, replacement verified, cache verified")
    with tempfile.TemporaryDirectory(dir=provision_asr.ROOT / ".local") as tmp:
        candidate, destination = Path(tmp) / "candidate.aar", Path(tmp) / "selected.aar"
        candidate.write_bytes(b"unknown runtime")
        destination.write_bytes(b"previous runtime")
        try:
            provision_asr.select_runtime(candidate, destination)
            raise AssertionError("Unpinned native binary selected")
        except ValueError:
            pass
        assert destination.read_bytes() == b"previous runtime"
        assert not destination.with_suffix(".aar.part").exists()
    print("PASS runtime selection: unpinned candidate rejected, previous runtime retained")


class DefaultRuntimeTests(unittest.TestCase):
    def setUp(self):
        (provision_asr.ROOT / ".local").mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=provision_asr.ROOT / ".local")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.destination = self.root / "app/libs/runtime.aar"
        self.destination.parent.mkdir(parents=True)
        self.destination.write_bytes(b"previous upstream runtime")
        self.cache = self.root / "cache"
        self.correct = b"authored integrity test, not a runtime binary"
        self.pin = patch.object(provision_asr, "NO_TTS_CANDIDATE_SHA256", hashlib.sha256(self.correct).hexdigest())
        self.pin.start()
        self.addCleanup(self.pin.stop)

    def fake_download(self, command, **kwargs):
        self.assertEqual(command[:4], ["gh", "run", "download", str(provision_asr.NO_TTS_CANDIDATE_RUN)])
        self.assertEqual(command[command.index("--repo") + 1], "Ai-b0ss/nuclear-neurostenographer")
        self.assertEqual(kwargs, {"check": True, "timeout": 120, "capture_output": True})
        (Path(command[-1]) / provision_asr.LOCK["filename"]).write_bytes(self.correct)

    def test_exact_repository_artifact_selected_and_cached(self):
        with patch("subprocess.run", side_effect=self.fake_download) as runner:
            provision_asr.provision_runtime(self.destination, self.cache)
            self.assertEqual(runner.call_count, 1)
        self.assertEqual(self.destination.read_bytes(), self.correct)
        self.assertEqual((self.cache / provision_asr.LOCK["filename"]).read_bytes(), self.correct)
        self.assertEqual(len(list(self.cache.iterdir())), 1)

    def test_expired_or_unauthorized_artifact_preserves_previous_without_fallback(self):
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, ["gh"])), \
             patch("urllib.request.urlretrieve", side_effect=AssertionError("Unexpected upstream fallback")):
            with self.assertRaises(RuntimeError):
                provision_asr.provision_runtime(self.destination, self.cache)
        self.assertEqual(self.destination.read_bytes(), b"previous upstream runtime")
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_corrupt_artifact_never_replaces_previous(self):
        def corrupt(command, **kwargs):
            (Path(command[-1]) / provision_asr.LOCK["filename"]).write_bytes(b"untrusted binary")
        with patch("subprocess.run", side_effect=corrupt):
            with self.assertRaises(ValueError):
                provision_asr.provision_runtime(self.destination, self.cache)
        self.assertEqual(self.destination.read_bytes(), b"previous upstream runtime")
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_valid_installed_runtime_needs_no_cli(self):
        self.destination.write_bytes(self.correct)
        with patch("subprocess.run", side_effect=AssertionError("CLI used for valid installation")):
            provision_asr.provision_runtime(self.destination, self.cache)

    def test_valid_cached_runtime_needs_no_cli(self):
        self.cache.mkdir()
        (self.cache / provision_asr.LOCK["filename"]).write_bytes(self.correct)
        with patch("subprocess.run", side_effect=AssertionError("CLI used for valid cache")):
            provision_asr.provision_runtime(self.destination, self.cache)
        self.assertEqual(self.destination.read_bytes(), self.correct)


if __name__ == "__main__":
    main()
    unittest.main()
