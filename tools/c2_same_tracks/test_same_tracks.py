"""Rules of the same-recordings comparison on hand-made data; no model, audio file, phone or emulator."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import wave
import io

import numpy as np

from build_same_corpus import wav_bytes
from prepare_phone_assets import plan_rows
from score_phone_run import score
from score_same_corpus import der, measure, speaker_measures
import random
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from score_transcript import der as reference_der  # noqa: E402

SHA = "a" * 64


def reference(turns, text=None, duration=10000):
    out = {"schema_version": 1, "recording_id": "x", "audio_sha256": SHA, "audio_duration_ms": duration, "annotation_source": "test",
           "license": "test", "kind": "TEST", "diarization": [{"start_ms": a, "end_ms": b, "speaker_id": s} for a, b, s in turns]}
    if text:
        out["text_segments"] = [{"start_ms": a, "end_ms": b, "speaker_id": s, "text": t} for (a, b, s), t in zip(turns, text)]
    return out


class Rules(unittest.TestCase):
    def test_wav_conversion_truncates_like_the_phone_tracks(self):
        data = wav_bytes(np.array([0.5, -0.5, 0.99999, 2.0], dtype=np.float32))
        with wave.open(io.BytesIO(data)) as w:
            samples = np.frombuffer(w.readframes(4), dtype="<i2")
            self.assertEqual((w.getframerate(), w.getnchannels(), w.getsampwidth()), (16000, 1, 2))
        self.assertEqual(samples.tolist(), [16383, -16383, 32766, 32767])

    def test_phone_plan_is_fixed_by_rule(self):
        cases = [{"id": i, "set": "holdout"} for i in ("hold-s5-r24", "hold-s4-r30", "hold-s4-r00", "hold-s5-r19", "hold-s4-r01", "hold-s6-r01")]
        rows = plan_rows(cases)
        self.assertEqual([r[0] for r in rows[:3]], ["syn3-clean", "syn3-brown", "syn4-noise"])
        self.assertTrue(all(r[1] == 2 for r in rows[:3]))
        self.assertEqual([r[0] for r in rows if r[0].startswith("hold")], ["hold-s4-r00", "hold-s4-r01", "hold-s5-r19", "hold-s5-r24", "hold-s6-r01"])
        # Text may leave the phone only for the synthetic tracks, never for real calls.
        self.assertEqual({r[0] for r in rows if r[3] == 1}, {r[0] for r in rows if r[0].startswith(("syn", "hold"))})

    def test_der_equals_the_project_scorer(self):
        rng = random.Random(7)
        for _ in range(60):
            def turns(prefix, count):
                out = []
                for _ in range(rng.randint(1, 8)):
                    a = rng.randrange(0, 9000, 10)
                    out.append({"start_ms": a, "end_ms": min(10000, a + rng.randrange(100, 3000, 10)), "speaker_id": f"{prefix}{rng.randrange(count)}"})
                return out
            ref, hyp = turns("r", rng.randint(1, 4)), turns("h", rng.randint(1, 6))
            for collar, skip in ((0, False), (250, False), (250, True)):
                ours, theirs = der(ref, hyp, 10000, collar, skip), reference_der(ref, hyp, 10000, collar, skip)
                self.assertEqual(ours["rate"], theirs["rate"])
                self.assertEqual(ours["miss_ms"] + ours["false_alarm_ms"], theirs["miss_ms"] + theirs["false_alarm_ms"])

    def test_split_and_merge_are_counted_apart(self):
        ref = [(0, 2000, "A"), (2000, 4000, "B"), (4000, 6000, "C")]
        hyp = [(0, 1000, 0), (1000, 2000, 1), (2000, 6000, 2)]
        m = speaker_measures(reference(ref)["diarization"], hyp, 6000)
        self.assertEqual(m["split_speakers"], ["A"])
        self.assertEqual(m["merged_clusters"], ["h2"])
        # Best one-to-one mapping: A->h0 or h1 (1 s), B or C ->h2 (2 s): 3 of 6 s correct.
        self.assertEqual((m["attributed_correctly"], m["frames"]), (300, 600))

    def test_unattributed_words_never_get_a_cpwer(self):
        case = {"id": "x", "set": "phone3", "text": True, "der": "NOT_SCORED: test"}
        ref = reference([(0, 3000, "1"), (3000, 6000, "2")], ["привет как дела", "хорошо спасибо"])
        segments = [{"start_ms": 0, "end_ms": 3000, "speaker_id": "Speaker 1", "text": "привет как дела"},
                    {"start_ms": 3000, "end_ms": 6000, "speaker_id": None, "text": "хорошо спасибо"}]
        row = measure(case, ref, [(0, 3000, 0), (3000, 6000, -1)], segments)
        self.assertEqual(row["wer"]["errors"], 0)
        self.assertEqual(row["cpwer"]["status"], "NOT_SCORED")
        # The pessimistic companion counts the two unattributed words as deleted; an "unknown" speaker would have matched speaker 2.
        self.assertEqual((row["cpwer_u"]["errors"], row["unattributed_words"]), (2, 2))
        self.assertEqual(row["der"]["status"], "NOT_SCORED")

    def test_phone_runs_are_scored_like_the_host_and_compared_with_it(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "C0").mkdir()
            (root / "C2").mkdir()
            (root / "C0/mix.tsv").write_text("0\t4000\t0\n4000\t8000\t1\n", encoding="ascii")
            (root / "C2/mix.tsv").write_text("0\t4000\t0\n4000\t8000\t1\n", encoding="ascii")
            ref = reference([(0, 4000, "a"), (4000, 8000, "b")], duration=8000)
            (root / "mix.ref.json").write_text(json.dumps(ref), encoding="utf-8")
            case = {"id": "mix", "set": "realmix", "speakers": 2, "noise": None, "text": False, "der": "SCORED"}
            run = lambda backend, turns, attempt=0: {"case": "mix", "backend": backend, "attempt": attempt, "status": "OK", "audio_ms": 8000,
                                                     "wall_ms": 900, "infer_ms": 800, "load_ms": 100, "peak_total_pss_kib": 400 * 1024, "turns": turns}
            evidence = {"device": {"abi": "arm64-v8a"}, "runs": [run("C0", [[0, 4000, 0], [4000, 8000, 1]]), run("C0", [[0, 4000, 0], [4000, 8000, 1]], 1),
                                                                  run("C2", [[0, 4000, 1], [4000, 6000, 0], [6000, 8000, 2]])]}
            report = score(evidence, {"mix": case}, root, root)
        rows = {r["system"]: r for r in report["rows"] if r["attempt"] == 0}
        self.assertEqual(rows["C0"]["der"]["rate"], 0.0)
        self.assertEqual(rows["C0"]["host_agreement"], {"der_phone_vs_host": 0.0, "same_speaker_count": True})
        self.assertFalse(rows["C2"]["host_agreement"]["same_speaker_count"])
        self.assertEqual(report["repeat_runs_identical"], {"mix/C0": True})
        self.assertEqual(report["summary"]["realmix"]["C2"]["split_speakers"], 1)


if __name__ == "__main__":
    unittest.main()
