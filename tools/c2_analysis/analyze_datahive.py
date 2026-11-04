"""Why does C2 fail on some DataHive calls? Separates reference defects from model errors, from signals only.

python tools/c2_analysis/analyze_datahive.py --root ROOT --ort-python PY --out docs/evidence/nemotron-android/datahive-error-analysis.json
Uses the frozen corpus, the original stereo MP3 and the stored C0/C2 outputs. Nothing here is human listening.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
import soundfile as sf

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from score_transcript import der  # noqa: E402

RATE = 16000
FRAME = 320  # 20 ms


def turns_tsv(path):
    rows = [line.split("\t") for line in Path(path).read_text(encoding="ascii").splitlines() if line.strip()]
    return [{"start_ms": int(a), "end_ms": int(b), "speaker_id": None if int(c) < 0 else f"h{c}"} for a, b, c in rows]


def frames_of(turns, count, speaker):
    out = np.zeros(count, dtype=bool)
    for t in turns:
        if t["speaker_id"] == speaker:
            out[t["start_ms"] // 20:t["end_ms"] // 20] = True
    return out


def stereo(ffmpeg, mp3):
    data = subprocess.run([ffmpeg, "-v", "error", "-ss", "30", "-t", "120", "-i", str(mp3), "-ar", str(RATE), "-f", "f32le", "-"],
                          capture_output=True, check=True).stdout
    return np.frombuffer(data, dtype=np.float32).reshape(-1, 2)


def level_db(x):
    count = len(x) // FRAME
    return 20 * np.log10(np.sqrt(np.mean(x[:count * FRAME].reshape(count, FRAME) ** 2, axis=1)) + 1e-9)


def pitch(x, voiced):
    """Median F0 in Hz over voiced 40 ms windows, autocorrelation between 70 and 400 Hz."""
    values = []
    window = 640
    for i in np.flatnonzero(voiced)[::5]:
        start = i * FRAME
        seg = x[start:start + window]
        if len(seg) < window:
            continue
        seg = seg - seg.mean()
        ac = np.correlate(seg, seg, mode="full")[window - 1:]
        lo, hi = RATE // 400, RATE // 70
        lag = lo + int(np.argmax(ac[lo:hi]))
        if ac[0] > 0 and ac[lag] / ac[0] > 0.5:
            values.append(RATE / lag)
    return (float(np.median(values)), len(values)) if values else (None, 0)


def mapping_report(reference, hypothesis, duration):
    """Cluster x reference speaker overlap, and DER if every cluster may map to its majority speaker (split-tolerant)."""
    speakers = sorted({t["speaker_id"] for t in reference})
    clusters = sorted({t["speaker_id"] for t in hypothesis if t["speaker_id"]})
    count = duration // 20
    ref = {s: frames_of(reference, count, s) for s in speakers}
    table = {}
    for c in clusters:
        h = frames_of(hypothesis, count, c)
        table[c] = {s: int((h & ref[s]).sum() * 20) for s in speakers} | {"none_ms": int((h & ~np.any(list(ref.values()), axis=0)).sum() * 20), "total_ms": int(h.sum() * 20)}
    majority = {c: max(speakers, key=lambda s: table[c][s]) for c in clusters}
    merged = [{"start_ms": t["start_ms"], "end_ms": t["end_ms"], "speaker_id": majority.get(t["speaker_id"])} for t in hypothesis]
    return table, majority, der(reference, merged, duration, 250, False)


def run_c2(ort_python, models, wav, out_tsv, out_meta):
    subprocess.run([ort_python, "-I", str(REPO / "tools/diar_bench/run_c1.py"), str(models / "nemotron"), "model.int8.onnx", str(wav), str(out_tsv), str(out_meta)], check=True)
    return turns_tsv(out_tsv)


def analyze(root, case, meta, ort_python, ffmpeg, scratch):
    corpus = root / "data/corpus"
    reference = json.loads((corpus / f"{case}.ref.json").read_text(encoding="utf-8"))["diarization"]
    duration = json.loads((corpus / f"{case}.ref.json").read_text(encoding="utf-8"))["audio_duration_ms"]
    name = case.removeprefix("datahive-")
    channels = stereo(ffmpeg, root / "data/raw/datahive" / f"{name}.mp3")
    levels = [level_db(channels[:, i]) for i in range(2)]
    count = min(len(levels[0]), duration // 20)
    caller, callee = frames_of(reference, count, "caller"), frames_of(reference, count, "callee")
    report = {"case": case, "metadata": {k: meta[k] for k in ("turns_per_minute", "speech_balance_percent", "overlap_percent", "turn_taking_gap_ms")}}
    # Reference check: a speaker label on one channel while that channel is quiet, or the other channel's voice leaking in.
    only_caller, only_callee = caller & ~callee, callee & ~caller
    report["reference"] = {
        "caller_ms": int(caller.sum() * 20), "callee_ms": int(callee.sum() * 20), "both_ms": int((caller & callee).sum() * 20),
        "leak_db_callee_channel_when_only_caller": float(np.median(levels[1][:count][only_caller]) - np.median(levels[0][:count][only_caller])) if only_caller.any() else None,
        "leak_db_caller_channel_when_only_callee": float(np.median(levels[0][:count][only_callee]) - np.median(levels[1][:count][only_callee])) if only_callee.any() else None,
        "envelope_correlation": float(np.corrcoef(levels[0][:count], levels[1][:count])[0, 1]),
    }
    report["pitch_hz"] = {}
    for index, label, voiced in ((0, "caller", only_caller), (1, "callee", only_callee)):
        f0, n = pitch(channels[:, index], voiced)
        report["pitch_hz"][label] = {"median": f0, "windows": n}
    for system in ("C0", "C2"):
        hypothesis = turns_tsv(root / "results-v2" / system / f"{case}.tsv")
        scored = der(reference, hypothesis, duration, 250, False)
        table, majority, merged = mapping_report(reference, hypothesis, duration)
        report[system] = {"der": scored["rate"], "miss": scored["miss_ms"], "false_alarm": scored["false_alarm_ms"], "confusion": scored["confusion_ms"],
                          "reference_ms": scored["reference_speaker_ms"], "clusters": table, "majority_map": majority,
                          "der_if_clusters_merged_by_majority": merged["rate"], "confusion_if_merged": merged["confusion_ms"]}
    # Each channel alone holds one person. More than one C2 cluster there means the model splits one voice.
    per_channel = {}
    for index, label in ((0, "caller"), (1, "callee")):
        wav = scratch / f"{name}-{label}.wav"
        sf.write(wav, channels[:, index], RATE, subtype="PCM_16")
        turns = run_c2(ort_python, root / "data/models", wav, scratch / f"{name}-{label}.tsv", scratch / f"{name}-{label}.json")
        totals = {}
        for t in turns:
            totals[t["speaker_id"]] = totals.get(t["speaker_id"], 0) + t["end_ms"] - t["start_ms"]
        per_channel[label] = {"clusters": len(totals), "cluster_ms": totals}
    report["c2_single_channel"] = per_channel
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--ort-python", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    meta = {json.loads(l)["file_name"].removesuffix(".mp3"): json.loads(l)
            for l in (args.root / "data/raw/datahive/metadata.jsonl").read_text(encoding="utf-8").splitlines() if l}
    reports = []
    with tempfile.TemporaryDirectory() as folder:
        for name in sorted(meta):
            reports.append(analyze(args.root, f"datahive-{name}", meta[name], args.ort_python, args.ffmpeg, Path(folder)))
            r = reports[-1]
            print(name, f"C2 {100 * r['C2']['der']:.1f} merged {100 * r['C2']['der_if_clusters_merged_by_majority']:.1f}",
                  "single-channel clusters", r["c2_single_channel"]["caller"]["clusters"], r["c2_single_channel"]["callee"]["clusters"],
                  "f0", r["pitch_hz"]["caller"]["median"], r["pitch_hz"]["callee"]["median"], "leak", r["reference"]["leak_db_callee_channel_when_only_caller"], flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"scope": "Signal analysis, no human listening", "recordings": reports}, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
