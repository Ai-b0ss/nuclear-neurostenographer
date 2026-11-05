"""Score frozen Golos farfield Android ASR runs; no diarization claim."""

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from score_transcript import edit_counts, words  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    evidence = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    lock = json.loads((ROOT / "tools/fixtures/golos-farfield-android-lock.json")
                      .read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in lock["cases"]}
    assert len(cases) == 30
    runs = evidence["runs"]
    assert len({(r["case"], r["backend"], r["head"]) for r in runs}) == len(runs)
    totals = {}
    for run in runs:
        assert run["suite"] == "golos-farfield" and run["case"] in cases
        case = cases[run["case"]]
        wav = ROOT / ".local/androidTestAssets/golos-farfield" / f'{run["case"]}.wav'
        ref = ROOT / ".local/golos-farfield-refs" / f'{run["case"]}.json'
        assert sha(wav) == case["wav_sha256"] == run["audio_sha256"]
        assert sha(ref) == case["reference_sha256"]
        reference = json.loads(ref.read_text(encoding="utf-8"))
        assert reference["id"] == case["source_id"]
        text = " ".join(s["text"] for s in sorted(run["segments"],
                       key=lambda s: (s["start_ms"], s["end_ms"])))
        score = edit_counts(words(reference["text"]), words(text))
        group = totals.setdefault((run["backend"], run["head"]),
                                  {"errors": 0, "words": 0, "wall_ms": 0,
                                   "max_pss_kb": 0, "cases": 0})
        group["errors"] += score["errors"]
        group["words"] += score["reference_words"]
        group["wall_ms"] += run["asr_wall_ms"]
        group["max_pss_kb"] = max(group["max_pss_kb"], run["peak_app_pss_kb"])
        group["cases"] += 1
        print(run["case"], run["backend"], run["head"],
              f'{score["errors"]}/{score["reference_words"]}',
              f'ASR {run["asr_wall_ms"]} ms', "windows", run["decoded_windows"])
    for (backend, head), group in sorted(totals.items()):
        assert group["cases"] == len(cases)
        print("TOTAL", backend, head, group)


if __name__ == "__main__":
    main()
