"""Score the fixed Android C0 threshold sweep against frozen acted references."""

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from score_transcript import evaluate  # noqa: E402


def main() -> None:
    evidence = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    for run in evidence["runs"]:
        case = run["case"]
        suite = run.get("suite", "asr-holdout")
        assert suite in ("asr-holdout", "nemotron-bench")
        ref_path = (ROOT / f".local/asr-independent-holdout/{case}.ref.json" if suite == "asr-holdout"
                    else ROOT / f".local/ivkond-independent/{case}.ref.json" if case.startswith("ivkond-")
                    else ROOT / (".local/dialogue-benchmark/reference.json" if case == "aba"
                                 else ".local/dialogue-holdout/reference.json"))
        ref = json.loads(ref_path.read_text(encoding="utf-8"))
        wav = ROOT / f".local/androidTestAssets/{suite}/{case}.wav"
        sha = hashlib.sha256(wav.read_bytes()).hexdigest()
        assert sha == run["audio_sha256"] == ref["audio_sha256"]
        score = evaluate(ref, {"audio_sha256": sha, "audio_duration_ms": run["audio_ms"],
                               "segments": run["segments"]})
        print(case, run["threshold"], "speakers", run["speaker_count"],
              "WER", score["wer"]["errors"], "/", score["wer"]["reference_words"],
              "cpWER", score["cpwer"].get("errors"), "/", score["cpwer"].get("reference_words"),
              "diar_ms", run["diar_process_ms"])


if __name__ == "__main__":
    main()
