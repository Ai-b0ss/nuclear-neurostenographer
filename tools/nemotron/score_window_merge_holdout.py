"""Score independently frozen acted Russian C2 window-merge holdout."""

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from score_transcript import evaluate  # noqa: E402


def main():
    evidence = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))["runs"]
    lock = json.loads((ROOT / "tools/fixtures/dialogs-ru-window-merge-holdout-lock.json").read_text(encoding="utf-8"))
    cases = {c["id"]: c for c in lock["cases"]}
    assert len(evidence) == 8
    assert {(r["case"], r["mode"]) for r in evidence} == {
        (case, mode) for case in cases for mode in ("pad150", "merge400")}
    totals = {mode: {"wer_errors": 0, "wer_words": 0, "cpwer_errors": 0,
                     "cpwer_words": 0, "asr_ms": 0, "windows": 0}
              for mode in ("pad150", "merge400")}
    for run in evidence:
        case, mode = run["case"], run["mode"]
        assert run["suite"] == "window-merge-holdout"
        wav = ROOT / f".local/androidTestAssets/window-merge-holdout/{case}.wav"
        ref_file = ROOT / f".local/window-merge-holdout-refs/{case}.ref.json"
        sha = hashlib.sha256(wav.read_bytes()).hexdigest()
        assert sha == run["audio_sha256"] == cases[case]["audio_sha256"]
        assert hashlib.sha256(ref_file.read_bytes()).hexdigest() == cases[case]["reference_sha256"]
        reference = json.loads(ref_file.read_text(encoding="utf-8"))
        report = evaluate(reference, {"audio_sha256": sha, "audio_duration_ms": run["audio_ms"],
                                      "segments": run["segments"]})
        assert report["wer"].get("status") == "SCORED"
        assert report["cpwer"].get("status") == "SCORED", "Unknown speaker words invalidate strict cpWER"
        t = totals[mode]
        t["wer_errors"] += report["wer"]["errors"]
        t["wer_words"] += report["wer"]["reference_words"]
        t["cpwer_errors"] += report["cpwer"]["errors"]
        t["cpwer_words"] += report["cpwer"]["reference_words"]
        t["asr_ms"] += run["asr_load_ms"] + run["asr_decode_ms"]
        t["windows"] += run["decoded_windows"]
        print(case, mode, "WER", report["wer"]["errors"], "/", report["wer"]["reference_words"],
              "cpWER", report["cpwer"].get("errors"), "/", report["cpwer"].get("reference_words"),
              "windows", run["decoded_windows"])
    for mode, t in totals.items():
        print("TOTAL", mode, "WER", t["wer_errors"], "/", t["wer_words"],
              "scored_cpWER", t["cpwer_errors"], "/", t["cpwer_words"],
              "ASR_ms", t["asr_ms"], "windows", t["windows"])


if __name__ == "__main__":
    main()
