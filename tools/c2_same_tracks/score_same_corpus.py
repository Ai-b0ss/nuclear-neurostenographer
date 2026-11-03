"""Score C0 and C2 on the same-recordings corpus. WER, cpWER, DER and the speaker measures are kept apart.

python tools/c2_same_tracks/score_same_corpus.py --corpus ROOT/data/same --results ROOT/results-same --evidence docs/evidence/c2-same-tracks

  WER / cpWER  tools/score_transcript.py on the app-format transcript (start, end, speaker, text), reference end times
               clamped to the audio as tools/score_clip_run.py does for the phone runs. Unattributed words make cpWER
               NOT_SCORED, never a silently matched speaker. Only sets with reference text.
  cpWER-U      Pessimistic companion: unattributed words are dropped from the hypothesis, so the reference words they
               cover count as deletions (an extra "unknown" speaker would be matched to a real one). Next to cpWER, never in its place.
  DER         realmix only, collar 250 ms, overlap scored, against the gated channel reference. Synthetic sets: NOT_SCORED.
  Attribution  NOT DER: on 10 ms frames where the reference has one speaker and the system one cluster, the share of
               frames whose cluster maps to that speaker under the best one-to-one mapping. Silence is left out.
  Split/merge  On the same frames: a reference speaker split if two or more clusters each hold >= 20% of its frames;
               a cluster merged if it holds two or more reference speakers with >= 20% of its frames each.
  A-B-A        score_bench.recurrence: reference turns >= 1 s; returns of a speaker must get the same dominant cluster,
               turns of different speakers different ones.
"""
import argparse
import json
from pathlib import Path
import random
import sys

import numpy as np
from scipy.optimize import linear_sum_assignment

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "diar_bench"))
from score_bench import read_turns, recurrence  # noqa: E402
from score_transcript import evaluate, validate_segments  # noqa: E402

FRAME_MS = 10
SHARE = 0.2
SYSTEMS = ("C0", "C2")


def clamp(reference):
    fixed = json.loads(json.dumps(reference))
    for key in ("text_segments", "diarization"):
        for s in fixed.get(key, []):
            s["end_ms"] = min(s["end_ms"], fixed["audio_duration_ms"])
            s["start_ms"] = min(s["start_ms"], s["end_ms"] - 1)
    return fixed


def der(reference, hypothesis, duration, collar_ms=0, skip_overlap=False):
    """tools/score_transcript.py der() with the optimal mapping found by the Hungarian method instead of its exhaustive
    search, which stops at 12 speakers (C0 finds up to 21 clusters on a 4-minute mix). Same regions, same rule, same value."""
    reference = validate_segments(reference, duration, reference=True)
    hypothesis = validate_segments(hypothesis, duration)
    collars = [(max(0, s[k] - collar_ms), min(duration, s[k] + collar_ms)) for s in reference for k in ("start_ms", "end_ms") if collar_ms]
    points = sorted({0, duration, *[s[k] for s in reference + hypothesis for k in ("start_ms", "end_ms")], *[x for c in collars for x in c]})
    regions = []
    for start, end in zip(points, points[1:]):
        if any(a <= start < b for a, b in collars):
            continue
        r = {s["speaker_id"] for s in reference if s["start_ms"] <= start < s["end_ms"]}
        h = {s["speaker_id"] for s in hypothesis if s["start_ms"] <= start < s["end_ms"]}
        if not (skip_overlap and len(r) > 1):
            regions.append((end - start, r, h))
    rn = sorted({s["speaker_id"] for s in reference})
    hn = sorted({s["speaker_id"] for s in hypothesis if s["speaker_id"] is not None})
    overlap = np.zeros((len(rn), len(hn)))
    for dt, r, h in regions:
        for who in r:
            for other in h:
                overlap[rn.index(who), hn.index(other)] += dt
    rows, cols = linear_sum_assignment(-overlap) if rn and hn else ([], [])
    mapping = {hn[j]: rn[i] for i, j in zip(rows, cols) if overlap[i, j] > 0}
    miss = fa = confusion = ref_ms = 0
    for dt, r, h in regions:
        correct = sum(1 for who in h if who in mapping and mapping[who] in r)
        miss += dt * max(len(r) - len(h), 0)
        fa += dt * max(len(h) - len(r), 0)
        confusion += dt * (min(len(r), len(h)) - correct)
        ref_ms += dt * len(r)
    return {"rate": (miss + fa + confusion) / ref_ms if ref_ms else None, "miss_ms": miss, "false_alarm_ms": fa,
            "confusion_ms": confusion, "reference_speaker_ms": ref_ms}


