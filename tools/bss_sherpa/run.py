"""Isolated host-only UVR negative control; no Android production assets are used.

python -I tools/bss_sherpa/run.py fetch --model .local/bss-sherpa/UVR-MDX-NET-Voc_FT.onnx
python -I tools/bss_sherpa/run.py preflight --model .local/bss-sherpa/UVR-MDX-NET-Voc_FT.onnx
python -I tools/bss_sherpa/run.py separate --model .local/bss-sherpa/UVR-MDX-NET-Voc_FT.onnx --input mixture.wav --output .local/bss-sherpa/tracks
python -I tools/bss_sherpa/run.py validate --tracks .local/bss-sherpa/tracks
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
from datetime import datetime, timezone
import urllib.request
import wave

SCHEMA = "issue10-bss-sherpa/v1"
TRACK_SCHEMA = "issue10-bss-tracks/v1"
LOCK_PATH = Path(__file__).resolve().with_name("upstream-lock.json")
TRACK_NAMES = ("vocals", "accompaniment")


def load_lock():
    return json.loads(LOCK_PATH.read_text(encoding="utf-8"))


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(path):
    path = Path(path)
    return {"bytes": path.stat().st_size, "sha256": sha256(path)}


def verify_file(path, expected):
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"missing file: {path}")
    actual = file_record(path)
    if actual["bytes"] != expected["bytes"] or actual["sha256"] != expected["sha256"]:
        raise ValueError(f"size/SHA-256 mismatch: {path}")
    return actual


def native_model_path(path):
    resolved = str(Path(path).resolve())
    if os.name != "nt":
        return resolved
    try:
        resolved.encode("ascii")
        return resolved
    except UnicodeEncodeError:
        pass
    import ctypes
    length = ctypes.windll.kernel32.GetShortPathNameW(resolved, None, 0)
    if length == 0:
        raise ctypes.WinError()
    buffer = ctypes.create_unicode_buffer(length)
    if ctypes.windll.kernel32.GetShortPathNameW(resolved, buffer, length) == 0:
        raise ctypes.WinError()
    return buffer.value


def fetch_model(destination):
    spec = load_lock()["model"]
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")
    try:
        with urllib.request.urlopen(spec["url"], timeout=120) as response, temporary.open("wb") as out:
            shutil.copyfileobj(response, out)
        verify_file(temporary, spec)
        if destination.exists():
            raise FileExistsError(f"refusing to replace existing model: {destination}")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {"status": "PASS", "model": str(destination), **file_record(destination)}


def preflight(model):
    lock = load_lock()
    runtime = lock["runtime"]
    report = {
        "schema_version": SCHEMA,
        "issue": 10,
        "candidate": lock["candidate"],
        "status": "PASS",
        "decision": "HOST_NEGATIVE_CONTROL_READY",
        "checks": {},
    }
    try:
        report["checks"]["model"] = {"status": "PASS", **verify_file(model, lock["model"])}
    except (OSError, ValueError) as error:
        report["checks"]["model"] = {"status": "FAIL", "error": str(error)}
        report["status"] = "FAIL"
        report["decision"] = "BLOCKED"
        return report
    try:
        from importlib.metadata import version
        import numpy
        import sherpa_onnx
        versions = {"sherpa_onnx": sherpa_onnx.__version__, "sherpa_onnx_core": version("sherpa-onnx-core"),
            "numpy": numpy.__version__}
        expected = {"sherpa_onnx": runtime["version"], "sherpa_onnx_core": runtime["core_version"],
            "numpy": runtime["numpy"]["version"]}
        api = all(hasattr(sherpa_onnx, name) for name in (
            "OfflineSourceSeparation", "OfflineSourceSeparationConfig",
            "OfflineSourceSeparationModelConfig", "OfflineSourceSeparationUvrModelConfig"))
        if versions != expected or not api:
            raise ValueError(f"runtime/API mismatch: versions={versions}, source_separation_api={api}")
        report["checks"]["runtime"] = {"status": "PASS", **versions, "source_separation_api": True,
            "host_only": True, "production_runtime_changed": False}
    except (ImportError, AttributeError, ValueError) as error:
        report["checks"]["runtime"] = {"status": "FAIL", "error": str(error)}
        report["status"] = "FAIL"
        report["decision"] = "BLOCKED"
    return report


def read_wav(path, require_stereo=False):
    path = Path(path)
    with wave.open(str(path), "rb") as stream:
        channels = stream.getnchannels()
        sample_rate = stream.getframerate()
        sample_width = stream.getsampwidth()
        frames = stream.getnframes()
        compression = stream.getcomptype()
        raw = stream.readframes(frames)
    if sample_width != 2 or compression != "NONE":
        raise ValueError("only uncompressed PCM16 WAV is accepted")
    if sample_rate != 44100:
        raise ValueError(f"UVR requires 44100 Hz input, got {sample_rate}")
    if channels not in (1, 2) or (require_stereo and channels != 2):
        raise ValueError(f"expected {'stereo' if require_stereo else 'mono/stereo'} input, got {channels} channels")
    if frames <= 0 or len(raw) != frames * channels * 2:
        raise ValueError("empty or truncated WAV")
    import numpy as np
    samples = np.frombuffer(raw, dtype="<i2").reshape(frames, channels).astype(np.float32).T / 32768.0
    if channels == 1:
        samples = np.concatenate((samples, samples), axis=0)
    return np.ascontiguousarray(samples), sample_rate


def write_wav(path, samples, sample_rate):
    import numpy as np
    samples = np.asarray(samples, dtype=np.float32)
    if samples.ndim != 2 or samples.shape[0] != 2 or samples.shape[1] == 0:
        raise ValueError(f"expected non-empty stereo [channels, samples], got {samples.shape}")
    if sample_rate != 44100 or not np.isfinite(samples).all():
        raise ValueError("invalid output sample rate or non-finite samples")
    pcm = (np.clip(samples.T, -1.0, 1.0) * 32767.0).round().astype("<i2")
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        stream.writeframes(pcm.tobytes())


def make_fixture(path):
    import numpy as np
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"refusing to replace existing fixture: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    t = np.arange(44100, dtype=np.float32) / 44100
    samples = np.stack((0.20 * np.sin(2 * np.pi * 220 * t) + 0.10 * np.sin(2 * np.pi * 330 * t),
        0.15 * np.sin(2 * np.pi * 330 * t) + 0.08 * np.sin(2 * np.pi * 440 * t)))
    write_wav(path, samples, 44100)
    return {"schema_version": SCHEMA, "issue": 10, "status": "PASS",
        "decision": "SYNTHETIC_TECHNICAL_FIXTURE_ONLY", "file": str(path),
        "kind": "GENERATED_NUMERIC_TONES_NOT_SPEECH", **file_record(path)}


def tracks_manifest(output, input_path, elapsed_seconds):
    lock = load_lock()
    tracks = []
    for name in TRACK_NAMES:
        path = output / f"{name}.wav"
        samples, sample_rate = read_wav(path, require_stereo=True)
        tracks.append({"name": name, "file": path.name, "sample_rate": sample_rate,
            "channels": 2, "frames": samples.shape[1], **file_record(path)})
    return {
        "schema_version": TRACK_SCHEMA,
        "status": "PASS",
        "decision": "A3_HANDOFF_READY_NOT_RUN",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "kind": "MUSIC_VOCAL_NEGATIVE_CONTROL_NOT_SPEAKER_SEPARATION",
        "source": {"file": Path(input_path).name, **file_record(input_path)},
        "runtime": {"sherpa_onnx": lock["runtime"]["version"], "host_only": True},
        "model": {"filename": lock["model"]["filename"], "sha256": lock["model"]["sha256"]},
        "elapsed_seconds": round(elapsed_seconds, 6),
        "tracks": tracks,
        "a3": {"status": "NOT_RUN", "wer": None, "honor": None,
            "reason": "Shared real DataHive fragments and A3 references are not ready."},
    }


def validate_tracks(output):
    output = Path(output)
    manifest_path = output / "tracks.json"
    if not manifest_path.is_file():
        raise ValueError(f"missing {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != TRACK_SCHEMA or manifest.get("status") != "PASS":
        raise ValueError("unsupported or failed track manifest")
    if manifest.get("kind") != "MUSIC_VOCAL_NEGATIVE_CONTROL_NOT_SPEAKER_SEPARATION":
        raise ValueError("track semantics changed: this is not speaker separation")
    if manifest.get("model", {}).get("sha256") != load_lock()["model"]["sha256"]:
        raise ValueError("track manifest model differs from the pinned model")
    if manifest.get("a3") != {"status": "NOT_RUN", "wer": None, "honor": None,
            "reason": "Shared real DataHive fragments and A3 references are not ready."}:
        raise ValueError("unsubstantiated A3/HONOR/WER result in track manifest")
    tracks = manifest.get("tracks")
    if not isinstance(tracks, list) or [track.get("name") for track in tracks] != list(TRACK_NAMES):
        raise ValueError("expected exactly vocals and accompaniment tracks")
    frames = set()
    for track in tracks:
        if Path(track["file"]).name != track["file"] or track["file"] != f"{track['name']}.wav":
            raise ValueError("unsafe or unexpected track path")
        path = output / track["file"]
        verify_file(path, track)
        samples, sample_rate = read_wav(path, require_stereo=True)
        if sample_rate != track["sample_rate"] or samples.shape[1] != track["frames"]:
            raise ValueError(f"WAV metadata mismatch: {path}")
        frames.add(samples.shape[1])
    if len(frames) != 1:
        raise ValueError("stem lengths differ")
    return {"schema_version": SCHEMA, "issue": 10, "status": "PASS",
        "decision": manifest["decision"], "tracks": TRACK_NAMES, "frames": frames.pop()}


def separate(model, input_path, output, threads):
    check = preflight(model)
    if check["status"] != "PASS":
        raise RuntimeError(json.dumps(check, ensure_ascii=False))
    import numpy as np
    import sherpa_onnx
    samples, sample_rate = read_wav(input_path)
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"refusing to replace existing output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent))
    try:
        config = sherpa_onnx.OfflineSourceSeparationConfig(
            model=sherpa_onnx.OfflineSourceSeparationModelConfig(
                uvr=sherpa_onnx.OfflineSourceSeparationUvrModelConfig(model=native_model_path(model)),
                num_threads=threads, debug=False, provider="cpu"))
        if not config.validate():
            raise ValueError("sherpa-onnx rejected source separation config")
        separator = sherpa_onnx.OfflineSourceSeparation(config)
        started = time.perf_counter()
        result = separator.process(sample_rate=sample_rate, samples=np.ascontiguousarray(samples))
        elapsed = time.perf_counter() - started
        if len(result.stems) != 2 or result.sample_rate != 44100:
            raise ValueError("unexpected UVR output stems or sample rate")
        for name, stem in zip(TRACK_NAMES, result.stems):
            if stem.data.shape != samples.shape:
                raise ValueError(f"unexpected {name} shape: {stem.data.shape} != {samples.shape}")
            write_wav(temporary / f"{name}.wav", stem.data, result.sample_rate)
        manifest = tracks_manifest(temporary, input_path, elapsed)
        (temporary / "tracks.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        validate_tracks(temporary)
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return validate_tracks(output) | {"elapsed_seconds": round(elapsed, 6), "output": str(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("fetch", "preflight"):
        command = commands.add_parser(name)
        command.add_argument("--model", type=Path, required=True)
    run = commands.add_parser("separate")
    run.add_argument("--model", type=Path, required=True)
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--threads", type=int, default=2, choices=range(1, 17))
    check = commands.add_parser("validate")
    check.add_argument("--tracks", type=Path, required=True)
    fixture = commands.add_parser("make-fixture")
    fixture.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "fetch":
        result = fetch_model(args.model)
    elif args.command == "preflight":
        result = preflight(args.model)
    elif args.command == "separate":
        result = separate(args.model, args.input, args.output, args.threads)
    elif args.command == "make-fixture":
        result = make_fixture(args.output)
    else:
        result = validate_tracks(args.tracks)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
