"""Authored adb output only: parsing, phone suitability and kit rejection. Not a device run."""
import json
import tempfile
import unittest
from pathlib import Path

import offline_kit
import phone_kit

DF = "Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/block/dm-48 118000000 60000000 {free} 51% /data\n"


class FakeAdb:
    def __init__(self, abi="arm64-v8a", sdk="34", free=8_000_000, ram=8_000_000, airplane="1"):
        self.answers = {("getprop", "ro.product.cpu.abi"): abi, ("getprop", "ro.build.version.sdk"): sdk,
                        ("getprop", "ro.product.model"): "TestPhone", ("getprop", "ro.build.version.release"): "14",
                        ("cat", "/proc/meminfo"): f"MemTotal:       {ram} kB\n",
                        ("df", "-k", "/data"): DF.format(free=free),
                        ("settings", "get", "global", "airplane_mode_on"): airplane,
                        ("settings", "get", "global", "wifi_on"): "0"}

    def shell(self, *args, **kwargs):
        return self.answers[args]


class ParseTests(unittest.TestCase):
    def test_devices_ignores_unauthorized_and_offline(self):
        text = "List of devices attached\nAAA\tdevice\nBBB\tunauthorized\nCCC\toffline\n"
        self.assertEqual(phone_kit.parse_devices(text), ["AAA"])
        self.assertEqual(phone_kit.parse_devices("List of devices attached\n\n"), [])

    def test_free_space_and_garbage(self):
        self.assertEqual(phone_kit.parse_free_kib(DF.format(free=123456)), 123456)
        with self.assertRaises(ValueError):
            phone_kit.parse_free_kib("df: error")

    def test_meminfo_and_battery(self):
        self.assertEqual(phone_kit.parse_meminfo_total_pss("   TOTAL PSS:   612345            TOTAL RSS: 1"), 612345)
        self.assertIsNone(phone_kit.parse_meminfo_total_pss("No process found for: x"))
        self.assertEqual(phone_kit.parse_battery("  level: 81\n  temperature: 372\n"), (37.2, 81))


class PreflightTests(unittest.TestCase):
    def test_good_phone_has_no_problems(self):
        problems, report = phone_kit.preflight(FakeAdb())
        self.assertEqual(problems, [])
        self.assertTrue(report["airplane_mode"])

    def test_x86_emulator_is_not_an_arm64_acceptance(self):
        problems, _ = phone_kit.preflight(FakeAdb(abi="x86_64"))
        self.assertTrue(any("arm64-v8a" in p for p in problems))

    def test_low_space_old_android_and_low_ram_are_reported(self):
        problems, _ = phone_kit.preflight(FakeAdb(free=400_000, sdk="25", ram=2_000_000))
        self.assertEqual(len(problems), 3)


class KitTests(unittest.TestCase):
    def make(self, directory, sizes=None):
        sizes = sizes or {"app-debug.apk": 10, "gigaam-v3.zip": 210 * 1024 * 1024, "diarization.zip": 45 * 1024 * 1024}
        kit = Path(directory)
        for name, size in sizes.items():
            with open(kit / name, "wb") as f:
                f.truncate(size)
        manifest = {"runtime_sha256": offline_kit.RUNTIME_SHA256, "asr_files": offline_kit.ASR_FILES}
        (kit / "KIT_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
        (kit / "SHA256SUMS.txt").write_text("".join(f"{offline_kit.sha256(kit / n)}  {n}\n" for n in sizes),
                                            encoding="utf-8")
        return kit

    def test_consistent_kit_passes_both_checkers(self):
        with tempfile.TemporaryDirectory() as tmp:
            kit = self.make(tmp)
            self.assertEqual(offline_kit.verify_kit(kit), [])
            self.assertEqual(phone_kit.verify_kit_files(kit), [])

    def test_tampered_zip_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            kit = self.make(tmp)
            with open(kit / "gigaam-v3.zip", "r+b") as f:
                f.write(b"x")
            self.assertTrue(any("checksum mismatch" in p for p in offline_kit.verify_kit(kit)))
            self.assertTrue(any("checksum mismatch" in p for p in phone_kit.verify_kit_files(kit)))

    def test_missing_file_and_truncated_model_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            kit = self.make(tmp)
            (kit / "diarization.zip").unlink()
            self.assertTrue(any("missing" in p for p in offline_kit.verify_kit(kit)))
        with tempfile.TemporaryDirectory() as tmp:
            kit = self.make(tmp, {"app-debug.apk": 10, "gigaam-v3.zip": 1000, "diarization.zip": 45 * 1024 * 1024})
            self.assertTrue(any("smaller than expected" in p for p in offline_kit.verify_kit(kit)))

    def test_manifest_with_another_runtime_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            kit = self.make(tmp)
            manifest = json.loads((kit / "KIT_MANIFEST.json").read_text())
            manifest["runtime_sha256"] = "e3905b1258b577d8d374db798618602ceaaff5805cbf9b356ab25267cd98144d"  # upstream GPL/TTS AAR
            (kit / "KIT_MANIFEST.json").write_text(json.dumps(manifest))
            self.assertTrue(any("pinned no-TTS runtime" in p for p in offline_kit.verify_kit(kit)))

    def test_pinned_values_match_the_application_sources(self):
        root = Path(__file__).resolve().parents[1]
        store = (root / "app/src/main/java/ru/neurostenographer/app/AsrModelStore.kt").read_text(encoding="utf-8")
        for digest in offline_kit.ASR_FILES.values():
            self.assertIn(digest, store)
        self.assertIn(offline_kit.RUNTIME_SHA256, (root / "tools/runtime/runtime.properties").read_text())


if __name__ == "__main__":
    unittest.main()