def frame_matrix(reference, turns, duration):
    """Counts of frames with exactly one reference speaker and exactly one cluster: rows speakers, columns clusters."""
    count = duration // FRAME_MS
    speakers = sorted({t["speaker_id"] for t in reference})
    clusters = sorted({c for _, _, c in turns if c >= 0})
    ref = np.zeros((len(speakers), count), dtype=bool)
    hyp = np.zeros((len(clusters), count), dtype=bool)
    for t in reference:
        ref[speakers.index(t["speaker_id"]), t["start_ms"] // FRAME_MS:t["end_ms"] // FRAME_MS] = True
    for a, b, c in turns:
        if c >= 0:
            hyp[clusters.index(c), a // FRAME_MS:b // FRAME_MS] = True
    usable = (ref.sum(0) == 1) & (hyp.sum(0) == 1)
    matrix = np.zeros((len(speakers), len(clusters)), dtype=int)
    if clusters:
        for i in range(len(speakers)):
            for j in range(len(clusters)):
                matrix[i, j] = int((ref[i] & hyp[j] & usable).sum())
    return speakers, clusters, matrix


def speaker_measures(reference, turns, duration):
    speakers, clusters, m = frame_matrix(reference, turns, duration)
    total = int(m.sum())
    rows, cols = linear_sum_assignment(-m) if clusters else ([], [])
    correct = int(sum(m[i, j] for i, j in zip(rows, cols)))
    split = [speakers[i] for i in range(len(speakers)) if m[i].sum() and (m[i] >= SHARE * m[i].sum()).sum() >= 2]
    merged = [f"h{clusters[j]}" for j in range(len(clusters)) if m[:, j].sum() and (m[:, j] >= SHARE * m[:, j].sum()).sum() >= 2]
    return {"frames": total, "attributed_correctly": correct, "attribution": round(correct / total, 4) if total else None,
            "split_speakers": split, "merged_clusters": merged}


def measure(case, reference, turns, segments):
    """Everything except timing, shared by host and phone runs. turns: (start, end, cluster); segments: app transcript or None."""
    duration = reference["audio_duration_ms"]
    row = {"hyp_speakers": len({c for _, _, c in turns if c >= 0}), "unknown_turns": sum(c < 0 for _, _, c in turns)}
    speaker_reference = reference.get("text_segments") or reference["diarization"]
    row["speaker"] = speaker_measures(speaker_reference, turns, duration)
    row["recurrence"] = recurrence(speaker_reference, turns)
    if case["set"] == "realmix":
        hypothesis = [{"start_ms": a, "end_ms": b, "speaker_id": f"h{c}"} for a, b, c in turns if c >= 0]
        d = der(reference["diarization"], hypothesis, duration, 250, False)
        row["der"] = {"status": "SCORED", "rate": round(d["rate"], 4), **{k: d[k] for k in ("miss_ms", "false_alarm_ms", "confusion_ms", "reference_speaker_ms")}}
    else:
        row["der"] = {"status": "NOT_SCORED", "reason": case["der"]}
    if not case["text"]:
        row["wer"] = row["cpwer"] = {"status": "NOT_SCORED", "reason": "no reference text"}
    elif segments is None:
        row["wer"] = row["cpwer"] = {"status": "NOT_RUN", "reason": "no transcript for this run"}
    else:
        hypothesis = {"schema_version": 1, "recording_id": case["id"], "audio_sha256": reference["audio_sha256"], "audio_duration_ms": duration,
                      "segments": [{k: s[k] for k in ("start_ms", "end_ms", "speaker_id", "text")} for s in segments]}
        report = evaluate({k: v for k, v in reference.items() if k != "diarization"}, hypothesis)
        row["wer"] = {k: report["wer"].get(k) for k in ("status", "errors", "reference_words", "rate")}
        row["cpwer"] = {k: report["cpwer"].get(k) for k in ("status", "errors", "reference_words", "rate", "reason")}
        unknown = dict(hypothesis, segments=[s for s in hypothesis["segments"] if s["speaker_id"] is not None])
        pessimistic = evaluate({k: v for k, v in reference.items() if k != "diarization"}, unknown)["cpwer"]
        row["cpwer_u"] = {k: pessimistic.get(k) for k in ("status", "errors", "reference_words", "rate")}
        row["unattributed_words"] = sum(len(s["text"].split()) for s in segments if s["speaker_id"] is None)
        row["asr_speakers"] = len({s["speaker_id"] for s in segments if s["speaker_id"]})
        row["unattributed_segments"] = sum(1 for s in segments if s["speaker_id"] is None)
    return row


def load_reference(corpus, case):
    return clamp(json.loads((corpus / f"{case['id']}.ref.json").read_text(encoding="utf-8")))


def score_case(case, corpus, results, runs, system):
    run = runs.get(f"{system}/{case['id']}")
    reference = load_reference(corpus, case)
    duration = reference["audio_duration_ms"]
    row = {"case": case["id"], "set": case["set"], "system": system, "duration_ms": duration, "ref_speakers": case["speakers"],
           "noise": case["noise"], "status": run["status"] if run else "NOT_RUN"}
    if not run or run["status"] != "OK":
        return row
    inference = run.get("inference", {})
    row.update(wall_ms=run["wall_ms"], infer_ms=inference.get("infer_ms"), load_ms=inference.get("load_ms"),
               rtf=round(inference["infer_ms"] / duration, 4) if inference.get("infer_ms") else None, peak_mib=run["peak_working_set_mib"])
    segments = None
    if case["text"] and run.get("asr", {}).get("status") == "OK":
        segments = json.loads((results / system / f"{case['id']}.transcript.json").read_text(encoding="utf-8"))["segments"]
    row.update(measure(case, reference, read_turns(results / system / f"{case['id']}.tsv"), segments))
    if case["text"] and segments is None:
        row["wer"] = row["cpwer"] = {"status": "FAILED_ASR"}
    return row


def bootstrap(pairs, seed=20261103, draws=4000):
    """Paired by recording: CI of the pooled-rate difference C2 - C0 from (c0_err, c2_err, words) triples."""
    rng = random.Random(seed)
    diffs = []
    for _ in range(draws):
        sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        words = sum(p[2] for p in sample)
        diffs.append((sum(p[1] for p in sample) - sum(p[0] for p in sample)) / words)
    diffs.sort()
    return round(diffs[int(0.025 * draws)], 4), round(diffs[int(0.975 * draws)], 4)


def summary(rows, set_name):
    out = {}
    by_case = {}
    for r in rows:
        by_case.setdefault(r["case"], {})[r["system"]] = r
    for system in SYSTEMS:
        rs = [r for r in rows if r["system"] == system and r["set"] == set_name]
        ok = [r for r in rs if r["status"] == "OK"]
        s = {"recordings": len(rs), "failed": len(rs) - len(ok),
             "exact_speaker_count": sum(r["hyp_speakers"] == r["ref_speakers"] for r in ok),
             "over_count": sum(r["hyp_speakers"] > r["ref_speakers"] for r in ok),
             "under_count": sum(r["hyp_speakers"] < r["ref_speakers"] for r in ok),
             "mean_abs_count_error": round(float(np.mean([abs(r["hyp_speakers"] - r["ref_speakers"]) for r in ok])), 3) if ok else None,
             "split_speakers": sum(len(r["speaker"]["split_speakers"]) for r in ok),
             "merged_clusters": sum(len(r["speaker"]["merged_clusters"]) for r in ok),
             "attribution": round(sum(r["speaker"]["attributed_correctly"] for r in ok) / max(1, sum(r["speaker"]["frames"] for r in ok)), 4),
             "same_speaker_returns": f"{sum(r['recurrence']['same_correct'] for r in ok)}/{sum(r['recurrence']['same_pairs'] for r in ok)}",
             "different_speakers_apart": f"{sum(r['recurrence']['different_correct'] for r in ok)}/{sum(r['recurrence']['different_pairs'] for r in ok)}",
             "median_rtf": round(float(np.median([r["rtf"] for r in ok if r["rtf"]])), 4) if ok else None,
             "max_peak_mib": max((r["peak_mib"] for r in ok), default=None),
             "median_wall_ms": round(float(np.median([r["wall_ms"] for r in ok]))) if ok else None}
        text = [r for r in ok if r.get("wer", {}).get("status") == "SCORED"]
        if text:
            s["wer"] = f"{sum(r['wer']['errors'] for r in text)}/{sum(r['wer']['reference_words'] for r in text)}"
            cp = [r for r in ok if r["cpwer"]["status"] == "SCORED"]
            s["cpwer_scored"] = f"{len(cp)}/{len(text)}"
            s["cpwer_on_scored"] = f"{sum(r['cpwer']['errors'] for r in cp)}/{sum(r['cpwer']['reference_words'] for r in cp)}" if cp else None
            s["cpwer_u"] = f"{sum(r['cpwer_u']['errors'] for r in text)}/{sum(r['cpwer_u']['reference_words'] for r in text)}"
            s["unattributed_words"] = sum(r["unattributed_words"] for r in text)
        else:
            s["wer"] = s["cpwer_scored"] = "NOT_SCORED"
        ders = [r for r in ok if r["der"]["status"] == "SCORED"]
        if ders:
            errors = sum(r["der"]["miss_ms"] + r["der"]["false_alarm_ms"] + r["der"]["confusion_ms"] for r in ders)
            s["der_pooled"] = round(errors / sum(r["der"]["reference_speaker_ms"] for r in ders), 4)
            s["der_components_ms"] = {k: sum(r["der"][k] for r in ders) for k in ("miss_ms", "false_alarm_ms", "confusion_ms")}
        else:
            s["der_pooled"] = "NOT_SCORED"
        out[system] = s
    # cpWER difference only on recordings where both systems are scored, so neither gets a NOT_SCORED pass.
    both = [(c["C0"]["cpwer"]["errors"], c["C2"]["cpwer"]["errors"], c["C0"]["cpwer"]["reference_words"]) for c in by_case.values()
            if set(SYSTEMS) <= set(c) and c["C0"]["set"] == set_name and all(c[x].get("cpwer", {}).get("status") == "SCORED" for x in SYSTEMS)]
    if len(both) >= 5:
        out["cpwer_both_scored"] = {"recordings": len(both), "C0": f"{sum(p[0] for p in both)}/{sum(p[2] for p in both)}",
                                    "C2": f"{sum(p[1] for p in both)}/{sum(p[2] for p in both)}", "c2_minus_c0_95ci": bootstrap(both)}
    pessimistic = [(c["C0"]["cpwer_u"]["errors"], c["C2"]["cpwer_u"]["errors"], c["C0"]["cpwer_u"]["reference_words"]) for c in by_case.values()
                   if set(SYSTEMS) <= set(c) and c["C0"]["set"] == set_name and all("cpwer_u" in c[x] for x in SYSTEMS)]
    if len(pessimistic) >= 5:
        out["cpwer_u_paired"] = {"recordings": len(pessimistic), "c2_minus_c0_95ci": bootstrap(pessimistic)}
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.evidence / "manifest.json").read_text(encoding="utf-8"))
    runs = json.loads((args.evidence / "runs.json").read_text(encoding="utf-8"))
    rows = [score_case(case, args.corpus, args.results, runs, system) for case in manifest["cases"] for system in SYSTEMS]
    report = {"scope": __doc__.strip(), "summary": {name: summary(rows, name) for name in ("phone3", "holdout", "realmix")}, "rows": rows}
    (args.evidence / "scores.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=1))
    for r in rows:
        if r["set"] == "phone3":
            print(r["case"], r["system"], r.get("hyp_speakers"), r.get("wer", {}).get("errors"), r.get("cpwer", {}).get("errors"), r.get("cpwer", {}).get("status"))


if __name__ == "__main__":
    main()
