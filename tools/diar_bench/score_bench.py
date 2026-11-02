"""Score C0/C1 runs with tools/score_transcript.py and write tables for the PR.

A failed run stays visible: it is counted, and the conservative aggregate treats it as 100% DER.
Same-speaker returns, speaker count and overlap detection are computed here from reference and turns.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
PROTOCOLS = {"collar0_overlap": (0, False), "collar250_overlap": (250, False), "collar250_no_overlap": (250, True)}


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def read_turns(path):
    turns = []
    for line in path.read_text(encoding="ascii").splitlines():
        if line.strip():
            start, end, cluster = line.split("\t")
            turns.append((int(start), int(end), int(cluster)))
    return turns


def speaker_name(cluster):
    return None if cluster < 0 else f"h{cluster}"


def overlap_stats(reference, hypothesis, duration):
    """Millisecond timeline of how many speakers are active in reference and hypothesis."""
    points = sorted({0, duration, *[x for t in reference for x in (t["start_ms"], t["end_ms"])], *[x for t in hypothesis for x in t[:2]]})
    ref_ms = hyp_ms = both = 0
    for a, b in zip(points, points[1:]):
        r = {t["speaker_id"] for t in reference if t["start_ms"] <= a < t["end_ms"]}
        h = {t[2] for t in hypothesis if t[0] <= a < t[1]}
        ref_ms += (b - a) * (len(r) >= 2)
        hyp_ms += (b - a) * (len(h) >= 2)
        both += (b - a) * (len(r) >= 2 and len(h) >= 2)
    return {"reference_overlap_ms": ref_ms, "hypothesis_overlap_ms": hyp_ms, "overlap_both_ms": both}


def merge_turns(turns, gap_ms=500):
    merged = {}
    for t in sorted(turns, key=lambda x: x["start_ms"]):
        rows = merged.setdefault(t["speaker_id"], [])
        if rows and t["start_ms"] - rows[-1][1] <= gap_ms:
            rows[-1][1] = max(rows[-1][1], t["end_ms"])
        else:
            rows.append([t["start_ms"], t["end_ms"]])
    return [(s, a, b) for s, rows in merged.items() for a, b in rows]


def recurrence(reference, hypothesis):
    """For turns of at least 1 s: dominant cluster must repeat for a speaker and differ across speakers."""
    turns = [t for t in merge_turns(reference) if t[2] - t[1] >= 1000]
    turns.sort(key=lambda t: t[1])
    dominant = []
    for speaker, start, end in turns:
        votes = {}
        for a, b, cluster in hypothesis:
            if cluster >= 0 and min(end, b) > max(start, a):
                votes[cluster] = votes.get(cluster, 0) + min(end, b) - max(start, a)
        ranked = sorted(votes.items(), key=lambda x: (-x[1], x[0]))
        dominant.append((speaker, ranked[0][0] if ranked else None))
    same_ok = same = diff_ok = diff = 0
    for i, (a, x) in enumerate(dominant):
        for b, y in dominant[i + 1:]:
            if a == b:
                same += 1
                same_ok += x is not None and x == y
            else:
                diff += 1
                diff_ok += x is not None and y is not None and x != y
    return {"same_pairs": same, "same_correct": same_ok, "different_pairs": diff, "different_correct": diff_ok, "turns": len(dominant)}


def score(reference_path, hypothesis_path, out, collar, skip):
    command = [sys.executable, str(REPO / "tools/score_transcript.py"), "--reference", str(reference_path), "--hypothesis", str(hypothesis_path),
               "--output", str(out), "--collar-ms", str(collar)] + (["--skip-overlap"] if skip else [])
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode == 1:
        raise SystemExit(f"Scorer ERROR {out}: {completed.stdout}")
    return json.loads(out.read_text(encoding="utf-8"))


def bootstrap(pairs, seed=20261102, draws=4000):
    """Paired bootstrap by recording for pooled DER(B) - DER(A). pairs: (errA, errB, denom)."""
    if not pairs:
        return None
    rng = random.Random(seed)
    values = []
    for _ in range(draws):
        sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        d = sum(p[2] for p in sample)
        values.append(sum(p[1] - p[0] for p in sample) / d if d else 0.0)
    values.sort()
    return [values[int(0.025 * draws)], values[int(0.975 * draws)]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.evidence / "corpus-manifest.json").read_text(encoding="utf-8"))
    runs = json.loads((args.evidence / "runs.json").read_text(encoding="utf-8"))
    corpus = args.root / "data/corpus"
    rows = []
    for case in manifest["cases"]:
        reference_path = corpus / f"{case['id']}.ref.json"
        reference = json.loads(reference_path.read_text(encoding="utf-8"))
        ref_turns = reference.get("diarization")
        for system in ("C0", "C1", "C2"):
            key = f"{system}/{case['id']}"
            run = runs.get(key, {"status": "NOT_RUN"})
            row = {"case": case["id"], "group": case["group"], "scenario": case["scenario"], "system": system,
                   "duration_ms": case["duration_ms"], "status": run["status"], "wall_ms": run.get("wall_ms"),
                   "peak_mib": run.get("peak_working_set_mib"), "inference": run.get("inference")}
            rows.append(row)
            folder = args.root / "results" / system
            if run["status"] != "OK":
                continue
            turns = read_turns(folder / f"{case['id']}.tsv")
            clusters = {t[2] for t in turns if t[2] >= 0}
            row.update(hyp_speakers=len(clusters), ref_speakers=case["speakers"], turn_count=len(turns),
                       hyp_speech_ms=sum(t[1] - t[0] for t in turns), unknown_turns=sum(t[2] < 0 for t in turns))
            diarization = [{"start_ms": a, "end_ms": b, "speaker_id": speaker_name(c)} for a, b, c in turns]
            hypothesis = {"audio_sha256": case["audio_sha256"], "audio_duration_ms": case["duration_ms"], "segments": [], "diarization": diarization}
            asr = runs.get(key + "/asr")
            row["asr_status"] = asr["status"] if asr else None
            if asr and asr["status"] == "OK":
                document = json.loads((folder / f"{case['id']}.transcript.json").read_text(encoding="utf-8"))
                segments = document["segments"]
                total_words = sum(len(s["text"].split()) for s in segments)
                unknown_words = sum(len(s["text"].split()) for s in segments if s["speaker_id"] is None or not s.get("attribution_reliable", True))
                row.update(asr_words=total_words, asr_unknown_words=unknown_words, asr_decode_ms=asr["inference"]["decode_ms"])
                # Words the app would leave unattributed count against the system as an extra speaker.
                hypothesis["segments"] = [{"start_ms": s["start_ms"], "end_ms": s["end_ms"], "text": s["text"], "attribution_reliable": True,
                                           "speaker_id": s["speaker_id"] if s["speaker_id"] and s.get("attribution_reliable", True) else "UNATTRIBUTED"} for s in segments]
            score_dir = folder / "scores" / case["id"]
            score_dir.mkdir(parents=True, exist_ok=True)
            hypothesis_path = score_dir / "hypothesis.json"
            hypothesis_path.write_text(json.dumps(hypothesis, ensure_ascii=False), encoding="utf-8")
            row["der"] = {}
            for name, (collar, skip) in PROTOCOLS.items():
                report = score(reference_path, hypothesis_path, score_dir / f"{name}.json", collar, skip)
                d = report["der"]
                row["der"][name] = {k: d.get(k) for k in ("status", "rate", "miss_ms", "false_alarm_ms", "confusion_ms", "reference_speaker_ms")}
                if name == "collar0_overlap":
                    row["wer"] = {k: report["wer"].get(k) for k in ("status", "errors", "reference_words", "rate")}
                    row["cpwer"] = {k: report["cpwer"].get(k) for k in ("status", "errors", "reference_words", "rate", "insertions", "deletions", "substitutions")}
            if ref_turns and case["group"] != "ivkond":
                row["overlap"] = overlap_stats(ref_turns, turns, case["duration_ms"])
                row["recurrence"] = recurrence(ref_turns, turns)
            elif ref_turns:
                row["recurrence"] = recurrence(ref_turns, turns)
            elif reference.get("text_segments"):
                row["recurrence"] = recurrence(reference["text_segments"], turns)
    (args.evidence / "scores.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    def aggregate(group_rows, protocol):
        scored = [r for r in group_rows if r.get("der", {}).get(protocol, {}).get("status") == "SCORED"]
        denominator = sum(r["der"][protocol]["reference_speaker_ms"] for r in scored)
        parts = {k: sum(r["der"][protocol][k] for r in scored) for k in ("miss_ms", "false_alarm_ms", "confusion_ms")}
        failed = [r for r in group_rows if r["status"] != "OK"]
        return {"n": len(group_rows), "scored": len(scored), "failed": len(failed), "denominator_ms": denominator,
                "der": sum(parts.values()) / denominator if denominator else None,
                "miss": parts["miss_ms"] / denominator if denominator else None,
                "fa": parts["false_alarm_ms"] / denominator if denominator else None,
                "confusion": parts["confusion_ms"] / denominator if denominator else None}

    def fmt(x):
        return "NOT_SCORED" if x is None else f"{100 * x:.2f}"

    summary = {}
    lines = ["# C0/C1/C2 host tables (generated by score_bench.py)", ""]
    scenarios = []
    for row in rows:
        if row["scenario"] not in scenarios:
            scenarios.append(row["scenario"])
    # ivkond labels cover about 100% of each file while roughly 45% of frames carry energy: DER is NOT_SCORED there.
    groups = {"natural_call": "DataHive natural calls; VAD-derived reference", "clean_2spk": "ru-book clean, 2 speakers", "clean_3spk": "ru-book clean, 3 speakers",
              "clean_4spk": "ru-book clean, 4 speakers", "high_overlap": "ru-book, highest overlap", "noise_10db": "ru-book + white noise 10 dB", "noise_0db": "ru-book + white noise 0 dB"}
    for protocol in PROTOCOLS:
        lines += [f"## DER, protocol `{protocol}`: %, pooled by reference speaker time", "",
                  "| Scenario | N | C0 DER (miss/FA/conf) | C1 fp32 DER | C2 int8 DER | C2-C0 pp, 95% CI by recording | Failures C0/C1/C2 |", "|---|---:|---|---|---|---|---|"]
        for scenario in scenarios:
            if scenario not in groups:
                continue
            per = {s: aggregate([r for r in rows if r["scenario"] == scenario and r["system"] == s], protocol) for s in ("C0", "C1", "C2")}
            pairs = []
            for case in {r["case"] for r in rows if r["scenario"] == scenario}:
                a = next((r for r in rows if r["case"] == case and r["system"] == "C0"), None)
                b = next((r for r in rows if r["case"] == case and r["system"] == "C2"), None)
                da, db = (x.get("der", {}).get(protocol, {}) if x else {} for x in (a, b))
                if da.get("status") == "SCORED" and db.get("status") == "SCORED":
                    err = lambda d: d["miss_ms"] + d["false_alarm_ms"] + d["confusion_ms"]
                    pairs.append((err(da), err(db), da["reference_speaker_ms"]))
            pairs.sort()
            ci = bootstrap(pairs)
            summary.setdefault(protocol, {})[scenario] = {**{s: per[s] for s in per}, "c2_minus_c0_ci": ci, "paired": len(pairs)}
            cell = lambda p: f"{fmt(p['der'])} ({fmt(p['miss'])}/{fmt(p['fa'])}/{fmt(p['confusion'])})"
            diff = "NOT_SCORED" if per["C0"]["der"] is None or per["C2"]["der"] is None else f"{100 * (per['C2']['der'] - per['C0']['der']):+.2f} [{100 * ci[0]:+.2f}, {100 * ci[1]:+.2f}]"
            lines.append(f"| {groups[scenario]} | {per['C0']['n']} | {cell(per['C0'])} | {cell(per['C1'])} | {cell(per['C2'])} | {diff} | {per['C0']['failed']}/{per['C1']['failed']}/{per['C2']['failed']} |")
        lines.append("")

    def sum_field(rs, get):
        return sum(get(r) for r in rs)

    lines += ["## Speaker identity and overlap", "", "| Scenario | System | Same-speaker repeat correct | Different-speaker pairs distinct | Exact speaker count | Mean abs count error | Overlap recall | Overlap precision |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for scenario in scenarios:
        for system in ("C0", "C1", "C2"):
            rs = [r for r in rows if r["scenario"] == scenario and r["system"] == system and r["status"] == "OK"]
            if not rs or "recurrence" not in rs[0]:
                continue
            same = sum_field(rs, lambda r: r["recurrence"]["same_correct"]), sum_field(rs, lambda r: r["recurrence"]["same_pairs"])
            diff = sum_field(rs, lambda r: r["recurrence"]["different_correct"]), sum_field(rs, lambda r: r["recurrence"]["different_pairs"])
            exact = sum(r["hyp_speakers"] == r["ref_speakers"] for r in rs)
            error = sum(abs(r["hyp_speakers"] - r["ref_speakers"]) for r in rs) / len(rs)
            over = [r["overlap"] for r in rs if "overlap" in r]
            ref_ms, hyp_ms, both = (sum(o[k] for o in over) for k in ("reference_overlap_ms", "hypothesis_overlap_ms", "overlap_both_ms"))
            recall = f"{100 * both / ref_ms:.1f}%" if ref_ms else "NOT_SCORED"
            precision = f"{100 * both / hyp_ms:.1f}%" if hyp_ms else "NOT_SCORED"
            lines.append(f"| {scenario} | {system} | {same[0]}/{same[1]} | {diff[0]}/{diff[1]} | {exact}/{len(rs)} | {error:.2f} | {recall} | {precision} |")
    lines += ["", "## Fixed ASR: GigaAM v3 CTC, same production window and fusion code", "",
              "Unattributed words count as an extra speaker in cpWER. Boundaries differ by diarizer, so WER differs too.", "",
              "| Scenario | System | Files | WER % | cpWER % | Reference words | Unattributed share % | ASR failures |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for scenario in scenarios:
        for system in ("C0", "C1", "C2"):
            all_rows = [r for r in rows if r["scenario"] == scenario and r["system"] == system]
            rs = [r for r in all_rows if r.get("cpwer", {}).get("status") == "SCORED"]
            if not rs and not any(r.get("asr_status") for r in all_rows):
                continue
            ref = sum(r["cpwer"]["reference_words"] for r in rs)
            wer = sum(r["wer"]["errors"] for r in rs) / ref if ref else None
            cp = sum(r["cpwer"]["errors"] for r in rs) / ref if ref else None
            total = sum(r["asr_words"] for r in rs)
            unknown = sum(r["asr_unknown_words"] for r in rs)
            failed = sum(r.get("asr_status") not in ("OK",) for r in all_rows)
            lines.append(f"| {scenario} | {system} | {len(rs)}/{len(all_rows)} | {fmt(wer)} | {fmt(cp)} | {ref} | {fmt(unknown / total if total else None)} | {failed} |")
    lines += ["", "## Non-speech", "", "| Case | System | Status | Detected speech s | Speakers |", "|---|---|---|---:|---:|"]
    for row in rows:
        if row["group"] == "nonspeech":
            lines.append(f"| {row['scenario']} | {row['system']} | {row['status']} | {row.get('hyp_speech_ms', 0) / 1000:.1f} | {row.get('hyp_speakers', 'n/a')} |")
    lines += ["", "## Host cost (Windows x86-64, E5-2690 v4, 2 inference threads). Not a phone measurement", "",
              "RTF = process_ms/audio. Memory is measured separately on the 20-minute file: the first run counted only the venv launcher for C1/C2.", "",
              "| System | Files OK/all | Audio min | RTF pooled | RTF worst file | Load ms median |", "|---|---:|---:|---:|---:|---:|"]
    for system in ("C0", "C1", "C2"):
        all_rows = [r for r in rows if r["system"] == system]
        rs = [r for r in all_rows if r["status"] == "OK" and r.get("inference")]
        if not rs:
            continue
        audio = sum(r["duration_ms"] for r in rs)
        rtf = sum(r["inference"]["process_ms"] for r in rs) / audio
        worst = max(r["inference"]["process_ms"] / r["duration_ms"] for r in rs)
        load = sorted(r["inference"]["load_ms"] for r in rs)[len(rs) // 2]
        lines.append(f"| {system} | {len(rs)}/{len(all_rows)} | {audio / 60000:.1f} | {rtf:.3f} | {worst:.3f} | {load} |")
    (args.evidence / "tables.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (args.evidence / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
