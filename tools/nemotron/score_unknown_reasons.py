"""Check aggregate attribution diagnostics from the natural-call Android probe."""

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WAV = ROOT / ".local/androidTestAssets/nemotron-bench/natural-long-ru_000010.wav"
SHA = "e9933e55693151a6f2c5d0f34188348d62053b66a70d9dad0dd25ffd3a408df5"
REASONS = ("no_turn", "overlap", "ineligible_turn", "low_coverage_or_margin")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    assert hashlib.sha256(WAV.read_bytes()).hexdigest() == SHA
    evidence = json.loads(args.evidence.read_text(encoding="utf-8-sig"))
    assert evidence["audio_sha256"] == SHA and evidence["audio_ms"] == 1_200_000
    for mode in ("pad150", "merge400"):
        data = evidence[mode]
        reasons = data["unknown_reasons"]
        assert sum(reasons[name] for name in REASONS) == (
            data["segments"] - data["attributed_segments"])
        assert 0 <= reasons["overlap_at_most_100ms"] <= reasons["overlap"]
        assert 0 <= data["unattributed_words"] <= data["word_count"]
        print(mode, "segments", data["segments"], "unknown", sum(reasons[name] for name in REASONS),
              "reasons", reasons, "unknown words", data["unattributed_words"],
              "/", data["word_count"])
    print("WER/cpWER/DER NOT_SCORED: no independent reference")


if __name__ == "__main__":
    main()
