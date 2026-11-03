"""Authored adb output only: parsing, phone suitability and kit rejection. Not a device run."""
import argparse
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import offline_kit
import phone_kit

DF = "Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/block/dm-48 118000000 60000000 {free} 51% /data\n"


class FakeAdb:
    def __init__(self, abi="arm64-v8a", sdk="34", free=8_000_000, ram=8_000_000, airplane="1", qemu="", hardware="kirin"):
        self.answers = {("getprop", "ro.product.cpu.abi"): abi, ("getprop", "ro.build.version.sdk"): sdk,
                        ("getprop", "ro.product.model"): "TestPhone", ("getprop", "ro.build.version.release"): "14",
                        ("cat", "/proc/meminfo"): f"MemTotal:       {ram} kB\n",
                        ("df", "-k", "/data"): DF.format(free=free),
                        ("settings", "get", "global", "airplane_mode_on"): airplane,
                        ("settings", "get", "global", "wifi_on"): "0",
                        ("getprop", "ro.kernel.qemu"): qemu, ("getprop", "ro.hardware"): hardware}

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


EXE = "adb.exe" if os.name == "nt" else "adb"


def finder(files=(), on_path=None, environ=None, globs=None, module_dir=None):
    existing = set(files)
    return phone_kit.find_adb(None, environ or {}, which=lambda name: on_path if name == "adb" else None,
                              is_file=lambda path: path in existing,
                              glob_files=lambda pattern: (globs or {}).get(pattern, []), module_dir=module_dir or "")


class DeviceStateTests(unittest.TestCase):
    HEADER = "List of devices attached" + chr(10)

    def test_states_and_reasons_are_concrete(self):
        text = self.HEADER + "AAA" + chr(9) + "unauthorized" + chr(10) + "BBB" + chr(9) + "offline" + chr(10)
        self.assertEqual(phone_kit.parse_device_states(text), {"AAA": "unauthorized", "BBB": "offline"})
        self.assertIn("data USB cable", phone_kit.explain_no_device({}))
        self.assertIn("Allow", phone_kit.explain_no_device({"AAA": "unauthorized"}))
        self.assertIn("offline", phone_kit.explain_no_device({"AAA": "offline"}))
        self.assertIn("--serial", phone_kit.explain_no_device({"A": "device", "B": "device"}))

    def test_wait_times_out_as_not_run_and_finds_a_late_phone(self):
        empty = mock.Mock(stdout=self.HEADER + chr(10))
        ready = mock.Mock(stdout=self.HEADER + "AAA" + chr(9) + "device" + chr(10))
        args = argparse.Namespace(adb=None, serial=None, minutes=0)
        with mock.patch.object(phone_kit, "find_adb", return_value=("adb", "PATH")), \
                mock.patch.object(phone_kit.subprocess, "run", return_value=empty), \
                mock.patch.object(phone_kit.time, "sleep"):
            self.assertEqual(phone_kit.command_wait(args), phone_kit.NOT_RUN)
        args.minutes = 5
        with mock.patch.object(phone_kit, "find_adb", return_value=("adb", "PATH")), \
                mock.patch.object(phone_kit.subprocess, "run", side_effect=[empty, empty, ready]), \
                mock.patch.object(phone_kit.time, "sleep"), \
                mock.patch.object(phone_kit, "command_check", return_value=0) as check:
            self.assertEqual(phone_kit.command_wait(args), 0)
            check.assert_called_once()


