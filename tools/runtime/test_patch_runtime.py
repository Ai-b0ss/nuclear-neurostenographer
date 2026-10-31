"""Fail-closed source patch tests; real C++ regression runs on GitHub Linux."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from patch_runtime import PINS, apply, replace_once

ROOT = Path(__file__).resolve().parents[2]


class PatchTests(unittest.TestCase):
    def test_ambiguous_context_is_rejected(self):
        for text in ("missing", "oldold"):
            with self.assertRaises(ValueError):
                replace_once(text, "old", "new")

    def test_wrong_source_never_partially_mutates(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as tmp:
            source = Path(tmp)
            csrc = source / "sherpa-onnx/csrc"
            csrc.mkdir(parents=True)
            for name in PINS:
                (csrc / name).write_text("unrecognized source")
            before = {p.name: p.read_bytes() for p in csrc.iterdir()}
            with self.assertRaises(ValueError):
                apply(source)
            self.assertEqual(before, {p.name: p.read_bytes() for p in csrc.iterdir()})

    def test_exact_upstream_when_available(self):
        # Local inspection cache only; CI supplies its pinned checkout separately.
        cache = ROOT / ".local/upstream-inspect"
        if not all((cache / name).exists() for name in PINS):
            self.skipTest("Pinned inspection cache absent")
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as tmp:
            source = Path(tmp)
            csrc = source / "sherpa-onnx/csrc"
            csrc.mkdir(parents=True)
            for name, digest in PINS.items():
                data = (cache / name).read_bytes()
                self.assertEqual(digest, hashlib.sha256(data).hexdigest())
                (csrc / name).write_bytes(data)
            report = apply(source)
            self.assertEqual("topk-bounds-and-unknown-v1", report["patch"])
            with self.assertRaises(ValueError):
                apply(source)  # Double apply is an error, never an unnoticed drift.


if __name__ == "__main__":
    unittest.main()
