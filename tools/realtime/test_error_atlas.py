"""Regression tests for exact time accounting and file identity."""
import hashlib
import json
import tempfile
import unittest
import wave
from array import array
from pathlib import Path
from error_atlas import audit, energy_frames, read_tsv

class ErrorAtlasTest(unittest.TestCase):
    def test_energy_and_tail(self):
        self.assertEqual(len(energy_frames(array("h", [0]*161))), 2)
        self.assertLess(energy_frames(array("h", [0]*160))[0], -100)
        self.assertGreater(energy_frames(array("h", [12000]*160))[0], -10)

    def test_rejects_corrupt_turn(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"h.tsv"
            path.write_text("30\t10\tspk0\n",encoding="utf-8")
            with self.assertRaises(ValueError): read_tsv(path,100)

    def test_exact_scorer_and_attribution(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); wav=d/"sample.wav"
            with wave.open(str(wav),"wb") as f:
                f.setparams((1,2,16000,0,"NONE","not compressed"))
                pcm=array("h",[0]*8000 + [12000]*8000 + [0]*16000)
                f.writeframes(pcm.tobytes())
            ref=dict(schema_version=1,recording_id="test",annotation_source="authored",
                license="authored",kind="SYNTHETIC",
                audio_sha256=hashlib.sha256(wav.read_bytes()).hexdigest(),
                audio_duration_ms=2000,
                diarization=[dict(start_ms=0,end_ms=1200,speaker_id="A")])
            refpath=d/"ref.json";refpath.write_text(json.dumps(ref),encoding="utf-8")
            turns=d/"out.tsv";turns.write_text("400\t900\t0\n",encoding="utf-8")
            result=audit(wav,refpath,turns,d/"out")
            self.assertEqual(result["totals"]["reference_ms"],700)
            self.assertEqual(result["totals"]["missed_ms"],200)
            self.assertGreater(result["totals"]["missed_quiet45_ms"],0)
            self.assertTrue((d/"out/frames.csv").is_file())
            self.assertEqual(result["totals"]["confusion_ms"],0)
            refpath.write_text(json.dumps({**ref, "audio_sha256": "0"*64}),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"SHA-256"):audit(wav,refpath,turns,d/"no")

if __name__=="__main__": unittest.main()
