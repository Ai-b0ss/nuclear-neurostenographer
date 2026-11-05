"""Score paired A0/A3 Android WER against frozen RINCO manual ELAN Text tiers."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from score_transcript import edit_counts, words  # noqa: E402
from rinco.provision import CASES, OUTPUT_SHA256, SOURCE_SHA256  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    runs = json.loads(args.evidence.read_text(encoding="utf-8-sig"))["runs"]
    expected = {(case, head) for case in CASES for head in ("a0", "a3")}
    if {(r["case"], r["head"]) for r in runs} != expected or len(runs) != len(expected):
        raise ValueError("Missing, unexpected, or duplicate RINCO case/head")
    totals = {head: {"errors": 0, "words": 0, "asr_wall_ms": 0, "max_pss_kb": 0}
              for head in ("a0", "a3")}
    for run in runs:
        if run["suite"] != "rinco" or run["backend"] != "c2":
            raise ValueError("Unexpected Android policy")
        case = run["case"]
        ref = json.loads((ROOT / f".local/rinco-refs/{case}.json").read_text(encoding="utf-8"))
        wav = ROOT / f".local/androidTestAssets/rinco/{case}.wav"
        audio_hash = hashlib.sha256(wav.read_bytes()).hexdigest()
        if (audio_hash != OUTPUT_SHA256[case] or audio_hash != ref["audio_sha256"] or
                audio_hash != run["audio_sha256"] or
                ref["audio_duration_ms"] != run["audio_ms"] or
                ref["source_archive_sha256"] != SOURCE_SHA256 or
                ref["source_wav_sha256"] != CASES[case][1] or
                ref["source_eaf_sha256"] != CASES[case][2]):
            raise ValueError("RINCO source or reference identity mismatch")
        reference = " ".join(s["text"] for s in ref["text_segments"])
        hypothesis = " ".join(s["text"] for s in sorted(
            run["segments"], key=lambda s: (s["start_ms"], s["end_ms"])))
        score = edit_counts(words(reference), words(hypothesis))
        total = totals[run["head"]]
        total["errors"] += score["errors"]
        total["words"] += score["reference_words"]
        total["asr_wall_ms"] += run["asr_wall_ms"]
        total["max_pss_kb"] = max(total["max_pss_kb"], run["peak_app_pss_kb"])
        print(case, run["head"], f"{score['errors']}/{score['reference_words']}",
              "S/D/I", score["substitutions"], score["deletions"], score["insertions"],
              "ASR_ms", run["asr_wall_ms"])
    for head, total in totals.items():
        print("TOTAL", head, total, "WER", f"{total['errors'] / total['words']:.3%}")


if __name__ == "__main__":
    main()
