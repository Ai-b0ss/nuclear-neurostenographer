"""Pinned, local-only research helpers for OpenSpeakerBeam-SS."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
import wave

ROOT = Path(__file__).resolve().parents[2]
LOCAL_ROOT = ROOT / ".local" / "speakerbeam-ss"
UPSTREAM_REPOSITORY = "https://github.com/helloooideeeeea/OpenSpeakerBeam-SS.git"
UPSTREAM_COMMIT = "bbbae73f74fc14eafdf7abb93f9094eafccd21df"
HF_DATASET = "helloidea/OpenSpeakerBeam-SS-dataset"
HF_REVISION = "82e6d7646126d1fa33b30c0b44f1d076496cca71"
CHECKPOINT_NAME = "best_model.pth"
CHECKPOINT_SHA256 = "41c250587af2e947dc3e265cd6e7aa7de230048d408e93c53d8348d63cf75896"
CHECKPOINT_SIZE = 33050566
CHECKPOINT_URL = (f"https://huggingface.co/datasets/{HF_DATASET}/resolve/{HF_REVISION}/"
                  f"checkpoints/{CHECKPOINT_NAME}")
DEFAULT_UPSTREAM = LOCAL_ROOT / "upstream"
DEFAULT_CHECKPOINT = LOCAL_ROOT / "checkpoints" / CHECKPOINT_NAME
REQUIRED_MODULES = ("torch", "torchaudio", "asteroid", "einops", "resemblyzer", "numpy")


class ResearchError(RuntimeError):
    pass


def sha256(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def download(url, destination, expected_sha256):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and sha256(destination) == expected_sha256:
        return
    temporary = destination.with_suffix(destination.suffix + ".part")
    try:
        urllib.request.urlretrieve(url, temporary)
        actual = sha256(temporary)
        if actual != expected_sha256:
            raise ResearchError(f"SHA-256 mismatch for {destination.name}: {actual}")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def validate_wav(path, role="audio"):
    path = Path(path)
    try:
        with wave.open(str(path), "rb") as audio:
            channels = audio.getnchannels()
            sample_width = audio.getsampwidth()
            sample_rate = audio.getframerate()
            frames = audio.getnframes()
    except (OSError, EOFError, wave.Error) as error:
        raise ResearchError(f"{role} must be a readable PCM WAV: {path}") from error
    if channels not in (1, 2):
        raise ResearchError(f"{role} must be mono or stereo, got {channels} channels")
    if sample_width != 2:
        raise ResearchError(f"{role} must be PCM16, got sample width {sample_width}")
    if sample_rate <= 0 or frames <= 0:
        raise ResearchError(f"{role} must have a positive sample rate and non-zero duration")
    return {
        "path": str(path.resolve()),
        "sha256": sha256(path),
        "channels": channels,
        "sample_width_bytes": sample_width,
        "sample_rate_hz": sample_rate,
        "frames": frames,
        "duration_ms": round(frames * 1000 / sample_rate, 3),
    }


def upstream_revision(upstream):
    try:
        result = subprocess.run(
            ["git", "-C", str(upstream), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ResearchError(f"Cannot read upstream revision: {upstream}") from error
    return result.stdout.strip()


def dependency_versions(python_executable):
    script = f"""
import importlib
import importlib.metadata
import json
result = {{}}
for name in {REQUIRED_MODULES!r}:
    module = importlib.import_module(name)
    try:
        result[name] = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        result[name] = getattr(module, '__version__', 'UNKNOWN')
import os
import tempfile
import wave
with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temporary:
    probe_path = temporary.name
try:
    with wave.open(probe_path, 'wb') as probe:
        probe.setnchannels(1)
        probe.setsampwidth(2)
        probe.setframerate(16000)
        probe.writeframes(b'\\x00\\x00' * 160)
    waveform, sample_rate = importlib.import_module('torchaudio').load(probe_path)
    assert waveform.shape == (1, 160) and sample_rate == 16000
    result['torchaudio_pcm16_load'] = 'PASS'
finally:
    os.unlink(probe_path)
