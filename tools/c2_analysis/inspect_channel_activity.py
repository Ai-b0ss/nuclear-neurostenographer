"""Second-by-second view of one DataHive call: channel levels, voicing, VAD reference and C2 clusters.

python tools/c2_analysis/inspect_channel_activity.py --root ROOT --case ru_000001 --out FILE.json
Answers: is there sound on a channel that the per-channel VAD reference calls silence, and what C2 does there.
Signal statistics only; nobody listened to the audio.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_datahive import FRAME, RATE, frames_of, level_db, stereo, turns_tsv  # noqa: E402


def voicing(x, count):
    """Per 20 ms frame: normalized autocorrelation peak in 70-400 Hz over a 40 ms window (0 = noise, near 1 = voiced)."""
    out = np.zeros(count)
    window = 640
    lo, hi = RATE // 400, RATE // 70
    for i in range(count):
        seg = x[i * FRAME:i * FRAME + window]
        if len(seg) < window:
            break
        seg = seg - seg.mean()
        energy = float(seg @ seg)
        if energy < 1e-8:
            continue
        ac = np.correlate(seg, seg, mode="full")[window - 1:]
        out[i] = ac[lo:hi].max() / ac[0]
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    case = f"datahive-{args.case}"
    reference = json.loads((args.root / "data/corpus" / f"{case}.ref.json").read_text(encoding="utf-8"))
    channels = stereo(args.ffmpeg, args.root / "data/raw/datahive" / f"{args.case}.mp3")
    count = reference["audio_duration_ms"] // 20
    levels = [level_db(channels[:, i])[:count] for i in range(2)]
    voiced = [voicing(channels[:, i], count) for i in range(2)]
    caller = frames_of(reference["diarization"], count, "caller")
    callee = frames_of(reference["diarization"], count, "callee")
    c2 = turns_tsv(args.root / "results-v2/C2" / f"{case}.tsv")
    clusters = sorted({t["speaker_id"] for t in c2 if t["speaker_id"]})
    active = {c: frames_of(c2, count, c) for c in clusters}

    def summary(mask, channel):
        if not mask.any():
            return None
        return {"frames": int(mask.sum()), "median_dbfs": round(float(np.median(levels[channel][mask])), 1),
                "voiced_share": round(float((voiced[channel][mask] > 0.5).mean()), 3)}

    quiet = ~caller & ~callee
    report = {"case": case, "scope": "Signal statistics only; no human listening",
              "callee_channel": {"callee_labelled": summary(callee, 1), "only_caller_labelled": summary(caller & ~callee, 1), "nobody_labelled": summary(quiet, 1)},
              "caller_channel": {"caller_labelled": summary(caller, 0), "only_callee_labelled": summary(callee & ~caller, 0), "nobody_labelled": summary(quiet, 0)}}
    # Sound that the reference calls silence: loud and voiced on a channel whose speaker is not labelled.
    floor = [float(np.percentile(levels[i], 10)) for i in range(2)]
    unlabelled = [(levels[i] > floor[i] + 20) & (voiced[i] > 0.5) & ~(caller if i == 0 else callee) for i in range(2)]
    report["voiced_unlabelled_ms"] = {"caller_channel": int(unlabelled[0].sum() * 20), "callee_channel": int(unlabelled[1].sum() * 20)}
    report["c2_on_unlabelled_callee_channel_sound"] = {c: int((active[c] & unlabelled[1]).sum() * 20) for c in clusters}
    # Where C2 disagrees with the reference: how loud and how voiced is the labelled speaker's own channel there?
    any_c2 = np.any([active[c] for c in clusters], axis=0) if clusters else np.zeros(count, dtype=bool)
    missed = {"caller": caller & ~any_c2, "callee": callee & ~any_c2}
    report["c2_missed_reference_speech"] = {
        label: None if not mask.any() else {
            "ms": int(mask.sum() * 20), "own_channel_median_dbfs": round(float(np.median(levels[i][mask])), 1),
            "own_channel_voiced_share": round(float((voiced[i][mask] > 0.5).mean()), 3),
            "share_below_minus_60_dbfs": round(float((levels[i][mask] < -60).mean()), 3)}
        for i, (label, mask) in enumerate(missed.items())}
    extra = any_c2 & ~caller & ~callee
    report["c2_speech_where_reference_has_none"] = None if not extra.any() else {
        "ms": int(extra.sum() * 20),
        "loudest_channel_median_dbfs": round(float(np.median(np.maximum(levels[0], levels[1])[extra])), 1),
        "voiced_share_either_channel": round(float(((voiced[0][extra] > 0.5) | (voiced[1][extra] > 0.5)).mean()), 3)}
    seconds = []
    for s in range(count // 50):
        span = slice(s * 50, (s + 1) * 50)
        seconds.append({"t_s": s, "caller_db": round(float(levels[0][span].max()), 1), "callee_db": round(float(levels[1][span].max()), 1),
                        "ref": "".join(x for x, m in (("A", caller), ("B", callee)) if m[span].mean() > 0.3) or "-",
                        "c2": "".join(c[-1] for c in clusters if active[c][span].mean() > 0.3) or "-",
                        "unlabelled_voiced_callee": round(float(unlabelled[1][span].mean()), 2)})
    report["per_second"] = seconds
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "per_second"}, indent=1))
    for row in seconds:
        if row["unlabelled_voiced_callee"] > 0.2 or row["ref"] != "-":
            pass
    bad = [r for r in seconds if r["unlabelled_voiced_callee"] > 0.2]
    print("seconds with unlabelled voiced sound on the callee channel:", len(bad), [r["t_s"] for r in bad][:60])


if __name__ == "__main__":
    main()
