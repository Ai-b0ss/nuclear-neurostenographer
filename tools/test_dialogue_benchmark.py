"""Authored integrity/arithmetic probes, never actual model accuracy evidence."""
import copy
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave
from evaluate_dialogue_benchmark import assess
import provision_dialogue_benchmark as fixtures

ROOT = Path(__file__).resolve().parents[1]
BASH = "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else shutil.which("bash")


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".local").mkdir(exist_ok=True)

    def test_fixture_uses_external_text_and_preserves_exact_pcm(self):
        (ROOT / ".local").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            rows = [{"audio_path": f"wavs/clip{i}.wav", "speaker_id": speaker,
                     "emotion": "neutral", "text": str(i)} for i, speaker in enumerate(["D", "M", "D"])]
            with (source / "test.csv").open("w", newline="", encoding="utf-8") as out:
                writer = csv.DictWriter(out, fieldnames=rows[0].keys(), delimiter="|")
                writer.writeheader(); writer.writerows(rows)
            (source / "LICENSE.md").write_text("Authored integrity fixture license")
            lock = {"repository": "authored", "revision": "authored", "selection_policy": "authored D M D",
                "sample_rate": 16000, "gap_frames": 8000, "clips": []}
            for key, path in [("metadata", "test.csv"), ("license", "LICENSE.md")]:
                lock[key] = {"path": path, "sha256": hashlib.sha256((source / path).read_bytes()).hexdigest()}
            pcm = [struct.pack("<h", v) * 1600 for v in [100, -200, 300]]
            for i, data in enumerate(pcm):
                path = source / f"clip{i}.wav"
                with wave.open(str(path), "wb") as wav:
                    wav.setparams((1, 2, 16000, 1600, "NONE", "not compressed")); wav.writeframes(data)
                lock["clips"].append({"path": "wavs/" + path.name, "speaker": rows[i]["speaker_id"],
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "frames": 1600})
            expected = io.BytesIO()
            with wave.open(expected, "wb") as wav:
                wav.setparams((1, 2, 16000, 20800, "NONE", "not compressed"))
                wav.writeframes(pcm[0] + bytes(16000) + pcm[1] + bytes(16000) + pcm[2])
            lock["composite_sha256"] = hashlib.sha256(expected.getvalue()).hexdigest()
            ref = fixtures.compose(source, root / "output", lock)
            self.assertEqual((root / "output/aba.wav").read_bytes(), expected.getvalue())
            self.assertEqual([s["text"] for s in ref["text_segments"]], ["0", "1", "2"])
            self.assertNotIn("diarization", ref)
            self.assertEqual(ref["audio_duration_ms"], 1300)
            for path in ["test.csv", "LICENSE.md", "clip0.wav"]:
                original = (source / path).read_bytes()
                (source / path).write_bytes(b"corrupted")
                with self.assertRaises(ValueError):
                    fixtures.compose(source, root / "rejected", lock)
                (source / path).write_bytes(original)

    def test_provision_failure_removes_stale_owned_evidence(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as tmp:
            root = Path(tmp)
            for directory in [root / ".local/dialogue-benchmark", root / ".local/androidTestAssets/dialogs"]:
                directory.mkdir(parents=True)
                for name in ["reference.json", "hypothesis.json", "scores.json", "aba.wav"]:
                    (directory / name).write_text("stale")
            with patch.object(fixtures, "ROOT", root), patch.object(sys, "argv", ["provision"]), \
                 patch.object(fixtures, "download", side_effect=OSError("authored network failure")):
                with self.assertRaises(OSError):
                    fixtures.main()
            self.assertFalse(list((root / ".local").rglob("scores.json")))
            self.assertFalse(list((root / ".local").rglob("reference.json")))

    def test_external_text_metrics_and_recurrence_are_separate_from_der(self):
        r = {"schema_version": 1, "recording_id": "authored", "annotation_source": "authored",
             "license": "authored", "kind": "authored", "audio_sha256": "0" * 64,
             "audio_duration_ms": 3000, "text_segments": [
                 {"start_ms": i*1000, "end_ms": (i+1)*1000, "speaker_id": s, "text": t}
                 for i, (s, t) in enumerate(zip(["D", "M", "D"], ["один", "два", "три"]))]}
        h = {"audio_duration_ms": 3000, "audio_sha256": "0" * 64,
             "segments": [{**s, "speaker_id": "X" if s["speaker_id"] == "D" else "Y", "attribution_reliable": True}
                          for s in r["text_segments"]]}
        h["diarization"] = [{k: v for k, v in s.items() if k != "text"} | {"attribution_eligible": True} for s in h["segments"]]
        report = assess(r, h)
        self.assertEqual(report["wer"]["rate"], 0)
        self.assertEqual(report["cpwer"]["rate"], 0)
        self.assertEqual(report["der"]["status"], "NOT_SCORED")
        self.assertEqual(report["recurrence_probe"]["status"], "PASS")
        h["segments"][2]["speaker_id"] = "Z"
        h["diarization"][2]["speaker_id"] = "Z"
        report = assess(r, h)
        self.assertGreater(report["cpwer"]["rate"], 0)
        self.assertEqual(report["recurrence_probe"]["status"], "FAIL")
        r["diarization"] = r["text_segments"]  # Clip extents must never become speech truth.
        with self.assertRaises(ValueError):
            assess(r, h)

    def test_threshold_sweep_preserves_baseline_and_rejects_malformed_evidence(self):
        # Small authored arithmetic probe; no neural network execution claimed.
        reference = {"schema_version": 1, "recording_id": "authored",
            "annotation_source": "authored", "license": "authored", "kind": "authored",
            "audio_sha256": "0" * 64, "audio_duration_ms": 3000,
            "text_segments": [{"start_ms": i * 1000, "end_ms": (i + 1) * 1000,
                "speaker_id": speaker, "text": word}
                for i, (speaker, word) in enumerate([("D", "один"), ("M", "два"), ("D", "три")])]}
        def turns(labels):
            return [{"start_ms": i * 1000, "end_ms": (i + 1) * 1000,
                "speaker_id": name, "attribution_eligible": True}
                for i, name in enumerate(labels)]
        collapsed = turns(["Speaker 1"] * 3)
        distinct = turns(["Speaker 1", "Speaker 2", "Speaker 1"])
        hypothesis = {"audio_sha256": "0" * 64, "audio_duration_ms": 3000,
            "segments": [{**item, "speaker_id": "Speaker 1", "attribution_reliable": True}
                for item in reference["text_segments"]],
            "diarization": collapsed,
            "production_clustering_threshold": 0.9,
            "clustering_sweep": [{"threshold": threshold,
                "diarization": distinct if threshold <= 0.65 else collapsed,
                "process_ms": 123} for threshold in (0.5, 0.65, 0.8, 0.9)]}
        report = assess(reference, hypothesis)
        self.assertEqual(report["recurrence_probe"]["status"], "FAIL")
        self.assertEqual([t["recurrence_probe"]["status"] for t in report["clustering_sweep"]],
                         ["PASS", "PASS", "FAIL", "FAIL"])
        self.assertEqual(report["clustering_experiment_status"], "EXPERIMENT_ONLY_NO_AUTO_SELECTION")
        self.assertEqual(report["cpwer"]["status"], "SCORED")
        self.assertEqual(report["clustering_sweep"][0]["eligible_speaker_count"], 2)
        for change in ("threshold", "baseline", "missing", "duration", "eligible", "nan", "production"):
            bad = copy.deepcopy(hypothesis)
            if change == "threshold": bad["clustering_sweep"][0]["threshold"] = 0.9
            if change == "baseline": bad["clustering_sweep"][-1]["diarization"] = distinct
            if change == "missing": bad["clustering_sweep"].pop()
            if change == "duration": bad["clustering_sweep"][1]["process_ms"] = -1
            if change == "eligible": bad["clustering_sweep"][2]["diarization"][1]["attribution_eligible"] = "true"
            if change == "nan": bad["clustering_sweep"][0]["threshold"] = float("nan")
            if change == "production": bad["production_clustering_threshold"] = 0.5
            with self.subTest(change=change), self.assertRaises(ValueError):
                assess(reference, bad)

    def test_disjoint_holdout_lock_is_frozen_before_inference(self):
        lock = fixtures.HOLDOUT_LOCK
        base = fixtures.LOCK
        self.assertEqual(lock["selection_indices"], [18, 49, 24, 51])
        self.assertEqual([clip["speaker"] for clip in lock["clips"]], ["M", "D", "M", "D"])
        self.assertEqual(lock["composite_sha256"],
            "52f34a15e35af61ac193d01ea135712e7b71df64d74c6e4d9d0c0da4772fb070")
        self.assertFalse({c["path"] for c in base["clips"]} & {c["path"] for c in lock["clips"]})
        self.assertEqual(len({c["sha256"] for c in lock["clips"]}), 4)
        self.assertEqual(lock["revision"], base["revision"])
        self.assertEqual(lock["license"], base["license"])

    def test_holdout_four_turn_pairwise_recurrence_and_no_threshold_sweep(self):
        reference = {"schema_version": 1, "recording_id": "authored-four", "annotation_source": "authored",
            "license": "authored", "kind": "ACTED_COMPOSED_FOUR_UTTERANCES_DISJOINT_FROM_DEVELOPMENT",
            "evaluation_suite": "holdout", "audio_sha256": "0" * 64, "audio_duration_ms": 4000,
            "text_segments": [
                {"start_ms": i * 1000, "end_ms": (i + 1) * 1000,
                 "speaker_id": speaker, "text": word}
                for i, (speaker, word) in enumerate(
                    [("M", "один"), ("D", "два"), ("M", "три"), ("D", "четыре")])]}
        predicted = [
            {"start_ms": i * 1000, "end_ms": (i + 1) * 1000,
             "speaker_id": label, "attribution_eligible": True}
            for i, label in enumerate(["X", "Y", "X", "Y"])]
        hypothesis = {"audio_sha256": reference["audio_sha256"],
            "audio_duration_ms": 4000, "benchmark_suite": "holdout",
            "production_clustering_threshold": 0.8, "diarization": predicted,
            "segments": [{**ref, "speaker_id": p["speaker_id"], "attribution_reliable": True}
                         for ref, p in zip(reference["text_segments"], predicted)]}
        report = assess(reference, hypothesis)
        self.assertEqual(report["recurrence_probe"]["status"], "PASS")
        self.assertEqual((report["recurrence_probe"]["same_speaker_pairs"],
                          report["recurrence_probe"]["different_speaker_pairs"]), (2, 4))
        self.assertEqual(report["cpwer"]["rate"], 0)
        self.assertEqual(report["der"]["status"], "NOT_SCORED")
        self.assertIn("SAME_DATASET", report["holdout_scope"])
        bad = copy.deepcopy(hypothesis)
        bad["diarization"][-1]["speaker_id"] = "X"
        self.assertEqual(assess(reference, bad)["recurrence_probe"]["status"], "FAIL")
        bad = copy.deepcopy(hypothesis)
        bad["diarization"][-1]["attribution_eligible"] = False
        self.assertEqual(assess(reference, bad)["recurrence_probe"]["status"], "UNDETERMINED")
        for mutation in ("wrong_suite", "wrong_threshold", "sweep", "wrong_reference_count"):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                altered = copy.deepcopy(hypothesis)
                ref = copy.deepcopy(reference)
                if mutation == "wrong_suite": altered["benchmark_suite"] = "development"
                if mutation == "wrong_threshold": altered["production_clustering_threshold"] = 0.9
                if mutation == "sweep": altered["clustering_sweep"] = []
                if mutation == "wrong_reference_count": ref["text_segments"].pop()
                assess(ref, altered)

    def test_cli_corruption_replaces_previous_favorable_score(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as tmp:
            root = Path(tmp)
            (root / "reference.json").write_text("[]")
            (root / "hypothesis.json").write_text("{}")
            (root / "scores.json").write_text('{"status":"SCORED","wer":0}')
            result = subprocess.run([sys.executable, ROOT / "tools/evaluate_dialogue_benchmark.py", root], capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads((root / "scores.json").read_text())["status"], "ERROR")

    def test_cli_rejects_stale_device_output_even_when_audio_and_text_match(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as tmp:
            root = Path(tmp)
            reference = {"schema_version": 1, "recording_id": "authored", "annotation_source": "authored",
                "license": "authored", "kind": "authored", "audio_sha256": "0" * 64,
                "audio_duration_ms": 1000, "text_segments": [
                    {"start_ms": 0, "end_ms": 1000, "speaker_id": "A", "text": "слово"}]}
            hypothesis = {"audio_sha256": "0" * 64, "audio_duration_ms": 1000,
                "segments": reference["text_segments"], "diarization": []}
            (root / "reference.json").write_text(json.dumps(reference))
            (root / "invocation.json").write_text(json.dumps({"id": "a" * 32}))
            for nonce, expected in [(None, 1), ("b" * 32, 1), ("a" * 32, 0)]:
                hypothesis["benchmark_invocation"] = nonce
                (root / "hypothesis.json").write_text(json.dumps(hypothesis))
                result = subprocess.run([sys.executable, ROOT / "tools/evaluate_dialogue_benchmark.py", root], capture_output=True)
                self.assertEqual(result.returncode, expected)
                score = json.loads((root / "scores.json").read_text())
                if expected:
                    self.assertEqual(score["status"], "ERROR")
                else:
                    self.assertEqual(score["wer"]["rate"], 0)

    @unittest.skipUnless(BASH and Path(BASH).exists(), "Bash unavailable")
    def test_shell_preserves_failures_and_rejects_stale_or_adb_error_output(self):
        # Authored shell commands only, no emulator or model execution evidence.
        for gradle_exit, mode, expected in [(0, "fresh", 0), (7, "fresh", 7),
                                             (0, "stale", 1), (0, "adb_error", 1)]:
            with self.subTest(gradle_exit=gradle_exit, mode=mode), tempfile.TemporaryDirectory(dir=ROOT / ".local") as tmp:
                root = Path(tmp)
                output = root / ".local/dialogue-benchmark"
                output.mkdir(parents=True)
                reference = {"schema_version": 1, "recording_id": "authored", "annotation_source": "authored",
                    "license": "authored", "kind": "authored", "audio_sha256": "0" * 64,
                    "audio_duration_ms": 1000, "text_segments": [
                        {"start_ms": 0, "end_ms": 1000, "speaker_id": "A", "text": "word"}]}
                (output / "reference.json").write_text(json.dumps(reference))
                (output / "scores.json").write_text('{"stale_favorable":true}')
                startup = root / "commands.sh"
                startup.write_text('''
python3() { "$TEST_PYTHON" "$@"; }
gradle() { return "$FAKE_GRADLE_EXIT"; }
adb() {
  if [[ "$*" != *"exec-out"* ]]; then return 0; fi
  if [[ "$FAKE_MODE" == adb_error ]]; then echo 'run-as: unknown package'; return 0; fi
  python3 - <<'PY'
import json, os
from pathlib import Path
p=Path('.local/dialogue-benchmark')
r=json.loads((p/'reference.json').read_text())
nonce=json.loads((p/'invocation.json').read_text())['id']
print(json.dumps({'audio_sha256': r['audio_sha256'], 'audio_duration_ms': 1000,
 'segments': r['text_segments'], 'diarization': [],
 'benchmark_invocation': nonce if os.environ['FAKE_MODE']=='fresh' else 'b'*32}))
PY
}
''', encoding="utf-8", newline="\n")
                env = dict(os.environ, BASH_ENV=startup.as_posix(), TEST_PYTHON=Path(sys.executable).as_posix(),
                           FAKE_GRADLE_EXIT=str(gradle_exit), FAKE_MODE=mode)
                result = subprocess.run([BASH, (ROOT / "tools/run_android_benchmark.sh").as_posix()],
                    cwd=root, env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stderr)
                score = json.loads((output / "scores.json").read_text())
                self.assertNotIn("stale_favorable", score)
                self.assertEqual(score.get("status") == "ERROR", mode != "fresh")


if __name__ == "__main__":
    unittest.main()
