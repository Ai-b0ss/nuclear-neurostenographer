"""Gate logic tests on synthetic evidence; no phone, emulator or audio."""
import json
from pathlib import Path
import tempfile
import unittest

from check_phone_gate import evaluate


def suite(folder, tests, failures):
    Path(folder).mkdir(parents=True, exist_ok=True)
    (Path(folder) / "TEST-x.xml").write_text(f'<testsuite name="s" tests="{tests}" failures="{failures}" errors="0"/>', encoding="utf-8")


def scored(drift=0.0, same_count=True, c0_drift=0.0, rtf_wall=300_000, c2_pss=500, failed=0, repeats=True):
    agree = lambda d, same: {"der_phone_vs_host": d, "same_speaker_count": same}
    return {"failed_runs": failed, "summary": {},
            "rows": [{"case": "syn3-clean", "system": "C2", "host_agreement": agree(drift, same_count)},
                     {"case": "syn3-clean", "system": "C0", "host_agreement": agree(c0_drift, True)}],
            "repeat_runs_identical": {"syn3-clean/C2": repeats},
            "long": {"C0": {"status": "OK", "wall_ms": 1_000_000, "audio_ms": 1_200_000, "peak_mib": 600},
                     "C2": {"status": "OK", "wall_ms": rtf_wall, "audio_ms": 1_200_000, "peak_mib": c2_pss}}}


class Gate(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.write("device.json", {"abi": "arm64-v8a", "contest_app_installed": True})
        self.write("prototype-package.json", {"installed_as": "ru.neurostenographer.app.c2"})
        self.write("exit-codes.json", {"prototype_gradle_exit": 0, "contest_app_untouched": True, "prototype_left_installed": False})
        suite(self.root / "prototype-junit", 3, 0)

    def write(self, name, data):
        (self.root / name).write_text(json.dumps(data), encoding="utf-8")

    def tearDown(self):
        self.folder.cleanup()

    def test_all_criteria_met_is_go(self):
        self.assertEqual(evaluate(self.root, scored())["verdict"], "GO")

    def test_missing_evidence_is_not_run_never_go(self):
        self.assertEqual(evaluate(self.root, None)["verdict"], "NOT_RUN")
        empty = self.root / "empty"
        empty.mkdir()
        self.assertEqual(evaluate(empty, None)["verdict"], "NOT_RUN")

    def test_each_failure_is_no_go(self):
        for bad in (scored(drift=0.05), scored(same_count=False), scored(c0_drift=0.2), scored(rtf_wall=700_000), scored(c2_pss=800),
                    scored(failed=1), scored(repeats=False)):
            self.assertEqual(evaluate(self.root, bad)["verdict"], "NO-GO")

    def test_touched_contest_app_or_wrong_package_is_no_go(self):
        self.write("exit-codes.json", {"prototype_gradle_exit": 0, "contest_app_untouched": False, "prototype_left_installed": False})
        self.assertEqual(evaluate(self.root, scored())["verdict"], "NO-GO")
        self.write("exit-codes.json", {"prototype_gradle_exit": 0, "contest_app_untouched": True, "prototype_left_installed": False})
        self.write("prototype-package.json", {"installed_as": "ru.neurostenographer.app"})
        self.assertEqual(evaluate(self.root, scored())["verdict"], "NO-GO")

    def test_failed_instrumentation_or_emulator_is_no_go(self):
        suite(self.root / "prototype-junit", 3, 1)
        self.assertEqual(evaluate(self.root, scored())["verdict"], "NO-GO")
        suite(self.root / "prototype-junit", 3, 0)
        self.write("device.json", {"abi": "x86_64", "contest_app_installed": True})
        self.assertEqual(evaluate(self.root, scored())["verdict"], "NO-GO")


if __name__ == "__main__":
    unittest.main()
