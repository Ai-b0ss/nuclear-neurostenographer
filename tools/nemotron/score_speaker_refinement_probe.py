"""Score a frozen speaker-refinement holdout without silently dropping unknowns.

Usage: python tools/nemotron/score_speaker_refinement_probe.py C2.json C0.json
"""

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from score_transcript import evaluate  # noqa: E402


def main() -> None:
    c2_runs = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))["runs"]
    c0_runs = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8-sig"))["runs"]
    lock = json.loads((ROOT / "tools/fixtures/dialogs-ru-speaker-refinement-holdout-lock.json")
                      .read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in lock["cases"]}
    assert len(cases) == 4
    c2 = {run["case"]: run for run in c2_runs}
    c0 = {run["case"]: run for run in c0_runs if abs(run["threshold"] - 0.65) < 0.001}
    assert set(c2) == set(c0) == set(cases) and len(c2_runs) == 4 and len(c0_runs) == 16
    totals = {"c2": defaultdict(int), "selected": defaultdict(int)}
    for name, frozen in cases.items():
        wav = ROOT / f".local/androidTestAssets/speaker-refinement-holdout/{name}.wav"
        ref_path = ROOT / f".local/speaker-refinement-holdout-refs/{name}.ref.json"
        ref = json.loads(ref_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(wav.read_bytes()).hexdigest()
        assert digest == frozen["audio_sha256"] == ref["audio_sha256"]
        assert hashlib.sha256(ref_path.read_bytes()).hexdigest() == frozen["reference_sha256"]
        base, alternative = c2[name], c0[name]
        assert base["suite"] == alternative["suite"] == "speaker-refinement-holdout"
        assert base["backend"] == "c2" and base["head"] == "a0"
        assert base["audio_sha256"] == alternative["audio_sha256"] == digest
        durations = defaultdict(int)
        for turn in alternative["turns"]:
            durations[turn["speaker_id"]] += turn["end_ms"] - turn["start_ms"]
        assert durations and len(durations) == alternative["speaker_count"]
        choose_c0 = (base["speaker_count"] == 2 and alternative["speaker_count"] == 3
                     and min(durations.values()) >= 1000)
        scores = {}
        for label, run in (("c2", base), ("selected", alternative if choose_c0 else base)):
            score = evaluate(ref, {"audio_sha256": digest,
                                   "audio_duration_ms": run["audio_ms"],
                                   "segments": run["segments"]})
            scores[label] = score
            total = totals[label]
            total["wer_errors"] += score["wer"]["errors"]
            total["wer_words"] += score["wer"]["reference_words"]
            if score["cpwer"]["status"] == "SCORED":
                total["cpwer_errors"] += score["cpwer"]["errors"]
                total["cpwer_words"] += score["cpwer"]["reference_words"]
            else:
                total["cpwer_not_scored"] += 1
        print(name, "switch_to_c0", choose_c0,
              "C2/C0_speakers", base["speaker_count"], alternative["speaker_count"],
              "C2_WER", scores["c2"]["wer"]["errors"],
              "selected_WER", scores["selected"]["wer"]["errors"],
              "C2_cpWER", scores["c2"]["cpwer"].get("errors", "NOT_SCORED"),
              "selected_cpWER", scores["selected"]["cpwer"].get("errors", "NOT_SCORED"))
    for label, total in totals.items():
        print(label, dict(total))


if __name__ == "__main__":
    main()
