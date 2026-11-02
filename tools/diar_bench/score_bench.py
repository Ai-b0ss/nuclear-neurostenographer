"""Score C0/C1 runs with tools/score_transcript.py and write tables.

A failed or timed-out run stays in the scored set: it is scored as an empty hypothesis (100% DER, all words deleted)
and counted as a failure. A stored output that no longer matches its record, audio or reference is refused.
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
SYSTEMS = ("C0", "C1", "C2")


class StaleEvidence(Exception):
    pass


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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


def verify_case(case, corpus):
    """Refuse a reference or audio file that differs from the frozen manifest."""
    for path, field in ((corpus / f"{case['id']}.wav", "audio_sha256"), (corpus / f"{case['id']}.ref.json", "reference_sha256")):
        if sha256_file(path) != case[field]:
            raise StaleEvidence(f"{path.name} differs from manifest {field}")


def verify_run(run, turns_path):
    """Refuse an output that was not produced by the run it is stored with."""
    if not run.get("fingerprint"):
        raise StaleEvidence(f"{turns_path.name}: run has no fingerprint")
    if run.get("turns_sha256") != sha256_file(turns_path):
        raise StaleEvidence(f"{turns_path.name}: output differs from its run record")


def verify_environment(run, expected):
    if expected is not None and run.get("fingerprint") != expected:
        raise StaleEvidence("Run fingerprint differs from the current model, code, threshold or audio")


def score_row(row, case, run, folder, reference_path, reference, runs, key):
    """Fill one row. A run that produced no usable output is scored as an empty hypothesis."""
    failed = run["status"] != "OK"
    row["scored_as_empty_hypothesis"] = failed
    turns = []
    if not failed:
        turns_path = folder / f"{case['id']}.tsv"
        verify_run(run, turns_path)
        turns = read_turns(turns_path)
        clusters = {t[2] for t in turns if t[2] >= 0}
        row.update(hyp_speakers=len(clusters), ref_speakers=case["speakers"], turn_count=len(turns),
                   hyp_speech_ms=sum(t[1] - t[0] for t in turns), unknown_turns=sum(t[2] < 0 for t in turns))
    diarization = [{"start_ms": a, "end_ms": b, "speaker_id": speaker_name(c)} for a, b, c in turns]
    hypothesis = {"audio_sha256": case["audio_sha256"], "audio_duration_ms": case["duration_ms"], "segments": [], "diarization": diarization}
    asr = runs.get(key + "/asr")
    row["asr_status"] = asr["status"] if asr else None
    if asr and asr["status"] == "OK":
        transcript = folder / f"{case['id']}.transcript.json"
        if asr.get("transcript_sha256") != sha256_file(transcript):
            raise StaleEvidence(f"{transcript.name}: output differs from its run record")
        segments = json.loads(transcript.read_text(encoding="utf-8"))["segments"]
        row.update(asr_words=sum(len(s["text"].split()) for s in segments),
                   asr_unknown_words=sum(len(s["text"].split()) for s in segments if s["speaker_id"] is None or not s.get("attribution_reliable", True)))
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
        row["der"][name] = {k: d.get(k) for k in ("status", "reason", "rate", "miss_ms", "false_alarm_ms", "confusion_ms", "reference_speaker_ms") if k in d}
        if name == "collar0_overlap":
            row["wer"] = {k: report["wer"].get(k) for k in ("status", "errors", "reference_words", "rate")}
            row["cpwer"] = {k: report["cpwer"].get(k) for k in ("status", "errors", "reference_words", "rate", "insertions", "deletions", "substitutions")}
    ref_turns = reference.get("diarization")
    if not failed:
        if ref_turns:
            row["overlap"] = overlap_stats(ref_turns, turns, case["duration_ms"])
            row["recurrence"] = recurrence(ref_turns, turns)
        elif reference.get("text_segments"):
            row["recurrence"] = recurrence(reference["text_segments"], turns)
    return row


def aggregate(group_rows, protocol):
    """Failures stay in the denominator because they were scored as empty hypotheses."""
    scored = [r for r in group_rows if r.get("der", {}).get(protocol, {}).get("status") == "SCORED"]
    denominator = sum(r["der"][protocol]["reference_speaker_ms"] for r in scored)
    parts = {k: sum(r["der"][protocol][k] for r in scored) for k in ("miss_ms", "false_alarm_ms", "confusion_ms")}
    return {"n": len(group_rows), "scored": len(scored), "failed": sum(r["status"] != "OK" for r in group_rows), "denominator_ms": denominator,
            "der": sum(parts.values()) / denominator if denominator else None,
            "miss": parts["miss_ms"] / denominator if denominator else None,
            "fa": parts["false_alarm_ms"] / denominator if denominator else None,
            "confusion": parts["confusion_ms"] / denominator if denominator else None}


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


def fmt(x):
    return "NOT_SCORED" if x is None else f"{100 * x:.2f}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--results", default="results-v2")
    args = parser.parse_args()
    manifest = json.loads((args.evidence / "corpus-manifest.json").read_text(encoding="utf-8"))
    runs = json.loads((args.evidence / "runs.json").read_text(encoding="utf-8"))
    corpus = args.root / "data/corpus"
    rows = []
    for case in manifest["cases"]:
        verify_case(case, corpus)
        reference_path = corpus / f"{case['id']}.ref.json"
        reference = json.loads(reference_path.read_text(encoding="utf-8"))
        for system in SYSTEMS:
            key = f"{system}/{case['id']}"
            run = runs.get(key, {"status": "NOT_RUN"})
            row = {"case": case["id"], "group": case["group"], "scenario": case["scenario"], "system": system,
                   "duration_ms": case["duration_ms"], "status": run["status"], "wall_ms": run.get("wall_ms"),
                   "peak_mib": run.get("peak_working_set_mib"), "inference": run.get("inference")}
            rows.append(score_row(row, case, run, args.root / args.results / system, reference_path, reference, runs, key))
    (args.evidence / "scores.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    summary = {}
    lines = ["# C0/C1/C2 host tables, version 2 (generated by score_bench.py)", "",
             "Failed runs are scored as empty hypotheses. ivkond DER is NOT_SCORED: its labels fail the reference check.", ""]
    scenarios = []
    for row in rows:
        if row["scenario"] not in scenarios:
            scenarios.append(row["scenario"])
    for protocol in PROTOCOLS:
        lines += [f"## DER, protocol `{protocol}`: %, pooled by reference speaker time", "",
                  "| Scenario | N | C0 DER (miss/FA/conf) | C1 fp32 DER | C2 int8 DER | C2-C0 pp, 95% CI by recording | Failures C0/C1/C2 |", "|---|---:|---|---|---|---|---|"]
        for scenario in scenarios:
            per = {s: aggregate([r for r in rows if r["scenario"] == scenario and r["system"] == s], protocol) for s in SYSTEMS}
            pairs = []
            for case in sorted({r["case"] for r in rows if r["scenario"] == scenario}):
                a = next(r for r in rows if r["case"] == case and r["system"] == "C0")
                b = next(r for r in rows if r["case"] == case and r["system"] == "C2")
                da, db = a["der"][protocol], b["der"][protocol]
                if da.get("status") == "SCORED" and db.get("status") == "SCORED":
                    err = lambda d: d["miss_ms"] + d["false_alarm_ms"] + d["confusion_ms"]
                    pairs.append((err(da), err(db), da["reference_speaker_ms"]))
            ci = bootstrap(pairs)
            summary.setdefault(protocol, {})[scenario] = {**per, "c2_minus_c0_ci": ci, "paired": len(pairs)}
            cell = lambda p: f"{fmt(p['der'])} ({fmt(p['miss'])}/{fmt(p['fa'])}/{fmt(p['confusion'])})" if p["der"] is not None else "NOT_SCORED"
            diff = "NOT_SCORED" if per["C0"]["der"] is None or per["C2"]["der"] is None else f"{100 * (per['C2']['der'] - per['C0']['der']):+.2f} [{100 * ci[0]:+.2f}, {100 * ci[1]:+.2f}]"
            lines.append(f"| {scenario} | {per['C0']['n']} | {cell(per['C0'])} | {cell(per['C1'])} | {cell(per['C2'])} | {diff} | {per['C0']['failed']}/{per['C1']['failed']}/{per['C2']['failed']} |")
        lines.append("")

    lines += ["## Speaker identity and overlap", "", "| Scenario | System | Same-speaker repeat correct | Different-speaker pairs distinct | Exact speaker count | Mean abs count error | Overlap recall | Overlap precision |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for scenario in scenarios:
        for system in SYSTEMS:
            rs = [r for r in rows if r["scenario"] == scenario and r["system"] == system and r["status"] == "OK"]
            if not rs or "recurrence" not in rs[0]:
                continue
            same = sum(r["recurrence"]["same_correct"] for r in rs), sum(r["recurrence"]["same_pairs"] for r in rs)
            diff = sum(r["recurrence"]["different_correct"] for r in rs), sum(r["recurrence"]["different_pairs"] for r in rs)
            exact = sum(r["hyp_speakers"] == r["ref_speakers"] for r in rs)
            error = sum(abs(r["hyp_speakers"] - r["ref_speakers"]) for r in rs) / len(rs)
            over = [r["overlap"] for r in rs if "overlap" in r]
            ref_ms, hyp_ms, both = (sum(o[k] for o in over) for k in ("reference_overlap_ms", "hypothesis_overlap_ms", "overlap_both_ms"))
            recall = f"{100 * both / ref_ms:.1f}%" if ref_ms else "NOT_SCORED"
            precision = f"{100 * both / hyp_ms:.1f}%" if hyp_ms else "NOT_SCORED"
            lines.append(f"| {scenario} | {system} | {same[0]}/{same[1]} | {diff[0]}/{diff[1]} | {exact}/{len(rs)} | {error:.2f} | {recall} | {precision} |")
    lines += ["", "## Fixed ASR: GigaAM v3 CTC, same production window and fusion code", "",
              "Unattributed words count as an extra speaker in cpWER. Boundaries differ by diarizer, so WER differs too. A failed run counts all words as deleted.", "",
              "| Scenario | System | Files scored | WER % | cpWER % | Reference words | Unattributed share % | Failures |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for scenario in scenarios:
        for system in SYSTEMS:
            all_rows = [r for r in rows if r["scenario"] == scenario and r["system"] == system]
            rs = [r for r in all_rows if r.get("cpwer", {}).get("status") == "SCORED"]
            if not rs:
                continue
            ref = sum(r["cpwer"]["reference_words"] for r in rs)
            wer = sum(r["wer"]["errors"] for r in rs) / ref if ref else None
            cp = sum(r["cpwer"]["errors"] for r in rs) / ref if ref else None
            total = sum(r.get("asr_words", 0) for r in rs)
            unknown = sum(r.get("asr_unknown_words", 0) for r in rs)
            failed = sum(r["status"] != "OK" or r.get("asr_status") != "OK" for r in all_rows)
            lines.append(f"| {scenario} | {system} | {len(rs)}/{len(all_rows)} | {fmt(wer)} | {fmt(cp)} | {ref} | {fmt(unknown / total if total else None)} | {failed} |")
    lines += ["", "## Non-speech", "", "| Case | System | Status | Detected speech s | Speakers |", "|---|---|---|---:|---:|"]
    for row in rows:
        if row["group"] == "nonspeech":
            lines.append(f"| {row['scenario']} | {row['system']} | {row['status']} | {row.get('hyp_speech_ms', 0) / 1000:.1f} | {row.get('hyp_speakers', 'n/a')} |")
    lines += ["", "## Host cost (Windows x86-64, E5-2690 v4, 2 inference threads). Not a phone measurement", "",
              "Same boundaries: load = model session creation; infer = diarization and post-processing up to the written turns file, on ",
              "ONNX Runtime 1.17.1 for C0 and the version in environment.json for C1/C2; wall = whole child process, including runtime start (JVM or Python).", "",
              "| System | Files OK/all | Audio min | Infer RTF | Infer RTF worst | Wall RTF | Load ms median | Wall overhead ms median |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for system in SYSTEMS:
        all_rows = [r for r in rows if r["system"] == system]
        rs = [r for r in all_rows if r["status"] == "OK" and r.get("inference")]
        if not rs:
            continue
        audio = sum(r["duration_ms"] for r in rs)
        rtf = sum(r["inference"]["infer_ms"] for r in rs) / audio
        worst = max(r["inference"]["infer_ms"] / r["duration_ms"] for r in rs)
        wall = sum(r["wall_ms"] for r in rs) / audio
        load = sorted(r["inference"]["load_ms"] for r in rs)[len(rs) // 2]
        overhead = sorted(r["wall_ms"] - r["inference"]["infer_ms"] for r in rs)[len(rs) // 2]
        lines.append(f"| {system} | {len(rs)}/{len(all_rows)} | {audio / 60000:.1f} | {rtf:.3f} | {worst:.3f} | {wall:.3f} | {load} | {overhead} |")
    (args.evidence / "tables.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (args.evidence / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
