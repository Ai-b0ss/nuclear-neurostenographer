"""Score the pinned standalone Android MOSS Q4 probe against manual RINCO text."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from score_transcript import edit_counts, words  # noqa: E402
from rinco.provision import OUTPUT_SHA256  # noqa: E402

MODEL_SHA256 = "4e3020379ff592bbb22a4e3d47a7cd6709951cc5d451c561b69df955b5f0a220"
CASES = ("rinco-q144", "rinco-i1321")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def score(reference: list[str], texts: list[str]) -> dict:
    return edit_counts(words(" ".join(reference)), words(" ".join(texts)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe-dir", type=Path, default=ROOT / ".local/moss-audio-cpp")
    args = parser.parse_args()
    model = args.probe_dir / "MOSS-Transcribe-Diarize-GGUF/moss-transcribe-diarize-q4_k.gguf"
    if digest(model) != MODEL_SHA256:
        raise ValueError("MOSS Q4 model hash mismatch")
    baseline = json.loads((ROOT / ".local/rinco-source/asr-head-product-rinco-evidence.json")
                          .read_text(encoding="utf-8-sig"))["runs"]
    for case in CASES:
        reference = json.loads((ROOT / f".local/rinco-refs/{case}.json").read_text(encoding="utf-8"))
        wav = ROOT / f".local/androidTestAssets/rinco/{case}.wav"
        if digest(wav) != OUTPUT_SHA256[case] or reference["audio_sha256"] != OUTPUT_SHA256[case]:
            raise ValueError(f"RINCO audio/reference identity mismatch: {case}")
        ref_texts = [s["text"] for s in reference["text_segments"]]
        for head in ("a0", "a3"):
            runs = [r for r in baseline if r["case"] == case and r["head"] == head]
            if len(runs) != 1 or runs[0]["audio_sha256"] != OUTPUT_SHA256[case]:
                raise ValueError(f"Missing baseline: {case}/{head}")
            result = score(ref_texts, [s["text"] for s in runs[0]["segments"]])
            print(case, head, f"{result['errors']}/{result['reference_words']}",
                  "wall_ms", runs[0]["asr_wall_ms"])
        names = (case.removeprefix("rinco-") + ".segments.json",)
        if case == "rinco-i1321":
            names += ("i1321-tuned.segments.json",)
        for name in names:
            segments = json.loads((args.probe_dir / name).read_text(encoding="utf-8"))
            if not segments or any(s["start_sample"] < 0 or
                                   s["end_sample"] <= s["start_sample"] or
                                   s["end_sample"] > reference["audio_duration_ms"] * 16 + 16 or
                                   not s["text"].strip() for s in segments):
                raise ValueError(f"Invalid MOSS segment: {name}")
            result = score(ref_texts, [s["text"] for s in segments])
            print(case, name, f"{result['errors']}/{result['reference_words']}")


if __name__ == "__main__":
    main()
