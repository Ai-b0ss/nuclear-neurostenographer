"""Synthetic arithmetic tests only; these files are NOT model performance evidence."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from compare_model_trials import compare


def score(name, audio, metric_errors=0, der_status="SCORED"):
    return {"schema_version": 1, "reference": {"recording_id": name, "kind": "ACTED",
             "audio_sha256": audio}, "reference_sha256": "f" * 64,
            "hypothesis_sha256": "e" * 64,
            "wer": {"status": "SCORED", "errors": metric_errors, "reference_words": 10, "rate": metric_errors / 10},
            "cpwer": {"status": "SCORED", "errors": metric_errors, "reference_words": 10, "rate": metric_errors / 10},
            "der": {"status": der_status, "rate": 0.1, "reference_speaker_ms": 1000,
                    "miss_ms": 100, "false_alarm_ms": 0, "confusion_ms": 0,
                    "collar_radius_ms": 0, "skip_reference_overlap": False}}


def trial(name, cases):
    return {"name": name, "code_commit": "a" * 40, "runtime_sha256": "b" * 64,
            "environment": {"platform": "android-emulator", "abi": "x86_64", "device": "pixel5-API33"},
            "timing_scope": "asr+diarization", "cases": cases}


class Comparisons(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.p = Path(self.temp.name)

    def fixture(self, missing=False):
        for c, errors in (("base-a", 0), ("base-b", 2), ("candidate-a", 1), ("candidate-b", 1)):
            name = c.split("-")[-1]
            value = score(name, ("c" if name == "a" else "d") * 64,
                          errors, "NOT_SCORED" if missing and name == "a" else "SCORED")
            (self.p / f"{c}.json").write_text(json.dumps(value))
        def cs(prefix):
            return [{"score_file": f"{prefix}-{name}.json", "audio_duration_ms": 1000 if name == "a" else 3000,
                     "elapsed_ms": 500 if prefix == "base" else 400} for name in ("a", "b")]
        return {"schema_version": 1, "trials": [trial("base", cs("base")), trial("candidate", cs("candidate"))]}

    def test_comparison_uses_weighted_counts_and_same_reference(self):
        data = compare(self.fixture(), self.p)
        self.assertTrue(data["timing_comparable"])
        self.assertEqual([x["metrics"]["wer"]["rate"] for x in data["trials"]], [0.1, 0.1])
        self.assertEqual([x["measured_rtf"] for x in data["trials"]], [0.25, 0.2])
        self.assertEqual(data["accuracy_protocol"]["der_collar_and_overlap"], (0, False))

    def test_reject_different_reference_and_der_protocol(self):
        data = self.fixture()
        h = json.loads((self.p / "candidate-a.json").read_text())
        h["reference_sha256"] = "1" * 64
        (self.p / "candidate-a.json").write_text(json.dumps(h))
        with self.assertRaisesRegex(ValueError, "corpus/reference mismatch"):
            compare(data, self.p)
        h["reference_sha256"] = "f" * 64
        h["der"]["skip_reference_overlap"] = True
        (self.p / "candidate-a.json").write_text(json.dumps(h))
        with self.assertRaisesRegex(ValueError, "DER scores use different"):
            compare(data, self.p)

    def test_missing_der_never_becomes_zero(self):
        result = compare(self.fixture(missing=True), self.p)
        for t in result["trials"]:
            self.assertEqual(t["metrics"]["der"]["status"], "NOT_SCORED")
            self.assertIsNone(t["metrics"]["der"]["rate"])
        self.assertEqual(result["trials"][0]["metrics"]["wer"]["status"], "SCORED")

    def test_different_hardware_not_rankable_for_speed(self):
        data = self.fixture()
        data["trials"][1]["environment"]["abi"] = "arm64-v8a"
        result = compare(data, self.p)
        self.assertFalse(result["timing_comparable"])
        self.assertTrue(all(t["metrics"]["wer"]["status"] == "SCORED" for t in result["trials"]))

    def test_invalid_score_and_path_escape(self):
        data = self.fixture()
        p = self.p / "candidate-a.json"
        v = json.loads(p.read_text())
        v["reference"]["kind"] = "AUTHORED_UNIT_TEST_NO_AUDIO"
        p.write_text(json.dumps(v))
        with self.assertRaisesRegex(ValueError, "Not real evaluation"):
            compare(data, self.p)
        data["trials"][0]["cases"][0]["score_file"] = "../escaping.json"
        with self.assertRaisesRegex(ValueError, "escapes manifest"):
            compare(data, self.p)

    def test_score_integrity_and_duplicate(self):
        data = self.fixture()
        p = self.p / "candidate-a.json"
        v = json.loads(p.read_text()); v["wer"]["rate"] = 0
        p.write_text(json.dumps(v))
        with self.assertRaisesRegex(ValueError, "Inconsistent scored wer"):
            compare(data, self.p)
        data = self.fixture()
        data["trials"][0]["cases"].append(copy.deepcopy(data["trials"][0]["cases"][0]))
        with self.assertRaisesRegex(ValueError, "duplicated case"):
            compare(data, self.p)

    def test_cli_replaces_favorable_stale_output(self):
        data = self.fixture()
        manifest = self.p / "manifest.json"
        out = self.p / "report.json"
        manifest.write_text(json.dumps(data))
        out.write_text('{"status":"COMPARABLE_INPUTS","verdict":"excellent"}')
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("compare_model_trials.py")),
                                 "--manifest", str(manifest), "--output", str(out)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(out.read_text())["status"], "COMPARABLE_INPUTS")
        data["trials"][0]["cases"][0]["audio_duration_ms"] = -1
        manifest.write_text(json.dumps(data))
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("compare_model_trials.py")),
                                 "--manifest", str(manifest), "--output", str(out)], capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(out.read_text())["status"], "ERROR")


if __name__ == "__main__":
    unittest.main()
