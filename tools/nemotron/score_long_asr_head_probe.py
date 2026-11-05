"""Verify paired 20-minute Android ASR-head evidence, with no accuracy claim."""

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WAV = ROOT / ".local/androidTestAssets/nemotron-bench/natural-long-ru_000010.wav"
SHA = "e9933e55693151a6f2c5d0f34188348d62053b66a70d9dad0dd25ffd3a408df5"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("a0", type=Path)
    parser.add_argument("a3", type=Path)
    args = parser.parse_args()
    assert hashlib.sha256(WAV.read_bytes()).hexdigest() == SHA
    a0 = json.loads(args.a0.read_text(encoding="utf-8-sig"))
    a3 = json.loads(args.a3.read_text(encoding="utf-8-sig"))
    assert a0["head"] == "a0" and a3["head"] == "a3"
    assert a0["audio_sha256"] == a3["audio_sha256"] == SHA
    assert a0["audio_ms"] == a3["audio_ms"] == 1_200_000
    assert a0["source"] == a3["source"]
    assert a0["merge400"]["windows"] == a3["merge400"]["windows"] == 429
    for item in (a0, a3):
        assert item["merge400"]["decoded_windows"] == 429
        assert item["merge400"]["segments"] > 0
        assert item["diar_peak_total_pss_kib"] > 0
        assert item["merge400"]["peak_app_pss_kib"] > 0
    before = a0["merge400"]["asr_wall_ms"]
    after = a3["merge400"]["asr_wall_ms"]
    print("A0/A3 ASR wall", before, after, "ms; A3 relative",
          round((after / before - 1) * 100, 2), "%")
    print("A0/A3 ASR load", a0["merge400"]["asr_load_ms"],
          a3["merge400"]["asr_load_ms"], "ms")
    print("A0/A3 transcript segments", a0["merge400"]["segments"],
          a3["merge400"]["segments"])
    print("WER/cpWER/DER NOT_SCORED: no independent reference")


if __name__ == "__main__":
    main()
