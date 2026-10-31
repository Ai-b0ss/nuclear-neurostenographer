"""Packaging corruption tests; these authored bytes are not valid JNI/APK builds."""
import hashlib
from pathlib import Path
import tempfile
import struct
import unittest
from unittest.mock import patch
import zipfile
import warnings
from check_apk import inspect, runtime_identity

ROOT = Path(__file__).resolve().parents[1]


class IdentityTests(unittest.TestCase):
    def test_elf_machine_must_match_each_packaged_abi(self):
        # Minimal authored ELF headers test static validation only, not loading.
        (ROOT / ".local").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as tmp:
            apk = Path(tmp) / "fixture.apk"
            natives = {}
            for abi, machine in [("arm64-v8a", 183), ("x86_64", 62)]:
                data = bytearray(120)
                data[:6] = b"\x7fELF\x02\x01"
                struct.pack_into("<H", data, 18, machine)
                struct.pack_into("<Q", data, 32, 64)
                struct.pack_into("<HH", data, 54, 56, 1)
                struct.pack_into("<I", data, 64, 1)
                struct.pack_into("<Q", data, 112, 16384)
                for library in ["libonnxruntime", "libsherpa-onnx-jni", "libandroidx.graphics.path"]:
                    natives[f"lib/{abi}/{library}.so"] = bytes(data)
            manifest = (b'E: service\n "ru.neurostenographer.app.DiarizationService"\n'
                        b' ":diarization"\n android:exported=(type 0x12)0x0\n')
            def check(corrupt=None):
                with zipfile.ZipFile(apk, "w") as archive:
                    for name, data in natives.items():
                        if name == corrupt:
                            mutated = bytearray(data)
                            struct.pack_into("<H", mutated, 18, 62 if "arm64-v8a" in name else 183)
                            data = bytes(mutated)
                        archive.writestr(name, data)
                    for name in ["sherpa-onnx", "onnxruntime"]:
                        archive.writestr(f"assets/licenses/{name}-LICENSE.txt", "Authored test notice")
                with patch("check_apk.subprocess.check_output", side_effect=[b"", manifest]):
                    return inspect(apk, Path("unused-aapt"))
            self.assertEqual(len(check()["native_load_alignment"]), 6)
            for name in natives:
                with self.subTest(library=name):
                    with self.assertRaisesRegex(ValueError, "ELF machine does not match ABI"):
                        check(name)

    def test_apk_guards_are_active_with_python_optimized(self):
        # Run this file with both python and python -O in CI. A malformed archive
        # must never be accepted when CPython strips bare assert statements.
        (ROOT / ".local").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as tmp:
            apk = Path(tmp) / "fixture.apk"
            native = {}
            for abi, machine in [("arm64-v8a", 183), ("x86_64", 62)]:
                header = bytearray(120)
                header[:6] = b"\x7fELF\x02\x01"
                struct.pack_into("<H", header, 18, machine)
                struct.pack_into("<Q", header, 32, 64)
                struct.pack_into("<HH", header, 54, 56, 1)
                struct.pack_into("<I", header, 64, 1)
                struct.pack_into("<Q", header, 112, 16384)
                for lib in ["libonnxruntime", "libsherpa-onnx-jni", "libandroidx.graphics.path"]:
                    native[f"lib/{abi}/{lib}.so"] = bytes(header)
            notices = {
                "assets/licenses/sherpa-onnx-LICENSE.txt": b"Authored test notice",
                "assets/licenses/onnxruntime-LICENSE.txt": b"Authored test notice",
            }
            default_manifest = (
                b'E: service\n "ru.neurostenographer.app.DiarizationService"\n'
                b' ":diarization"\n android:exported=(type 0x12)0x0\n'
            )
            def run(removed=(), altered=None, extra=None, permissions=b"",
                    manifest=default_manifest):
                contents = dict(native, **notices)
                for name in removed:
                    contents.pop(name)
                if altered is not None:
                    name, data = altered
                    contents[name] = data
                with zipfile.ZipFile(apk, "w") as archive:
                    for name, data in contents.items():
                        archive.writestr(name, data)
                    if extra:
                        # A deliberately duplicated ZIP entry is part of this negative.
                        with warnings.catch_warnings():
                            warnings.filterwarnings("ignore", message=r"Duplicate name:", category=UserWarning)
                            archive.writestr(*extra)
                with patch("check_apk.subprocess.check_output",
                           side_effect=[permissions, manifest]):
                    return inspect(apk, Path("unused-aapt"))
            self.assertEqual(len(run()["native_elf_machine"]), 6)
            with self.assertRaisesRegex(AssertionError, "INTERNET"):
                run(permissions=b"uses-permission: android.permission.INTERNET")
            with self.assertRaisesRegex(AssertionError, "exported"):
                run(manifest=default_manifest.replace(b"0x0", b"0x1"))
            with self.assertRaisesRegex(AssertionError, "native"):
                run(removed=["lib/x86_64/libonnxruntime.so"])
            with self.assertRaisesRegex(AssertionError, "ELF"):
                name = "lib/x86_64/libonnxruntime.so"
                run(altered=(name, b"Not an ELF" + native[name][10:]))
            with self.assertRaisesRegex(AssertionError, "alignment"):
                name = "lib/arm64-v8a/libonnxruntime.so"
                bad = bytearray(native[name])
                struct.pack_into("<Q", bad, 112, 4096)
                run(altered=(name, bytes(bad)))
            with self.assertRaisesRegex(AssertionError, "license"):
                run(removed=["assets/licenses/onnxruntime-LICENSE.txt"])
            with self.assertRaisesRegex(AssertionError, "Model/audio"):
                run(extra=("assets/secret.wav", b"Authored empty wav marker"))
            with self.assertRaisesRegex(AssertionError, "Duplicate ZIP"):
                run(extra=("lib/x86_64/libonnxruntime.so", native["lib/x86_64/libonnxruntime.so"]))

    def test_native_swap_and_false_build_digest_are_rejected(self):
        (ROOT / ".local").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as tmp:
            root = Path(tmp)
            aar, apk = root / "runtime.aar", root / "app.apk"
            names = [f"lib/{abi}/{lib}.so" for abi in ["arm64-v8a", "x86_64"]
                     for lib in ["libonnxruntime", "libsherpa-onnx-jni"]]
            with zipfile.ZipFile(aar, "w") as z:
                for name in names:
                    z.writestr(name.replace("lib/", "jni/", 1), name.encode())
            digest = hashlib.sha256(aar.read_bytes()).hexdigest()
            def fixture(corrupt=None, identity=digest):
                with zipfile.ZipFile(apk, "w") as z:
                    for name in names:
                        z.writestr(name, b"swapped runtime" if name == corrupt else name.encode())
                    z.writestr("classes.dex", identity.encode())
            fixture()
            self.assertEqual(runtime_identity(apk, aar)["aar_sha256"], digest)
            for name in names:
                fixture(corrupt=name)
                with self.assertRaises(AssertionError):
                    runtime_identity(apk, aar)
            fixture(identity="0" * 64)
            with self.assertRaises(AssertionError):
                runtime_identity(apk, aar)


if __name__ == "__main__":
    unittest.main()
