"""Compare fixed C2 boundary padding against base ASR on frozen Russian text cases."""

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from score_transcript import evaluate  # noqa: E402


def reference_path(suite, case):
    if suite == "asr-holdout":
        return ROOT / f".local/asr-independent-holdout/{case}.ref.json"
    if case.startswith("ivkond-"):
        return ROOT / f".local/ivkond-independent/{case}.ref.json"
    if case == "aba":
        return ROOT / ".local/dialogue-benchmark/reference.json"
    if case == "holdout":
        return ROOT / ".local/dialogue-holdout/reference.json"
    raise ValueError(case)


def main():
    runs = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))["runs"]
    modes = tuple(dict.fromkeys(r["mode"] for r in runs))
    baseline = "base" if "base" in modes else "pad150"
    assert baseline in modes
    assert len(runs) == 10 * len(modes)
    assert len({(r["suite"], r["case"], r["mode"]) for r in runs}) == len(runs)
    assert {r["case"] for r in runs} == {"aba", "holdout", "ivkond-2clean", "ivkond-2overlap",
                                         "ivkond-3overlap", "ivkond-4overlap",
                                         *(f"acted-holdout-{i}" for i in range(4))}
    totals = {mode: {"wer_errors": 0, "wer_words": 0, "cpwer_errors": 0,
                     "cpwer_words": 0, "asr_ms": 0} for mode in modes}
    scores = {}
    for run in runs:
        suite, case, mode = run["suite"], run["case"], run["mode"]
        assert mode in totals
        reference = json.loads(reference_path(suite, case).read_text(encoding="utf-8"))
        wav = ROOT / f".local/androidTestAssets/{suite}/{case}.wav"
        sha = hashlib.sha256(wav.read_bytes()).hexdigest()
        assert sha == run["audio_sha256"] == reference["audio_sha256"]
        score = evaluate(reference, {"audio_sha256": sha, "audio_duration_ms": run["audio_ms"],
                                     "segments": run["segments"]})
        scores[(case, mode)] = score
        t = totals[mode]
        t["wer_errors"] += score["wer"]["errors"]
        t["wer_words"] += score["wer"]["reference_words"]
        if score["cpwer"].get("status") == "SCORED":
            t["cpwer_errors"] += score["cpwer"]["errors"]
            t["cpwer_words"] += score["cpwer"]["reference_words"]
        t["asr_ms"] += run["asr_load_ms"] + run["asr_decode_ms"]
        print(case, mode, "WER", score["wer"]["errors"], "/", score["wer"]["reference_words"],
              "cpWER", score["cpwer"].get("errors"), "/", score["cpwer"].get("reference_words"))
    for mode, t in totals.items():
        comparable = [case for case in {r["case"] for r in runs}
                      if scores[(case, baseline)]["cpwer"].get("status") == "SCORED"
                      and scores[(case, mode)]["cpwer"].get("status") == "SCORED"]
        common_base = sum(scores[(case, baseline)]["cpwer"]["errors"] for case in comparable)
        common_mode = sum(scores[(case, mode)]["cpwer"]["errors"] for case in comparable)
        common_words = sum(scores[(case, mode)]["cpwer"]["reference_words"] for case in comparable)
        print("TOTAL", mode, "WER", t["wer_errors"], "/", t["wer_words"],
              "scored_cpWER", t["cpwer_errors"], "/", t["cpwer_words"],
              f"common_cpWER_{baseline}_to_mode", f"{common_base}/{common_words}", "to", f"{common_mode}/{common_words}",
              "ASR_ms", t["asr_ms"])


if __name__ == "__main__":
    main()
