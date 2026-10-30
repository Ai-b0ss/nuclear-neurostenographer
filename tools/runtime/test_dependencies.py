import json
from pathlib import Path
import tempfile
import unittest
from collect_dependencies import inventory

ROOT = Path(__file__).resolve().parents[2]


class InventoryTests(unittest.TestCase):
    def test_actual_cache_and_bounded_text_are_required(self):
        (ROOT / ".local").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as tmp:
            root = Path(tmp)
            for build in ["build-android-arm64-v8a", "build-android-x86-64"]:
                directory = root / "source" / build
                dep = directory / "_deps/test-src"
                dep.mkdir(parents=True)
                (directory / "CMakeCache.txt").write_text("SHERPA_ONNX_ENABLE_TTS:BOOL=OFF\n")
                (dep / "LICENSE").write_text("Authored test notice, not a dependency license")
                (dep / "CMakeLists.txt").write_text("# numeric fixture")
            result = inventory(root / "source", root / "output")
            self.assertEqual(len(result["dependencies"]), 2)
            self.assertTrue(all(d["licenses"] for d in result["dependencies"]))
            for bad in ["SHERPA_ONNX_ENABLE_TTS:BOOL=ON", "missing"]:
                (root / "source/build-android-arm64-v8a/CMakeCache.txt").write_text(bad)
                with self.assertRaises(ValueError):
                    inventory(root / "source", root / "bad-output")
                self.assertFalse((root / "bad-output").exists())
            (root / "source/build-android-arm64-v8a/CMakeCache.txt").write_text("SHERPA_ONNX_ENABLE_TTS:BOOL=OFF")
            dep = root / "source/build-android-arm64-v8a/_deps/test-src"
            for data in [b"binary\x00notice", b"x" * (256 * 1024 + 1)]:
                (dep / "LICENSE").write_bytes(data)
                with self.assertRaises(ValueError):
                    inventory(root / "source", root / "bad-output")
            (dep / "LICENSE").write_text("notice")
            dep.rename(dep.with_name("espeak-src"))
            with self.assertRaises(ValueError):
                inventory(root / "source", root / "bad-output")


if __name__ == "__main__":
    unittest.main()
