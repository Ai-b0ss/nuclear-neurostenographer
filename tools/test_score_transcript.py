"""Authored arithmetic fixtures, NOT audio/model accuracy evidence."""
import copy
import itertools
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from score_transcript import assignment, cpwer, der, edit_counts, evaluate, words

ROOT = Path(__file__).resolve().parents[1]


def turn(start, end, who, text=""):
    return {"start_ms": start, "end_ms": end, "speaker_id": who, "text": text}


class MetricsTests(unittest.TestCase):
    def test_russian_normalization(self):
        self.assertEqual(words("Ёлка, ёж! ДА—нет 2026. foo_bar"), ["елка", "еж", "да", "нет", "2026", "foo", "bar"])
        self.assertEqual(edit_counts(words("Привет, мир!"), words("привет МИР"))["rate"], 0)

    def test_word_errors_and_empty_reference(self):
        r = edit_counts(["a", "b", "c"], ["a", "x", "c", "d"])
        self.assertEqual((r["substitutions"], r["insertions"], r["errors"]), (1, 1, 2))
        self.assertEqual(edit_counts(["a", "b"], [])["deletions"], 2)
        self.assertEqual(edit_counts([], ["a"])["insertions"], 1)
        self.assertIsNone(edit_counts([], ["a"])["rate"])
        self.assertGreater(edit_counts(["a"], ["b", "c", "d"])["rate"], 1)

    def test_assignment_against_exhaustive_oracle(self):
        rng = random.Random(179)
        for n in range(7):
            for _ in range(5):
                cost = [[rng.randrange(-20, 21) for _ in range(n)] for _ in range(n)]
                best = min((sum(cost[i][j] for i, j in enumerate(p)), p)
                           for p in itertools.permutations(range(n)))
                self.assertEqual(assignment(cost), best)
        with self.assertRaises(ValueError):
            assignment([[0] * 13 for _ in range(13)])

    def test_cpwer_recurring_speaker_permutation(self):
        r = [turn(0, 1000, "A", "добрый день"), turn(1000, 2000, "B", "привет"), turn(2000, 3000, "A", "да")]
        h = [turn(0, 1000, "2", "добрый день"), turn(1000, 2000, "1", "привет"), turn(2000, 3000, "2", "да")]
        self.assertEqual(cpwer(r, h)["errors"], 0)
        h[2]["speaker_id"] = "3"  # A split on recurrence
        self.assertGreater(cpwer(r, h)["errors"], 0)
        h[2]["speaker_id"] = None
        self.assertEqual(cpwer(r, h)["status"], "NOT_SCORED")
        self.assertEqual(cpwer(r, [])["deletions"], 4)

    def test_cpwer_unmatched_speakers(self):
        r = [turn(0, 1, "A", "a b")]
        h = [turn(0, 1, "1", "a b"), turn(1, 2, "2", "c d")]
        result = cpwer(r, h)
        self.assertEqual((result["errors"], result["insertions"], result["rate"]), (2, 2, 1))

    def test_cpwer_against_exhaustive_word_and_speaker_oracle(self):
        # Independent full-matrix edit distance; do not reuse production DP/counts.
        def distance(a, b):
            d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
            for i in range(len(a) + 1):
                d[i][0] = i
            for j in range(len(b) + 1):
                d[0][j] = j
            for i in range(1, len(a) + 1):
                for j in range(1, len(b) + 1):
                    d[i][j] = min(d[i-1][j] + 1, d[i][j-1] + 1,
                                  d[i-1][j-1] + (a[i-1] != b[j-1]))
            return d[-1][-1]
        rng = random.Random(214)
        for _ in range(50):
            r = [[rng.choice("abc") for _ in range(rng.randrange(1, 6))] for _ in range(rng.randrange(1, 5))]
            h = [[rng.choice("abc") for _ in range(rng.randrange(1, 6))] for _ in range(rng.randrange(5))]
            n = max(len(r), len(h))
            rp = r + [[] for _ in range(n - len(r))]
            hp = h + [[] for _ in range(n - len(h))]
            expected = min(sum(distance(rp[i], hp[j]) for i, j in enumerate(p))
                           for p in itertools.permutations(range(n)))
            actual = cpwer([turn(i, i+1, str(i), " ".join(s)) for i, s in enumerate(r)],
                           [turn(i, i+1, str(i), " ".join(s)) for i, s in enumerate(h)])
            self.assertEqual(actual["errors"], expected)
            self.assertEqual(actual["errors"], sum(actual[k] for k in ("substitutions", "deletions", "insertions")))

    def test_der_components_and_global_mapping(self):
        r = [turn(0, 1000, "A"), turn(1000, 2000, "B"), turn(2000, 3000, "A")]
        h = [turn(0, 1000, "X"), turn(1000, 2000, "Y"), turn(2000, 3000, "X")]
        self.assertEqual(der(r, h, 4000)["rate"], 0)
        # Remove B, add hallucinated speech in silence; A->X mapping remains global.
        h = [h[0], h[2], turn(3000, 3500, "X")]
        result = der(r, h, 4000)
        self.assertEqual((result["miss_ms"], result["false_alarm_ms"], result["confusion_ms"]), (1000, 500, 0))
        self.assertEqual(result["rate"], 0.5)
        h = [turn(0, 3000, "X")]
        self.assertEqual(der(r, h, 3000)["confusion_ms"], 1000)

    def test_der_overlap_collar_and_unknown(self):
        r = [turn(0, 1000, "A"), turn(500, 1500, "B")]
        h = [turn(0, 1000, "X")]
        self.assertEqual(der(r, h, 2000)["rate"], 0.5)
        self.assertEqual(der(r, h, 2000, skip_overlap=True)["reference_speaker_ms"], 1000)
        result = der([turn(100, 900, "A")], [turn(0, 1000, "X")], 1000, 100)
        self.assertEqual((result["rate"], result["scored_wall_ms"]), (0, 600))
        unknown = der([turn(0, 1000, "A")], [turn(0, 1000, None)], 1000)
        self.assertEqual((unknown["confusion_ms"], unknown["rate"]), (1000, 1))
        empty = der([], [turn(0, 1000, "X")], 1000)
        self.assertIsNone(empty["rate"])
        self.assertEqual(empty["false_alarm_ms"], 1000)
        # Same-speaker duplicate/overlapping intervals count as one active speaker.
        self.assertEqual(der([turn(0, 1000, "A")] * 2, [turn(0, 1000, "X")], 1000)["rate"], 0)

    def test_der_against_independent_discrete_oracle(self):
        rng = random.Random(19)
        for _ in range(80):
            r = [turn(t, t + 1, s) for t in range(6) for s in "AB" if rng.randrange(2)]
            h = [turn(t, t + 1, s) for t in range(6) for s in "XY" if rng.randrange(2)]
            best = None
            for permutation in itertools.permutations("AB"):
                errors = total = 0
                mapping = dict(zip("XY", permutation))
                for t in range(6):
                    rs = {s["speaker_id"] for s in r if s["start_ms"] == t}
                    hs = {s["speaker_id"] for s in h if s["start_ms"] == t}
                    correct = len(rs & {mapping[s] for s in hs})
                    errors += max(len(rs), len(hs)) - correct
                    total += len(rs)
                best = errors if best is None else min(best, errors)
            actual = der(r, h, 6)
            self.assertEqual(actual["miss_ms"] + actual["false_alarm_ms"] + actual["confusion_ms"], best)
            self.assertEqual(actual["reference_speaker_ms"], total)

    def test_schema_and_missing_ground_truth(self):
        fixture = json.loads((ROOT / "tools/fixtures/metrics-ru-authored.json").read_text(encoding="utf-8"))
        r, h = fixture["reference"], fixture["hypothesis"]
        result = evaluate(r, h)
        for name in ("wer", "cpwer", "der"):
            self.assertEqual(result[name]["rate"], 0)
            self.assertEqual(evaluate(None, h)[name]["status"], "NOT_SCORED")
        for key, val in (("audio_sha256", "a" * 64), ("audio_duration_ms", 1)):
            bad = dict(h, **{key: val})
            with self.assertRaises(ValueError):
                evaluate(r, bad)
        no_turns = dict(h)
        del no_turns["diarization"]
        self.assertEqual(evaluate(r, no_turns)["der"]["status"], "NOT_SCORED")
        bad = copy.deepcopy(r)
        bad["text_segments"][0]["end_ms"] = 5000
        with self.assertRaises(ValueError):
            evaluate(bad, h)

    def test_cli_failure_replaces_stale_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            hyp, out = Path(tmp) / "h.json", Path(tmp) / "o.json"
            hyp.write_text("{broken")
            out.write_text('{"wer":{"rate":0}}')
            run = subprocess.run([sys.executable, ROOT / "tools/score_transcript.py", "--hypothesis", hyp, "--output", out], capture_output=True)
            self.assertEqual(run.returncode, 1)
            self.assertEqual(json.loads(out.read_text())["status"], "ERROR")
            hyp.write_text('{"segments":[]}')
            run = subprocess.run([sys.executable, ROOT / "tools/score_transcript.py", "--hypothesis", hyp, "--output", out], capture_output=True)
            self.assertEqual(run.returncode, 2)
            self.assertEqual(json.loads(out.read_text())["wer"]["status"], "NOT_SCORED")

    def test_malformed_roots_and_flag_types_never_preserve_stale_pass(self):
        fixture = json.loads((ROOT / "tools/fixtures/metrics-ru-authored.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            ref, hyp, out = (Path(tmp) / name for name in ("r.json", "h.json", "o.json"))
            cases = []
            for malformed in ([], "wrong root", 1, None, True):
                cases.append((malformed, fixture["hypothesis"]))
                cases.append((fixture["reference"], malformed))
            for flag in (None, "false", 0, [], {}):
                h = copy.deepcopy(fixture["hypothesis"])
                h["segments"][0]["attribution_reliable"] = flag
                cases.append((fixture["reference"], h))
            for duration in (True, 1000.0, "1000"):
                cases.append((fixture["reference"], dict(fixture["hypothesis"], audio_duration_ms=duration)))
            for r, h in cases:
                ref.write_text(json.dumps(r), encoding="utf-8")
                hyp.write_text(json.dumps(h), encoding="utf-8")
                out.write_text('{"wer":{"rate":0,"status":"SCORED"}}', encoding="utf-8")
                run = subprocess.run([sys.executable, ROOT / "tools/score_transcript.py",
                    "--reference", ref, "--hypothesis", hyp, "--output", out], capture_output=True)
                self.assertEqual(run.returncode, 1, run.stderr)
                self.assertEqual(json.loads(out.read_text())["status"], "ERROR")
            # Bad hypothesis roots are invalid even without a reference file.
            for h in ([], None, "invalid"):
                with self.assertRaises(ValueError):
                    evaluate(None, h)
            for collar in (-1, True, 0.5):
                with self.assertRaises(ValueError):
                    evaluate(None, fixture["hypothesis"], collar)


if __name__ == "__main__":
    unittest.main()
