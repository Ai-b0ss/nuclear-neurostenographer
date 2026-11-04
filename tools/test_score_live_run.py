"""Authored data only: reference/hypothesis building for the live read-aloud scorer."""
import json
import unittest
from pathlib import Path

import score_live_run

SCRIPT = json.loads((Path(__file__).resolve().parents[1] / "tools/fixtures/live-dialogue-script-ru.json").read_text(encoding="utf-8"))


class LiveScoreTests(unittest.TestCase):
    def export(self, texts, speakers):
        return {"audio_duration_ms": 60000, "segments": [
            {"start_ms": i * 10000, "end_ms": (i + 1) * 10000 - 500, "speaker_id": speakers[i], "text": texts[i]}
            for i in range(len(texts))]}

    def test_reference_covers_the_script_in_order_with_valid_intervals(self):
        reference, hypothesis = score_live_run.build(self.export(["x"], ["S1"]), SCRIPT, "ab" * 32)
        segments = reference["text_segments"]
        self.assertEqual([s["text"] for s in segments], [t["text"] for t in SCRIPT["turns"]])
        self.assertTrue(all(0 <= s["start_ms"] < s["end_ms"] <= 60000 for s in segments))
        self.assertEqual(segments[-1]["end_ms"], 60000)
        self.assertEqual(hypothesis["segments"][0]["speaker_id"], "S1")

    def test_perfect_reading_scores_zero_errors_and_wrong_speakers_are_caught(self):
        texts = [t["text"] for t in SCRIPT["turns"]]
        import subprocess, sys, tempfile
        root = Path(__file__).resolve().parents[1]
        (root / ".local").mkdir(exist_ok=True)
        for speakers, expect in ((["S1", "S2"] * 3, 0), (["S1"] * 6, None)):
            with tempfile.TemporaryDirectory(dir=root / ".local") as tmp:
                export = Path(tmp) / "t.json"
                export.write_text(json.dumps(self.export(texts, speakers)), encoding="utf-8")
                out = subprocess.run([sys.executable, str(root / "tools/score_live_run.py"), "--export", str(export),
                                      "--audio-sha256", "cd" * 32, "--out-dir", str(Path(tmp) / "o")],
                                     capture_output=True, text=True).stdout
                self.assertIn("WER 0 /", out.splitlines()[0]) if expect == 0 else self.assertNotIn("cpWER 0 /", out)


if __name__ == "__main__":
    unittest.main()
