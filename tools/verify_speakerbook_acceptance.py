"""Verify frozen speakerbook acceptance evidence without rerunning phone/model inference.

Usage: python tools/verify_speakerbook_acceptance.py --qa-dir .local/qa-three-checks-current
No audio, transcripts or voice embeddings are copied into this report.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/c2_same_tracks"))
from score_transcript import der as exhaustive_der
from score_same_corpus import der as hungarian_der


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qa-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    qa = args.qa_dir.resolve()
    inputs = json.loads((qa / "veche_c2_output/inputs.json").read_text(encoding="utf8"))
    checked_sources = {}
    for name, expected in inputs["sources"].items():
        path = ROOT.joinpath(*name.replace("\\", "/").split("/"))
        actual = digest(path)
        if actual != expected:
            raise ValueError("Source provenance mismatch: " + name)
        checked_sources[name.replace("\\", "/")] = actual
    for name, expected in inputs["model_pins"].items():
        if digest(qa / "c2model" / name) != expected:
            raise ValueError("Model hash mismatch: " + name)
    ort = Path("K:/nn-bench/harness/onnxruntime-1.17.1.jar")
    if digest(ort) != inputs["ort_jar_sha256"]:
        raise ValueError("ORT hash mismatch")
    prior = json.loads((qa / "veche_hard_diarization_result.json").read_text(encoding="utf8"))
    rows = []
    for old in prior["files"]:
        name = old["meeting"]
        wav = qa / "veche_hard" / (name + ".wav")
        if digest(wav) != inputs["wavs"][wav.name] or digest(wav) != old["wav_sha256"]:
            raise ValueError("Audio hash mismatch: " + name)
        with wave.open(str(wav), "rb") as stream:
            duration = round(stream.getnframes() * 1000 / stream.getframerate())
        csv_path = qa / "veche_hard" / (name + ".csv")
        with csv_path.open(encoding="utf-8-sig", newline="") as stream:
            ref = [{"start_ms": round(float(x["start"]) * 1000),
                    "end_ms": round(float(x["end"]) * 1000),
                    "speaker_id": x["speaker_id"]} for x in csv.DictReader(stream)]
        row = {"meeting": name, "duration_ms": duration,
               "reference_speakers": len({x["speaker_id"] for x in ref}),
               "wav_sha256": digest(wav), "csv_sha256": digest(csv_path),
               "metrics": {}, "hypothesis_sha256": {}}
        for mode in ("product", "raw"):
            path = qa / "veche_c2_output" / (name + "." + mode + ".tsv")
            hyp = []
            for line in path.read_text(encoding="utf8").splitlines():
                start, end, cluster = line.split("\t")
                start = max(0, round(float(start) * 1000))
                end = min(duration, round(float(end) * 1000))
                if end > start:
                    hyp.append({"start_ms": start, "end_ms": end,
                                "speaker_id": str(int(cluster)) if int(cluster) >= 0 else None})
            if any(x["speaker_id"] is None for x in hyp):
                raise ValueError("Unknown cluster requires explicit scoring policy")
            if mode == "product":
                row["predicted_speakers"] = len({x["speaker_id"] for x in hyp})
            row["hypothesis_sha256"][mode] = digest(path)
            for collar in (0, 250):
                a = exhaustive_der(ref, hyp, duration, collar, False)
                b = hungarian_der(ref, hyp, duration, collar, False)
                if a["status"] != "SCORED":
                    raise ValueError("Exhaustive scorer did not score")
                keys = ("reference_speaker_ms", "miss_ms", "false_alarm_ms", "confusion_ms")
                if any(a[k] != b[k] for k in keys) or abs(a["rate"] - b["rate"]) > 1e-12:
                    raise ValueError("Independent DER implementation disagreement")
                key = mode + "_collar_" + str(collar) + "ms"
                if any(a[k] != old[key][k] for k in keys):
                    raise ValueError("Saved score mismatch: " + name + "/" + key)
                row["metrics"][key] = {k: a[k] for k in (*keys, "rate")}
        rows.append(row)
    pooled = {}
    for mode in ("product", "raw"):
        for collar in (0, 250):
            key = mode + "_collar_" + str(collar) + "ms"
            total = {k: sum(row["metrics"][key][k] for row in rows)
                     for k in ("reference_speaker_ms", "miss_ms", "false_alarm_ms", "confusion_ms")}
            rate = 100 * sum(total[k] for k in ("miss_ms", "false_alarm_ms", "confusion_ms")) / total["reference_speaker_ms"]
            if abs(rate - prior["diarization"][mode + "_" + str(collar) + "ms"]["DER_pct"]) > 1e-10:
                raise ValueError("Saved pooled DER mismatch")
            pooled[key] = {**total, "DER_pct": rate}
    thermal_path = ROOT / ".local/speakerbook-long20-validation-20261112.status.json"
    thermal = json.loads(thermal_path.read_text(encoding="utf8"))
    if thermal["status"] != "THERMAL_ABORT" or not thermal["cleanup_verified"]["verified"]:
        raise ValueError("Thermal abort/cleanup evidence mismatch")
    read_inputs = ["veche_hard_diarization_result.json", "russian_c2_der_score.json",
                   "russian_voice_link_score.json", "russian_c2_actual_voice_links_result.json",
                   "strict_previous_project_exclusion.json"]
    result = {"schema": "speakerbook-final-acceptance-verification-v1", "date": "2026-11-12",
              "status": "VERIFIED_SAVED_RESULTS", "release_decision": "NO_GO_GLOBAL_SPEAKERBOOK",
              "verification": "Re-scored frozen actual model predictions; no new model or Android run",
              "git_head": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
              "source_hashes_verified": checked_sources, "model_hashes_verified": inputs["model_pins"],
              "ort_sha256_verified": inputs["ort_jar_sha256"],
              "source_report_hashes": {name: digest(qa / name) for name in read_inputs},
              "veche": {"audio_duration_ms": sum(row["duration_ms"] for row in rows),
                        "recordings": rows, "pooled": pooled,
                        "crosscheck": "Exact millisecond counts agree between exhaustive and Hungarian DER for all 12 evaluations",
                        "reference_limit": "Human-read scripted assembled meetings; not spontaneous natural dialogue"},
              "long_test": {"status": thermal["status"], "wall_seconds": thermal["wall_seconds"],
                            "max_cpu_c": thermal["max_cpu_temperature_c"],
                            "max_battery_c": thermal["max_temperature_c"],
                            "qa_cleanup_verified": thermal["cleanup_verified"]["verified"],
                            "source_sha256": digest(thermal_path)},
              "not_measured": ["natural spontaneous meeting DER", "latest-build paired WER/cpWER",
                               "completed 20+ minute continuous Android run", "population false-merge reliability"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"status": result["status"], "veche_pooled": pooled,
                      "source_files_checked": len(checked_sources), "report": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
