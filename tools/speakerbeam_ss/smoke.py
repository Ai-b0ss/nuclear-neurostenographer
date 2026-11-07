"""Run a synthetic mechanical smoke, never a quality or performance benchmark."""
import json
import math
from pathlib import Path
import struct
import sys
import wave

from research import DEFAULT_CHECKPOINT, DEFAULT_UPSTREAM, LOCAL_ROOT, run_inference, sha256

SAMPLE_RATE = 16000


def write_tone(path, frequencies):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for index in range(SAMPLE_RATE * 2):
            value = sum(math.sin(2 * math.pi * frequency * index / SAMPLE_RATE)
                        for frequency in frequencies) / len(frequencies)
            frames.extend(struct.pack("<h", round(value * 12000)))
        output.writeframes(frames)


def main():
    root = LOCAL_ROOT / "smoke"
    mixture = root / "authored-mixture.wav"
    enrollment = root / "authored-manual-enrollment.wav"
    write_tone(mixture, (220, 440))
    write_tone(enrollment, (220,))
    outputs = []
    for name in ("a3-first.wav", "a3-second.wav"):
        output = root / name
        result = run_inference(mixture, enrollment, output,
                               DEFAULT_UPSTREAM, DEFAULT_CHECKPOINT, sys.executable)
        (root / (output.stem + ".json")).write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        outputs.append(output)
    deterministic = sha256(outputs[0]) == sha256(outputs[1])
    summary = {
        "schema_version": 1,
        "status": "PASS",
        "kind": "AUTHORED_SYNTHETIC_UPSTREAM_SMOKE",
        "quality_or_performance_benchmark": False,
        "datahive": False,
        "byte_deterministic": deterministic,
        "output_sha256": [sha256(path) for path in outputs],
    }
    rendered = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    (root / "smoke.json").write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if deterministic else 2


if __name__ == "__main__":
    raise SystemExit(main())
