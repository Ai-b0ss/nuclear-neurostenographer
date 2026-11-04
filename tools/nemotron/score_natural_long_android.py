"""Verify paired 20-minute natural-call Android evidence; no accuracy score."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WAV = ROOT / ".local/androidTestAssets/nemotron-bench/natural-long-ru_000010.wav"
SHA = "e9933e55693151a6f2c5d0f34188348d62053b66a70d9dad0dd25ffd3a408df5"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paired", type=Path)
    parser.add_argument("product", type=Path)
    args = parser.parse_args()
    assert hashlib.sha256(WAV.read_bytes()).hexdigest() == SHA
    paired = json.loads(args.paired.read_text(encoding="utf-8-sig"))
    product = json.loads(args.product.read_text(encoding="utf-8-sig"))
    assert paired["audio_sha256"] == product["audio_sha256"] == SHA
    assert paired["audio_ms"] == product["audio_ms"] == 1_200_000
    assert paired["merge400"]["windows"] < paired["pad150"]["windows"]
    assert paired["merge400"]["segments"] == product["segments"]
    assert paired["merge400"]["attributed_segments"] == product["attributed_segments"]
    assert paired["merge400"]["text_sha256"] == product["text_sha256"]
    before, after = paired["pad150"]["asr_wall_ms"], paired["merge400"]["asr_wall_ms"]
    print("ASR windows", paired["pad150"]["windows"], "->", paired["merge400"]["windows"])
    print("ASR wall ms", before, "->", after, "difference", after - before,
          "relative", round((after / before - 1) * 100, 2), "%")
    print("product import+inference+export ms", product["total_with_export_ms"],
          "RTF", round(product["total_with_export_ms"] / 1_200_000, 4))
    print("product app peak PSS MiB", round(product["peak_app_pss_kib"] / 1024, 1))
    print("WER/cpWER/DER NOT_SCORED: no independent reference")


if __name__ == "__main__":
    main()
