"""Corrupt copies of retained public evidence; no model or device calls."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from verify_android_evidence import verify

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/evidence"
PREFIX = "round11-provider-export"


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".local").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".local")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        for format in ["txt", "json", "srt"]:
            shutil.copyfile(SOURCE / (PREFIX + "." + format), self.directory / (PREFIX + "." + format))
        self.report = json.loads((SOURCE / "round11-ui-flow.json").read_bytes())
        self.apk = json.loads((SOURCE / "round11-apk-inspection.json").read_bytes())

    def test_actual_archive_and_corrupted_export_bytes(self):
        self.assertEqual(verify(self.report, self.apk, self.directory, PREFIX)["exports_verified"], 3)
        for format in ["txt", "json", "srt"]:
            path = self.directory / (PREFIX + "." + format)
            raw = path.read_bytes()
            path.write_bytes(raw + b"corruption")
            with self.assertRaises(ValueError):
                verify(self.report, self.apk, self.directory, PREFIX)
            path.write_bytes(raw)

    def test_wrong_runtime_and_failed_packaging_report(self):
        for key, value in [("aar_sha256", "0" * 64), ("native_bytes", "MISMATCH"), ("build_config_digest", "MISSING")]:
            apk = copy.deepcopy(self.apk)
            apk["runtime_identity"][key] = value
            with self.assertRaises(ValueError):
                verify(self.report, apk, self.directory, PREFIX)

    def test_updated_hash_cannot_hide_broken_cross_format_timeline(self):
        path = self.directory / (PREFIX + ".srt")
        raw = path.read_bytes().replace(b"00:00:00,031", b"00:00:00,032")
        self.assertNotEqual(raw, path.read_bytes())
        path.write_bytes(raw)
        self.report["saved_public_exports"]["srt"] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        with self.assertRaises(AssertionError):
            verify(self.report, self.apk, self.directory, PREFIX)


if __name__ == "__main__":
    unittest.main()
