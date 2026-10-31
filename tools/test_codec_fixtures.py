"""Validate generated codec fixtures with FFmpeg. NOT Android execution evidence."""
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / ".local/androidTestAssets/codecs"


class CodecFixtureTests(unittest.TestCase):
    def test_generated_audio_is_bounded_tone(self):
        manifest = json.loads((FIXTURES / "manifest.json").read_text())
        self.assertEqual(manifest["kind"], "GENERATED_NUMERIC_TONES_NOT_SPEECH")
        self.assertEqual(len(manifest["files"]), 5)
        for name, record in (manifest["files"] | manifest["reject_files"] | manifest["format_probe_files"]).items():
            data = (FIXTURES / name).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), record["sha256"])
            self.assertEqual(len(data), record["bytes"])
        for name in manifest["files"]:
            raw = subprocess.check_output(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-i", str(FIXTURES / name), "-ar", "16000", "-ac", "1", "-f", "s16le", "pipe:1"], timeout=15)
            samples = [x[0] / 32768 for x in struct.iter_unpack("<h", raw)]
            self.assertTrue(1200 <= len(samples) / 16 <= 1450, name)
            rms = math.sqrt(sum(x * x for x in samples) / len(samples))
            self.assertTrue(0.04 <= rms <= 0.3, (name, rms))

    def test_generator_failure_discards_stale_outputs(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as temp:
            dest = Path(temp)
            for name in ["manifest.json", "tone.mp3", "two-tracks.m4a", "too-long.m4a"]:
                (dest / name).write_text("stale")
            result = subprocess.run([sys.executable, str(ROOT / "tools/provision_codec_fixtures.py"),
                "--output", str(dest), "--ffmpeg", str(dest / "missing-ffmpeg")], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(list(dest.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
