"""Prepare pinned, existing public DEV fixtures for the opt-in .solhigh APK.

No downloads, private recordings, device access, or model changes. Provision the
existing synthetic-ru and dialogue-benchmark fixtures first. Unexpected source
bytes or an existing different destination fail before any file is replaced.
"""
import hashlib
import io
import json
from pathlib import Path
import wave

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "aba.wav": "300e7ef28c6caf93395af9be07fd3df0a850cbe6797c8416bd57489aaec143a7",
    "syn3-clean.wav": "7b5d5f9c8d5a984d193c2a0e31afe5dc6e3c1fb068d9499d552f104c0a6c4ce9",
    "syn4-noise.wav": "939648072d210ef99b1d6b1866110997852a53239d63989b78cbb2b267a70d49",
    "silence.wav": "190415015d40eef0cd797e1b59ffe00846b01873050b12d44b3a216de3faa2a9",
    "acted-dev.wav": "61354eefab1ba60e41e54c2c34e6ddd1b60d99bc923a9b798f26004dd98b3861",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pcm_wav(pcm):
    output = io.BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        stream.writeframes(pcm)
    return output.getvalue()


def main():
    source = ROOT / ".local/synthetic-ru"
    data = {name: (source / name).read_bytes() for name in ("syn3-clean.wav", "syn4-noise.wav")}
    for name, content in data.items():
        require(digest(content) == EXPECTED[name], "Unexpected public source: " + name)
    reference = json.loads((source / "syn3-clean.reference.json").read_text(encoding="utf-8"))
    require(reference["audio_sha256"] == EXPECTED["syn3-clean.wav"], "Synthetic reference mismatch")
    with wave.open(io.BytesIO(data["syn3-clean.wav"]), "rb") as stream:
        require((stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) == (1, 2, 16000),
                "Expected mono PCM16 16 kHz")
        pcm = stream.readframes(stream.getnframes())
    parts = []
    for index in (0, 1, 5):
        turn = reference["text_segments"][index]
        parts.append(pcm[turn["start_ms"] * 32:min(turn["end_ms"] * 32, len(pcm))])
        parts.append(bytes(16000))  # 500 ms silence after each turn.
    data["aba.wav"] = pcm_wav(b"".join(parts))
    data["silence.wav"] = pcm_wav(bytes(8 * 16000 * 2))
    # Licensed acted DEV material, not independent natural conversation or human gold.
    data["acted-dev.wav"] = (ROOT / ".local/dialogue-benchmark/aba.wav").read_bytes()
    destination = ROOT / ".local/solHighTestAssets/sol-high"
    require(destination.resolve().is_relative_to((ROOT / ".local").resolve()), "Output escapes workspace")
    # Validate the whole input/output set before writing any fixture.
    for name, content in data.items():
        require(digest(content) == EXPECTED[name], "Fixture derivation/hash mismatch: " + name)
        target = destination / name
        require(not target.exists() or target.read_bytes() == content,
                "Refusing to replace a different existing fixture: " + name)
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in data.items():
        target = destination / name
        if not target.exists():
            with target.open("xb") as stream:
                stream.write(content)
    report = {"scope": "public_synthetic_and_licensed_acted_DEV_not_human_gold", "files": EXPECTED}
    (ROOT / ".local/honor-acceptance-fixtures.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "fixtures": len(data), "directory": ".local/solHighTestAssets/sol-high"}))


if __name__ == "__main__":
    main()
