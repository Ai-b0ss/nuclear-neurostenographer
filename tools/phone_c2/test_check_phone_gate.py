"""Gate logic tests on synthetic evidence; no phone, emulator or audio."""
import json
from pathlib import Path
import tempfile
import unittest

from check_phone_gate import evaluate


def suite(folder, tests, failures):
    Path(folder).mkdir(parents=True, exist_ok=True)
    (Path(folder) / "TEST-x.xml").write_text(f'<testsuite name="s" tests="{tests}" failures="{failures}" errors="0"/>', encoding="utf-8")


def row(case, backend, der=None, wall=0, audio=1, pss=0, status="OK"):
    out = {"case": case, "backend": backend, "attempt": 0, "status": status, "wall_ms": wall, "audio_ms": audio, "peak_total_pss_kib": pss}
    if der is not None:
        out["der"] = der
    return out


REFERENCE = {"summary": {"c2": {"pooled_der_collar250": 0.12}}, "rows": [row("a", "c2", der=0.10)]}


def scored(der=0.12, file_der=0.10, rtf_wall=300_000, c2_pss=500 * 1024, failed=0, repeats=True):
    return {"summary": {"c0": {"failed": 0}, "c2": {"failed": failed, "pooled_der_collar250": der}},
            "rows": [row("a", "c2", der=file_der), row("long-ru_000010", "c0", wall=1_000_000, audio=1_200_000, pss=600 * 1024),
                     row("long-ru_000010", "c2", wall=rtf_wall, audio=1_200_000, pss=c2_pss)],
            "repeat_runs_identical": {"a/c2": repeats}}


class Gate(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        (self.root / "device.json").write_text(json.dumps({"abi": "arm64-v8a"}), encoding="utf-8")
        suite(self.root / "prototype-junit", 3, 0)
        suite(self.root / "ordinary-junit", 7, 0)

    def tearDown(self):
        self.folder.cleanup()

    def test_all_criteria_met_is_go(self):
        self.assertEqual(evaluate(self.root, scored(), REFERENCE)["verdict"], "GO")

    def test_missing_evidence_is_not_run_never_go(self):
        self.assertEqual(evaluate(self.root, None, REFERENCE)["verdict"], "NOT_RUN")
        empty = Path(self.folder.name) / "empty"
        empty.mkdir()
        self.assertEqual(evaluate(empty, None, REFERENCE)["verdict"], "NOT_RUN")

    def test_each_failure_is_no_go(self):
        for bad in (scored(der=0.14), scored(file_der=0.2), scored(rtf_wall=700_000), scored(c2_pss=800 * 1024), scored(failed=1), scored(repeats=False)):
            self.assertEqual(evaluate(self.root, bad, REFERENCE)["verdict"], "NO-GO")

    def test_failed_instrumentation_is_no_go(self):
        suite(self.root / "prototype-junit", 3, 1)
        self.assertEqual(evaluate(self.root, scored(), REFERENCE)["verdict"], "NO-GO")

    def test_emulator_abi_is_no_go(self):
        (self.root / "device.json").write_text(json.dumps({"abi": "x86_64"}), encoding="utf-8")
        self.assertEqual(evaluate(self.root, scored(), REFERENCE)["verdict"], "NO-GO")


if __name__ == "__main__":
    unittest.main()
