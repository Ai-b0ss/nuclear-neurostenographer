"""Score opt-in Android ASR head probe against independent local references.

Usage: python tools/nemotron/score_asr_head_probe.py EVIDENCE.json
The WAVs and references live under ignored .local/ benchmark fixtures.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from score_transcript import evaluate  # noqa: E402


def main() -> None:
    evidence = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    refs = {
        "aba": ROOT / ".local/dialogue-benchmark/reference.json",
        "holdout": ROOT / ".local/dialogue-holdout/reference.json",
    }
    refs.update({
        name: ROOT / f".local/ivkond-independent/{name}.ref.json"
        for name in ("ivkond-2clean", "ivkond-2overlap", "ivkond-3overlap", "ivkond-4overlap")
    })
    refs.update({f"acted-holdout-{index}": ROOT / f".local/asr-independent-holdout/acted-holdout-{index}.ref.json"
                 for index in range(4)})
    suite = evidence["runs"][0].get("suite", "nemotron-bench")
    expected = ({"aba", "holdout", "ivkond-2clean", "ivkond-2overlap",
                 "ivkond-3overlap", "ivkond-4overlap"} if suite == "nemotron-bench"
                else {f"acted-holdout-{index}" for index in range(4)})
    rows = []
    for run in evidence["runs"]:
        assert run.get("suite", "nemotron-bench") == suite and run["case"] in expected
        ref = json.loads(refs[run["case"]].read_text(encoding="utf-8"))
        wav = ROOT / f".local/androidTestAssets/{suite}" / f'{run["case"]}.wav'
        sha = hashlib.sha256(wav.read_bytes()).hexdigest()
        assert sha == run["audio_sha256"] == ref["audio_sha256"]
        hyp = {"audio_sha256": sha, "audio_duration_ms": run["audio_ms"],
               "segments": run["segments"]}
        score = evaluate(ref, hyp)
        row = {"case": run["case"], "backend": run["backend"], "head": run["head"],
               "wer": score["wer"], "cpwer": score["cpwer"],
               "asr_wall_ms": run["asr_wall_ms"], "asr_load_ms": run["asr_load_ms"],
               "asr_decode_ms": run["asr_decode_ms"],
               "peak_app_pss_kb": run.get("peak_app_pss_kb")}
        rows.append(row)
        print(row["case"], row["backend"], row["head"],
              f'WER {row["wer"]["errors"]}/{row["wer"]["reference_words"]}',
              f'cpWER {row["cpwer"].get("errors")}/{row["cpwer"].get("reference_words")}',
              f'ASR {row["asr_wall_ms"]} ms')
    for backend in ("c0", "c2"):
        for head in sorted({row["head"] for row in rows}):
            subset = [row for row in rows if row["backend"] == backend and row["head"] == head]
            assert len(subset) == len(expected)
            print("TOTAL", backend, head,
                  "WER", sum(row["wer"]["errors"] for row in subset), "/",
                  sum(row["wer"]["reference_words"] for row in subset),
                  "ASR", sum(row["asr_wall_ms"] for row in subset), "ms",
                  "max app PSS", max((row["peak_app_pss_kb"] or 0) for row in subset), "KiB")


if __name__ == "__main__":
    main()