print(json.dumps(result, sort_keys=True))
"""
    try:
        result = subprocess.run(
            [str(python_executable), "-c", script],
            check=True, capture_output=True, text=True, timeout=60,
        )
        return json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        raise ResearchError(f"Python dependencies unavailable: {detail.strip()}") from error


def preflight(upstream=DEFAULT_UPSTREAM, checkpoint=DEFAULT_CHECKPOINT,
              python_executable=sys.executable):
    upstream = Path(upstream)
    checkpoint = Path(checkpoint)
    checks = {}
    try:
        revision = upstream_revision(upstream)
        missing = [name for name in ("inference.py", "LICENSE", "model/__init__.py", "tools/__init__.py")
                   if not (upstream / name).is_file()]
        if revision != UPSTREAM_COMMIT or missing:
            raise ResearchError(f"Wrong upstream revision or missing files: {revision}, {missing}")
        checks["upstream"] = {"status": "PASS", "commit": revision}
    except ResearchError as error:
        checks["upstream"] = {"status": "FAIL", "reason": str(error)}
    try:
        if not checkpoint.is_file() or checkpoint.stat().st_size != CHECKPOINT_SIZE:
            raise ResearchError(f"Missing or wrong-size checkpoint: {checkpoint}")
        actual = sha256(checkpoint)
        if actual != CHECKPOINT_SHA256:
            raise ResearchError(f"Checkpoint SHA-256 mismatch: {actual}")
        checks["checkpoint"] = {"status": "PASS", "sha256": actual}
    except OSError as error:
        checks["checkpoint"] = {"status": "FAIL", "reason": str(error)}
    except ResearchError as error:
        checks["checkpoint"] = {"status": "FAIL", "reason": str(error)}
    try:
        checks["dependencies"] = {"status": "PASS", "versions": dependency_versions(python_executable)}
    except ResearchError as error:
        checks["dependencies"] = {"status": "FAIL", "reason": str(error)}
    return {
        "schema_version": 1,
        "status": "PASS" if all(item["status"] == "PASS" for item in checks.values()) else "FAIL",
        "checks": checks,
    }


def require_preflight(upstream, checkpoint, python_executable):
    report = preflight(upstream, checkpoint, python_executable)
    if report["status"] != "PASS":
        raise ResearchError(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return report


def validate_output(output, mixture, enrollment):
    output = Path(output).resolve()
    root = LOCAL_ROOT.resolve()
    if not output.is_relative_to(root):
        raise ResearchError(f"Research output must be inside {root}")
    if output.suffix.lower() != ".wav":
        raise ResearchError("Output must have .wav extension")
    if output in (Path(mixture).resolve(), Path(enrollment).resolve()):
        raise ResearchError("Output must not overwrite an input")
    return output


def build_command(python_executable, upstream, checkpoint, mixture, enrollment, output):
    return [
        str(python_executable), str(Path(upstream) / "inference.py"),
        "--mixture", str(mixture), "--enrollment", str(enrollment),
        "--output", str(output), "--checkpoint_dir", str(Path(checkpoint).parent),
        "--sample_rate", "16000",
    ]


def run_inference(mixture, enrollment, output, upstream=DEFAULT_UPSTREAM,
                  checkpoint=DEFAULT_CHECKPOINT, python_executable=sys.executable,
                  runner=subprocess.run):
    mixture_info = validate_wav(mixture, "mixture")
    enrollment_info = validate_wav(enrollment, "manual enrollment")
    output = validate_output(output, mixture, enrollment)
    report = require_preflight(upstream, checkpoint, python_executable)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.stem + ".partial.wav")
    temporary.unlink(missing_ok=True)
    command = build_command(python_executable, upstream, checkpoint,
                            Path(mixture).resolve(), Path(enrollment).resolve(), temporary)
    try:
        result = runner(command, check=True, capture_output=True, text=True, timeout=900)
        output_info = validate_wav(temporary, "A3 output")
        temporary.replace(output)
        output_info["path"] = str(output)
        return {
            "schema_version": 1,
            "status": "PASS",
            "adapter": "pinned-upstream-inference-v1",
            "upstream_commit": UPSTREAM_COMMIT,
            "checkpoint_sha256": CHECKPOINT_SHA256,
            "mixture": mixture_info,
            "manual_enrollment": enrollment_info,
            "a3_output": output_info,
            "preflight": report,
            "upstream_stdout": result.stdout.strip(),
        }
    except (OSError, subprocess.SubprocessError, ResearchError) as error:
        temporary.unlink(missing_ok=True)
        if isinstance(error, subprocess.CalledProcessError):
            detail = error.stderr or error.stdout or str(error)
            raise ResearchError(f"Upstream inference failed: {detail.strip()}") from error
        raise
