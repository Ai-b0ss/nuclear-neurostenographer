"""Stdlib tests for DiCoP conversion and the no-download research preflight."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import wave

sys.path.insert(0, str(Path(__file__).resolve().parent))

from contract import BASE_MODEL, CHECKPOINT_ID, UPSTREAM_COMMIT
from convert_c2 import convert, read_c2_turns, rttm_escape, rttm_text, validate_intervals
import preflight


class RttmRules(unittest.TestCase):
    def test_escaping_preserves_safe_tokens_and_encodes_utf8_and_controls(self):
        self.assertEqual(rttm_escape("speaker_A-1.~"), "speaker_A-1.~")
        self.assertEqual(
            rttm_escape("spk A/%\nё"), "spk%20A%2F%25%0A%D1%91"
        )
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            rttm_escape("")

    def test_rttm_escapes_session_and_speaker_and_uses_duration(self):
        turns = [{"start_ms": 1250, "end_ms": 3750, "speaker_id": "A B"}]
        self.assertEqual(
            rttm_text("session/1", turns),
            "SPEAKER session%2F1 1 1.250 2.500 <NA> <NA> A%20B <NA> <NA>\n",
        )

    def test_intervals_are_sorted_deterministically(self):
        turns = [
            {"start_ms": 2000, "end_ms": 3000, "speaker_id": "B"},
            {"start_ms": 1000, "end_ms": 2500, "speaker_id": "Z"},
            {"start_ms": 1000, "end_ms": 2500, "speaker_id": "A"},
            {"start_ms": 1000, "end_ms": 2000, "speaker_id": "C"},
        ]
        normalized = validate_intervals(turns, 4000)
        self.assertEqual(
            [(t["start_ms"], t["end_ms"], t["speaker_id"]) for t in normalized],
            [(1000, 2000, "C"), (1000, 2500, "A"), (1000, 2500, "Z"), (2000, 3000, "B")],
        )

    def test_invalid_intervals_are_rejected(self):
        invalid = [
            {"start_ms": -1, "end_ms": 10, "speaker_id": "A"},
            {"start_ms": 10, "end_ms": 10, "speaker_id": "A"},
            {"start_ms": 0, "end_ms": 1001, "speaker_id": "A"},
            {"start_ms": 0.5, "end_ms": 10, "speaker_id": "A"},
            {"start_ms": False, "end_ms": 10, "speaker_id": "A"},
            {"start_ms": 0, "end_ms": 10, "speaker_id": ""},
        ]
        for turn in invalid:
            with self.subTest(turn=turn), self.assertRaises(ValueError):
                validate_intervals([turn], 1000)

    def test_c2_unknown_turns_are_excluded_before_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "case.tsv"
            path.write_text("2000\t3000\t2\n0\t1000\t-1\n1000\t2000\t0\n", encoding="ascii")
            turns, unknown = read_c2_turns(path, 3000)
        self.assertEqual(unknown, 1)
        self.assertEqual([turn["speaker_id"] for turn in turns], ["h0", "h2"])


class Conversion(unittest.TestCase):
    def make_case(self, root, case_id):
        audio = root / f"{case_id}.wav"
        with wave.open(str(audio), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b"\0\0" * 16000)
        digest = hashlib.sha256(audio.read_bytes()).hexdigest()
        reference = {
            "schema_version": 1,
            "recording_id": case_id,
            "audio_sha256": digest,
            "audio_duration_ms": 1000,
            "diarization": [
                {"start_ms": 500, "end_ms": 1000, "speaker_id": "B"},
                {"start_ms": 0, "end_ms": 750, "speaker_id": "A"},
            ],
        }
        (root / f"{case_id}.ref.json").write_text(
            json.dumps(reference, ensure_ascii=False), encoding="utf-8"
        )
        return {"id": case_id, "audio_sha256": digest}

    def test_reference_conversion_builds_official_flat_audio_layout(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            corpus = root / "corpus"
            corpus.mkdir()
            cases = [self.make_case(corpus, "z last"), self.make_case(corpus, "a")]
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"cases": cases}), encoding="utf-8")
            result = convert(manifest, corpus, root / "out")
            self.assertEqual([row["case_id"] for row in result["cases"]], ["a", "z last"])
            escaped = root / "out/audio/z%20last.wav"
            self.assertTrue(escaped.is_file())
            rttm = root / "out/rttm/z%20last.rttm"
            self.assertEqual(
                rttm.read_text(encoding="ascii"),
                "SPEAKER z%20last 1 0.000 0.750 <NA> <NA> A <NA> <NA>\n"
                "SPEAKER z%20last 1 0.500 0.500 <NA> <NA> B <NA> <NA>\n",
            )
            self.assertEqual(sha256(escaped), result["cases"][1]["audio_sha256"])
            self.assertEqual(result["checkpoint"]["base_model"], BASE_MODEL)
            self.assertFalse(result["checkpoint"]["downloaded"])

    def test_c2_conversion_uses_h_labels_and_counts_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            corpus = root / "corpus"
            turns = root / "turns"
            corpus.mkdir()
            turns.mkdir()
            case = self.make_case(corpus, "case")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"cases": [case]}), encoding="utf-8")
            (turns / "case.tsv").write_text("0\t500\t-1\n500\t1000\t3\n", encoding="ascii")
            result = convert(manifest, corpus, root / "out", "c2", turns)
            row = result["cases"][0]
            self.assertEqual((row["turns"], row["unknown_turns_excluded"]), (1, 1))
            self.assertIn(" h3 ", (root / "out/rttm/case.rttm").read_text(encoding="ascii"))


class Preflight(unittest.TestCase):
    def test_official_checkpoint_is_blocked_and_v3_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            upstream = Path(folder)
            for name in preflight.REQUIRED_SOURCES:
                path = upstream / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture", encoding="ascii")
            with mock.patch.object(preflight, "git", side_effect=[UPSTREAM_COMMIT, ""]):
                english = preflight.inspect(upstream, CHECKPOINT_ID)
            with mock.patch.object(preflight, "git", side_effect=[UPSTREAM_COMMIT, ""]):
                russian_v3 = preflight.inspect(upstream, "nvidia/parakeet-tdt-0.6b-v3")
        self.assertEqual(english["status"], "BLOCKED")
        self.assertEqual(english["checkpoint"]["status"], "LANGUAGE_MISMATCH")
        self.assertEqual(english["inference"]["status"], "NOT_RUN")
        self.assertEqual(russian_v3["checkpoint"]["status"], "WRONG_BASE_MODEL")
        self.assertEqual(russian_v3["checkpoint"]["base_model"], "nvidia/parakeet-tdt-0.6b-v2")
        self.assertFalse(english["checkpoint"]["downloaded"])


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
