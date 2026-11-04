"""Score debug-only oracle speaker-count probe on pinned Android recordings."""

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from score_transcript import evaluate  # noqa: E402


def reference_path(suite: str, case: str) -> Path:
    if suite == "asr-holdout":
        return ROOT / f".local/asr-independent-holdout/{case}.ref.json"
    if case.startswith("ivkond-"):
        return ROOT / f".local/ivkond-independent/{case}.ref.json"
    if case == "aba":
        return ROOT / ".local/dialogue-benchmark/reference.json"
    if case == "holdout":
        return ROOT / ".local/dialogue-holdout/reference.json"
    raise ValueError(case)


def main() -> None:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    rows = []
    for run in data["runs"]:
        suite, case = run["suite"], run["case"]
        ref = json.loads(reference_path(suite, case).read_text(encoding="utf-8"))
        wav = ROOT / f".local/androidTestAssets/{suite}/{case}.wav"
        sha = hashlib.sha256(wav.read_bytes()).hexdigest()
        assert sha == run["audio_sha256"] == ref["audio_sha256"]
        score = evaluate(ref, {"audio_sha256": sha, "audio_duration_ms": run["audio_ms"],
                               "segments": run["segments"]})
        rows.append((run, score))
        print(case, "known" if run["requested_speakers"] > 0 else "auto",
              "speakers", run["predicted_speakers"], "/", run["expected_speakers"],
              "WER", score["wer"]["errors"], "/", score["wer"]["reference_words"],
              "cpWER", score["cpwer"].get("errors"), "/", score["cpwer"].get("reference_words"))
    for mode in ("auto", "known"):
        chosen = [(run, score) for run, score in rows
                  if (run["requested_speakers"] > 0) == (mode == "known")]
        print("TOTAL", mode, "WER", sum(score["wer"]["errors"] for _, score in chosen), "/",
              sum(score["wer"]["reference_words"] for _, score in chosen),
              "speaker_count_correct", sum(run["predicted_speakers"] == run["expected_speakers"]
                                           for run, _ in chosen), "/", len(chosen),
              "scored_cpWER", sum(score["cpwer"]["errors"] for _, score in chosen
                                   if score["cpwer"].get("status") == "SCORED"), "/",
              sum(score["cpwer"]["reference_words"] for _, score in chosen
                  if score["cpwer"].get("status") == "SCORED"))


if __name__ == "__main__":
    main()