class EmulatorIsNeverAPhoneTests(unittest.TestCase):
    """Regression: an `emulator-5564 offline` entry was reported as a phone to reconnect."""
    H = "List of devices attached" + chr(10)

    def listing(self, *rows):
        return self.H + "".join(serial + chr(9) + state + chr(10) for serial, state in rows)

    def connect(self, text, serial=None):
        args = argparse.Namespace(adb=None, serial=serial)
        with mock.patch.object(phone_kit, "find_adb", return_value=("adb", "PATH")), \
                mock.patch.object(phone_kit.subprocess, "run", return_value=mock.Mock(stdout=text)):
            return phone_kit.connect(args)

    def test_offline_emulator_is_not_described_as_a_phone(self):
        reason = phone_kit.explain_no_device({"emulator-5564": "offline"})
        self.assertIn("no physical phone", reason)
        self.assertIn("emulator-5564 (offline)", reason)
        self.assertNotIn("listed as offline", reason)

    def test_connect_with_only_an_offline_or_ready_emulator_is_not_run(self):
        for state in ("offline", "device"):
            with self.assertRaises(SystemExit) as raised:
                self.connect(self.listing(("emulator-5564", state)))
            self.assertEqual(raised.exception.code, phone_kit.NOT_RUN)

    def test_a_real_phone_next_to_an_emulator_is_chosen(self):
        adb = self.connect(self.listing(("emulator-5564", "device"), ("ABC123", "device")))
        self.assertEqual(adb.prefix[-2:], ["-s", "ABC123"])

    def test_serial_of_an_emulator_is_refused(self):
        with self.assertRaises(SystemExit) as raised:
            self.connect(self.listing(("emulator-5554", "device")), serial="emulator-5554")
        self.assertEqual(raised.exception.code, phone_kit.NOT_RUN)

    def test_unauthorized_phone_is_still_reported_as_unauthorized_beside_an_emulator(self):
        reason = phone_kit.explain_no_device({"emulator-5564": "offline", "ABC123": "unauthorized"})
        self.assertIn("authorize", reason)
        self.assertIn("Ignored emulator", reason)

    def test_wait_ignores_a_ready_emulator(self):
        ready = mock.Mock(stdout=self.listing(("emulator-5554", "device")))
        args = argparse.Namespace(adb=None, serial=None, minutes=0)
        with mock.patch.object(phone_kit, "find_adb", return_value=("adb", "PATH")), \
                mock.patch.object(phone_kit.subprocess, "run", return_value=ready), \
                mock.patch.object(phone_kit.time, "sleep"), \
                mock.patch.object(phone_kit, "command_check") as check:
            self.assertEqual(phone_kit.command_wait(args), phone_kit.NOT_RUN)
            check.assert_not_called()

    def test_emulator_properties_fail_the_preflight_even_with_a_phone_like_serial(self):
        problems, report = phone_kit.preflight(FakeAdb(qemu="1", hardware="ranchu", abi="x86_64"))
        self.assertTrue(report["emulator"])
        self.assertTrue(any("emulator" in p for p in problems))
        problems, report = phone_kit.preflight(FakeAdb(hardware="goldfish"))
        self.assertTrue(report["emulator"])

    def test_install_never_reaches_an_emulator(self):
        with tempfile.TemporaryDirectory() as tmp:
            adb = RecordingAdb(qemu="1", hardware="ranchu")
            self.assertEqual(InstallTests().install(adb, KitTests().make(tmp)), 1)
            self.assertFalse(any(c[0] == "install" for c in adb.calls))


class FindAdbTests(unittest.TestCase):
    def test_explicit_path_wins_and_a_wrong_one_is_reported(self):
        path, source = phone_kit.find_adb("C:/tools/adb.exe", {}, which=lambda n: None, is_file=lambda p: p == "C:/tools/adb.exe")
        self.assertEqual((path, source), ("C:/tools/adb.exe", "--adb"))
        path, source = phone_kit.find_adb("C:/nope/adb.exe", {}, which=lambda n: None, is_file=lambda p: False)
        self.assertIsNone(path)
        self.assertIn("does not exist", source)

    def test_environment_variable_then_path_then_sdk_folder(self):
        self.assertEqual(finder(files=["/x/adb"], environ={"ADB_PATH": "/x/adb"}, on_path="/usr/bin/adb"), ("/x/adb", "ADB_PATH"))
        self.assertEqual(finder(on_path="/usr/bin/adb"), ("/usr/bin/adb", "PATH"))
        sdk = os.path.join("/sdk", "platform-tools", EXE)
        self.assertEqual(finder(files=[sdk], environ={"ANDROID_HOME": "/sdk"}), (sdk, "ANDROID_HOME"))

    def test_adbutils_package_binary_is_used(self):
        binary = os.path.join("/site/adbutils", "binaries", EXE)
        self.assertEqual(finder(files=[binary], module_dir="/site/adbutils"), (binary, "adbutils package"))

    def test_bundled_copy_in_a_per_user_python_environment_is_found_without_vendor_names(self):
        local = "C:/Users/u/AppData/Local"
        pattern = os.path.join(local, "Packages", "*", "LocalCache", "Roaming", "*", "*", "*", ".venv", "Lib",
                               "site-packages", "adbutils", "binaries", EXE)
        found = "C:/Users/u/AppData/Local/Packages/Any_1/LocalCache/Roaming/Vendor/Ext/ext.a/.venv/Lib/site-packages/adbutils/binaries/" + EXE
        self.assertEqual(finder(environ={"LOCALAPPDATA": local}, globs={pattern: [found]}), (found, "bundled adbutils copy"))

    def test_nothing_found_is_reported_not_guessed(self):
        path, reason = finder(environ={"LOCALAPPDATA": "C:/none"})
        self.assertIsNone(path)
        self.assertEqual(reason, "adb not found")

    def test_missing_adb_and_missing_device_end_as_not_run(self):
        args = argparse.Namespace(adb=None, serial=None)
        with mock.patch.object(phone_kit, "find_adb", return_value=(None, "adb not found")):
            with self.assertRaises(SystemExit) as raised:
                phone_kit.connect(args)
        self.assertEqual(raised.exception.code, phone_kit.NOT_RUN)
        completed = mock.Mock(stdout="List of devices attached\n\n")
        with mock.patch.object(phone_kit, "find_adb", return_value=("adb", "PATH")), \
                mock.patch.object(phone_kit.subprocess, "run", return_value=completed):
            with self.assertRaises(SystemExit) as raised:
                phone_kit.connect(args)
        self.assertEqual(raised.exception.code, phone_kit.NOT_RUN)


