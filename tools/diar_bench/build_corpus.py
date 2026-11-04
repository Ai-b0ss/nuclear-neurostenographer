"""Build the frozen C0/C1 corpus from pinned sources. Audio and references stay outside Git.

Selection rules are fixed here, before any model output is looked at:
  rubook  k=2,3,4: first 8 per k by SHA-256("c0c1|id"); first 4 of k=2,3 again with white noise at
          SNR 10 and 0 dB; 3 highest-overlap remaining files per k.
  ivkond  shard 0, 2-4 speakers: first 5 by hash per (speakers, has_overlaps) where available, at most 20.
  datahive every conversation, seconds 30-150, stereo downmixed to mono by ffmpeg; the reference comes
          from Silero VAD on each separate channel: not human annotation.
  nonspeech 60 s digital silence and 60 s white noise at -30 dBFS (false-alarm checks only).
  acted   the repository's pinned development D-M-D clip, if supplied; text and clip order only.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

import numpy as np
import onnxruntime as ort
import pyarrow.parquet as pq
import soundfile as sf

RATE = 16000
SEED = "c0c1"
VAD = {"threshold": 0.5, "negative_threshold": 0.35, "min_speech_ms": 250, "min_silence_ms": 200, "pad_ms": 30}


def order_key(identifier):
    return hashlib.sha256(f"{SEED}|{identifier}".encode()).hexdigest()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def der_reference_problem(turns, audio, rate=RATE):
    """Why a turn list cannot serve as a DER reference, or None. Compares labels with frame energy."""
    if not turns:
        return "no turns"
    frame = rate // 50
    count = len(audio) // frame
    rms = np.sqrt(np.mean(audio[:count * frame].reshape(count, frame) ** 2, axis=1) + 1e-12)
    active = rms > max(1e-3, 0.1 * np.percentile(rms, 95))
    labelled = np.zeros(count, dtype=bool)
    for t in turns:
        labelled[t["start_ms"] // 20:t["end_ms"] // 20] = True
    coverage, excess = float(labelled.mean()), float((labelled & ~active).sum() / max(int(labelled.sum()), 1))
    if coverage >= 0.96 and excess > 0.33:
        return f"labels covers {coverage:.0%} of the file while {excess:.0%} of labelled frames have no energy"
    return None


def write_case(out, case_id, audio, group, scenario, kind, source, license_name, annotation, turns, text=None, extra=None):
    problem = der_reference_problem(turns, audio) if turns else None
    wav = out / f"{case_id}.wav"
    sf.write(wav, np.clip(audio, -1, 1), RATE, subtype="PCM_16")
    digest = sha256(wav)
    duration = round(len(audio) * 1000 / RATE)
    reference = {"schema_version": 1, "recording_id": case_id, "annotation_source": annotation,
                 "license": license_name, "kind": kind, "audio_sha256": digest, "audio_duration_ms": duration}
    # A rejected turn list never reaches the scorer, so no report can call it SCORED.
    if turns and not problem:
        reference["diarization"] = turns
    if text:
        reference["text_segments"] = text
    (out / f"{case_id}.ref.json").write_text(json.dumps(reference, ensure_ascii=False), encoding="utf-8")
    speakers = sorted({t["speaker_id"] for t in (turns or text or [])})
    entry = {"id": case_id, "group": group, "scenario": scenario, "kind": kind, "source": source, "license": license_name,
             "annotation": annotation, "audio_sha256": digest, "duration_ms": duration, "speakers": len(speakers),
             "reference_sha256": sha256(out / f"{case_id}.ref.json"), "der_reference_problem": problem}
    entry.update(extra or {})
    return entry


def rttm_turns(text, duration):
    turns = []
    for line in text.splitlines():
        fields = line.split()
        if fields and fields[0] == "SPEAKER":
            start, end = round(float(fields[3]) * 1000), round((float(fields[3]) + float(fields[4])) * 1000)
            end = min(end, duration)
            if end > start:
                turns.append({"start_ms": start, "end_ms": end, "speaker_id": fields[7]})
    return turns


def white_at_snr(audio, snr_db, seed):
    voiced = audio[np.abs(audio) > 1e-4]
    noise = np.random.default_rng(int(seed[:8], 16)).standard_normal(len(audio))
    scale = np.sqrt(np.mean(voiced ** 2) / 10 ** (snr_db / 10))
    return audio + (noise * scale).astype(np.float32)


def build_rubook(raw, out):
    manifest = [json.loads(line) for line in (raw / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if line]
    chosen, noisy, overlap = {}, {}, {}
    for k in (2, 3, 4):
        items = sorted((m for m in manifest if m["n_speakers"] == k), key=lambda m: order_key(m["file_id"]))
        for m in items[:8]:
            chosen[m["file_id"]] = m
        if k < 4:
            for m in items[:4]:
                noisy[m["file_id"]] = m
        rest = sorted(items[8:], key=lambda m: (-m["overlap_stats"]["overlap2"], order_key(m["file_id"])))
        for m in rest[:3]:
            overlap[m["file_id"]] = m
    wanted = {**chosen, **overlap}
    cases = []
    for shard in sorted((raw).glob("shard-*.tar")):
        with tarfile.open(shard) as tar:
            members = {m.name: m for m in tar.getmembers()}
            for file_id, m in sorted(wanted.items()):
                if f"{file_id}.flac" not in members:
                    continue
                audio, rate = sf.read(io.BytesIO(tar.extractfile(members[f"{file_id}.flac"]).read()), dtype="float32")
                if rate != RATE:
                    raise ValueError(file_id)
                rttm = tar.extractfile(members[f"{file_id}.rttm"]).read().decode()
                duration = round(len(audio) * 1000 / RATE)
                turns = rttm_turns(rttm, duration)
                common = dict(group="rubook", kind="SYNTHETIC_MIX_AUDIOBOOK_GENERATOR_RTTM",
                              source=f"mexus/ru-book-mix-10h:{file_id}", license_name="CC-BY-4.0",
                              annotation="Generator RTTM; independent of C0/C1; audiobook mix", turns=turns)
                extra = {"overlap2": m["overlap_stats"]["overlap2"]}
                scenario = "high_overlap" if file_id in overlap else f"clean_{m['n_speakers']}spk"
                cases.append(write_case(out, f"rubook-{file_id}", audio, scenario=scenario, extra=extra, **common))
                if file_id in noisy:
                    for snr in (10, 0):
                        cases.append(write_case(out, f"rubook-{file_id}-white{snr}db", white_at_snr(audio, snr, order_key(file_id)),
                                                scenario=f"noise_{snr}db", extra={**extra, "added_noise": "white"}, **common))
    return cases


def build_ivkond(raw, out):
    table = pq.read_table(raw / "shard0.parquet").to_pylist()
    rows = [(i, r) for i, r in enumerate(table) if 2 <= r["num_speakers"] <= 4]
    rows.sort(key=lambda x: order_key(f"ivkond{x[0]}"))
    picked, counts = [], {}
    for i, r in rows:
        key = (r["num_speakers"], r["has_overlaps"])
        if counts.get(key, 0) < 5 and len(picked) < 20:
            counts[key] = counts.get(key, 0) + 1
            picked.append((i, r))
    cases = []
    for i, r in picked:
        cell = r["audio"]
        if cell.get("bytes"):
            audio, rate = sf.read(io.BytesIO(cell["bytes"]), dtype="float32")
        else:
            audio, rate = np.asarray(cell["array"], dtype=np.float32), cell["sampling_rate"]
        if rate != RATE or audio.ndim != 1:
            raise ValueError(f"ivkond row {i}")
        duration = round(len(audio) * 1000 / RATE)
        text = [{"start_ms": round(s["start"] * 1000), "end_ms": min(round(s["end"] * 1000), duration),
                 "speaker_id": f"s{s['speaker_id']}", "text": s["text"]}
                for s in r["speakers"] if round(s["start"] * 1000) < min(round(s["end"] * 1000), duration)]
        turns = [{k: t[k] for k in ("start_ms", "end_ms", "speaker_id")} for t in text]
        cases.append(write_case(out, f"ivkond-{i:04d}", audio, "ivkond", f"text_{r['num_speakers']}spk",
                                "SYNTHETIC_DATASET_LABELS", f"ivkond/synthetic-speech-diarization-ru:shard0:{i}",
                                "MIT per card; voice origin undocumented", "Dataset labels; turn level, not word level",
                                turns, text=text, extra={"has_overlaps": bool(r["has_overlaps"]), "has_noise": bool(r["has_noise"]),
                                                         "difficulty": r["difficulty"]}))
    return cases


class Silero:
    def __init__(self, path):
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        self.session = ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])

    def probabilities(self, audio):
        window = 512
        h, c = np.zeros((2, 1, 64), dtype=np.float32), np.zeros((2, 1, 64), dtype=np.float32)
        probs = []
        for start in range(0, len(audio) - window + 1, window):
            prob, h, c = self.session.run(None, {"x": audio[start:start + window][None, :], "h": h, "c": c})
            probs.append(float(np.ravel(prob)[0]))
        return np.array(probs), window * 1000 / RATE


def segments_from_probs(probs, frame_ms, duration):
    segments, start, last_voice = [], None, None
    for i, p in enumerate(probs):
        t = i * frame_ms
        if start is None:
            if p >= VAD["threshold"]:
                start, last_voice = t, t + frame_ms
        elif p >= VAD["negative_threshold"]:
            last_voice = t + frame_ms
        elif t - last_voice >= VAD["min_silence_ms"]:
            segments.append((start, last_voice))
            start = None
    if start is not None:
        segments.append((start, last_voice))
    result = []
    for a, b in segments:
        if b - a >= VAD["min_speech_ms"]:
            result.append((max(0, round(a - VAD["pad_ms"])), min(duration, round(b + VAD["pad_ms"]))))
    return result


def decode(ffmpeg, path, channels, start, seconds):
    command = [ffmpeg, "-v", "error", "-ss", str(start), "-t", str(seconds), "-i", str(path), "-ar", str(RATE)]
    if channels == 1:
        command += ["-ac", "1"]
    command += ["-f", "f32le", "-"]
    data = subprocess.run(command, capture_output=True, check=True).stdout
    audio = np.frombuffer(data, dtype=np.float32)
    return audio if channels == 1 else audio.reshape(-1, 2)


def build_datahive(raw, out, silero_path, ffmpeg):
    silero = Silero(silero_path)
    meta = {json.loads(l)["file_name"]: json.loads(l) for l in (raw / "metadata.jsonl").read_text(encoding="utf-8").splitlines() if l}
    cases = []
    for name in sorted(meta):
        channels = decode(ffmpeg, raw / name, 2, 30, 120)
        mono = decode(ffmpeg, raw / name, 1, 30, 120)
        duration = round(len(mono) * 1000 / RATE)
        turns = []
        for index, label in enumerate(("caller", "callee")):
            probs, frame_ms = silero.probabilities(channels[:, index].copy())
            turns += [{"start_ms": a, "end_ms": b, "speaker_id": label} for a, b in segments_from_probs(probs, frame_ms, duration)]
        turns.sort(key=lambda t: t["start_ms"])
        left, right = channels[:, 0], channels[:, 1]
        cases.append(write_case(out, f"datahive-{Path(name).stem}", mono, "datahive", "natural_call",
                                "NATURAL_TWO_CHANNEL_CALL_VAD_REFERENCE_NOT_HUMAN", f"datahiveai/russian-conversations-sample:{name}:30-150s",
                                "CC-BY-4.0 attribution DataHive", f"Silero VAD per channel {VAD}; no human check", turns,
                                extra={"channel_correlation": float(np.corrcoef(left, right)[0, 1]), "metadata_overlap_percent": meta[name]["overlap_percent"]}))
    return cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--acted", type=Path, help="Folder with aba.wav and reference.json from provision_dialogue_benchmark.py")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    out = args.data / "corpus"
    out.mkdir(parents=True, exist_ok=True)
    cases = build_rubook(args.data / "raw/rubook", out)
    cases += build_ivkond(args.data / "raw/ivkond", out)
    cases += build_datahive(args.data / "raw/datahive", out, args.data / "models/silero/silero_vad.onnx", args.ffmpeg)
    n = 60 * RATE
    cases.append(write_case(out, "nonspeech-silence", np.zeros(n, dtype=np.float32), "nonspeech", "silence", "GENERATED_NO_SPEECH",
                            "generated", "generated", "Generated; no speech by construction", []))
    noise = np.random.default_rng(1234).standard_normal(n).astype(np.float32) * 10 ** (-30 / 20)
    cases.append(write_case(out, "nonspeech-whitenoise", noise, "nonspeech", "white_noise", "GENERATED_NO_SPEECH",
                            "generated", "generated", "Generated; no speech by construction", []))
    if args.acted:
        reference = json.loads((args.acted / "reference.json").read_text(encoding="utf-8"))
        if sha256(args.acted / "aba.wav") != reference["audio_sha256"]:
            raise ValueError("Acted clip hash mismatch")
        # The source clip is 44.1 kHz: both systems get one identical 16 kHz copy.
        subprocess.run([args.ffmpeg, "-v", "error", "-y", "-i", str(args.acted / "aba.wav"), "-ar", str(RATE), "-ac", "1",
                        "-bitexact", "-c:a", "pcm_s16le", str(out / "acted-dmd.wav")], check=True)
        reference.update(recording_id="acted-dmd", audio_sha256=sha256(out / "acted-dmd.wav"),
                         audio_duration_ms=round(sf.info(out / "acted-dmd.wav").frames * 1000 / RATE))
        for segment in reference["text_segments"]:
            segment["end_ms"] = min(segment["end_ms"], reference["audio_duration_ms"])
        (out / "acted-dmd.ref.json").write_text(json.dumps(reference, ensure_ascii=False), encoding="utf-8")
        cases.append({"id": "acted-dmd", "group": "acted", "scenario": "aba_acted", "kind": reference["kind"],
                      "source": "langswap/dialogs-ru-emotional-conversations (repository dev clip; threshold 0.8 was tuned on it)",
                      "license": reference["license"], "annotation": "Scripted text, clip order", "audio_sha256": reference["audio_sha256"],
                      "duration_ms": reference["audio_duration_ms"], "speakers": 2,
                      "reference_sha256": sha256(out / "acted-dmd.ref.json")})
    args.evidence.mkdir(parents=True, exist_ok=True)
    (args.evidence / "corpus-manifest.json").write_text(json.dumps(
        {"schema_version": 1, "selection_seed": SEED, "vad": VAD, "sample_rate": RATE, "cases": cases}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    total = sum(c["duration_ms"] for c in cases) / 60000
    print(f"cases={len(cases)} minutes={total:.1f}")


if __name__ == "__main__":
    main()
