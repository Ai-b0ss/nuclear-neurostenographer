"""Packaging corruption tests; these authored bytes are not valid JNI/APK builds."""
import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile
from check_apk import runtime_identity

ROOT = Path(__file__).resolve().parents[1]


class IdentityTests(unittest.TestCase):
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