class RecordingAdb(FakeAdb):
    def __init__(self, push_fails=False, leftover=False, **kwargs):
        super().__init__(**kwargs)
        self.calls, self.push_fails, self.leftover = [], push_fails, leftover

    def run(self, *args, **kwargs):
        self.calls.append(args)
        if args[0] == "push" and self.push_fails and "/Android/data/" in args[-1]:
            raise RuntimeError("adb push failed: Permission denied")
        return ""

    def shell(self, *args, **kwargs):
        self.calls.append(("shell",) + args)
        if args[0] == "ls":
            return "gigaam-v3.zip\n" if self.leftover else ""
        return self.answers.get(args, "")


class InstallTests(unittest.TestCase):
    def kit(self, tmp):
        return KitTests().make(tmp)

    def install(self, adb, kit, wait=0):
        args = argparse.Namespace(kit=str(kit), wait_minutes=wait, force=False)
        with mock.patch.object(phone_kit, "connect", return_value=adb), mock.patch.object(phone_kit.time, "sleep"):
            return phone_kit.command_install(args)

    def test_install_pushes_both_zips_to_the_app_folder_and_reports_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            adb = RecordingAdb()
            self.assertEqual(self.install(adb, self.kit(tmp), wait=1), 0)
            pushed = [c for c in adb.calls if c[0] == "push"]
            self.assertEqual(len(pushed), 2)
            self.assertTrue(all(c[-1].startswith(phone_kit.KIT_DIR_ON_PHONE) for c in pushed))
            self.assertTrue(any(c[0] == "install" for c in adb.calls))

    def test_tampered_kit_never_touches_the_phone(self):
        with tempfile.TemporaryDirectory() as tmp:
            kit = self.kit(tmp)
            with open(kit / "diarization.zip", "r+b") as f:
                f.write(b"x")
            adb = RecordingAdb()
            self.assertEqual(self.install(adb, kit), 1)
            self.assertEqual(adb.calls, [])

    def test_wrong_phone_is_refused_before_installing(self):
        with tempfile.TemporaryDirectory() as tmp:
            adb = RecordingAdb(abi="x86_64")
            self.assertEqual(self.install(adb, self.kit(tmp)), 1)
            self.assertFalse(any(c[0] == "install" for c in adb.calls))

    def test_forbidden_app_folder_falls_back_to_download_with_instructions(self):
        with tempfile.TemporaryDirectory() as tmp:
            adb = RecordingAdb(push_fails=True)
            self.assertEqual(self.install(adb, self.kit(tmp)), 1)
            self.assertEqual([c[-1] for c in adb.calls if c[0] == "push" and "/Download/" in c[-1]],
                             ["/sdcard/Download/gigaam-v3.zip", "/sdcard/Download/diarization.zip"])

    def test_zips_left_in_the_folder_mean_the_install_did_not_finish(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.install(RecordingAdb(leftover=True), self.kit(tmp), wait=0), 1)


if __name__ == "__main__":
    unittest.main()
