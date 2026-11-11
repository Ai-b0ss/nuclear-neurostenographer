import json
import tempfile
import unittest
from pathlib import Path
from compare_transcript_outputs import words, distance, cpwer, evaluate, transcript


class BenchmarkTest(unittest.TestCase):
    def turns(self, *items):
        return [(i * 1000, (i + 1) * 1000, speaker, text)
                for i, (speaker, text) in enumerate(items)]

    def test_wer(self):
        self.assertEqual(distance(words("Привет, ЁЖ!"), words("привет еж")), 0)
        self.assertEqual(distance(words("один два три"), words("один три")), 1)
        self.assertEqual(distance(words(""), words("тест")), 1)

    def test_speaker_permutation(self):
        ref = self.turns(("a", "привет"), ("b", "да"), ("a", "пока"))
        swapped = self.turns(("z", "привет"), ("y", "да"), ("z", "пока"))
        self.assertEqual(cpwer(ref, swapped), 0)
        self.assertEqual(evaluate(ref, swapped)["cpwer"], 0.0)
        merged = self.turns(("z", "привет"), ("z", "да"), ("z", "пока"))
        self.assertGreater(cpwer(ref, merged), 0)

    def test_bad_input(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "t.json"
            p.write_text(json.dumps({"transcript": [{"speaker_id": "a",
                "start_ms": 0, "end_ms": 0, "text": "bad"}]}), encoding="utf8")
            with self.assertRaises(ValueError):
                transcript(p)
            p.write_text(json.dumps({"transcript": [{"speaker_id": None,
                "start_ms": 0, "end_ms": 123, "text": "word"}]}), encoding="utf8")
            self.assertEqual(transcript(p)[0][2], "unknown")


if __name__ == "__main__":
    unittest.main()
