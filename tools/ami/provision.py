"""Freeze a four-speaker AMI meeting excerpt for Android diarization evaluation.

Source is the official AMI manual v1.6.2 archive and Mix-Headset WAV. The
360-600 second cut was selected from annotation coverage before inference.
Outputs live under ignored .local/; no corpus audio is committed.
"""
from __future__ import annotations

import hashlib
import json
import wave
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / ".local/ami-source"
DEST = ROOT / ".local/androidTestAssets/ami-meeting"
START, END = 360, 600
ARCHIVE = "ami_public_manual_1.6.2.zip"
MEETINGS = {
    "ES2004a": "3e2560b19bee6952c7c7ce041b0f1ea8a7ea9468044c4eea79d2a2c67e24ab0f",
    "IS1009a": "6eb5a0ede0d9e72794f976ce7bea5b78133eae969f99b4c5418b43c2468d25b1",
}
HASHES = {
    ARCHIVE: "b56e5babb2496b8795deeeda7e71178d7fbc9963f94276cf2a3f4b56ebbc9f9d",
    **{f"{meeting}.Mix-Headset.wav": digest for meeting, digest in MEETINGS.items()},
}
URLS = {
    ARCHIVE: "https://groups.inf.ed.ac.uk/ami/AMICorpusAnnotations/ami_public_manual_1.6.2.zip",
    **{f"{meeting}.Mix-Headset.wav":
       f"https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus/{meeting}/audio/{meeting}.Mix-Headset.wav"
       for meeting in MEETINGS},
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    import urllib.request

    SOURCE.mkdir(parents=True, exist_ok=True)
    DEST.mkdir(parents=True, exist_ok=True)
    for name, expected in HASHES.items():
        path = SOURCE / name
        if not path.exists():
            urllib.request.urlretrieve(URLS[name], path)
        if sha(path) != expected:
            raise ValueError(f"Unexpected source hash: {path}")
    with zipfile.ZipFile(SOURCE / ARCHIVE) as archive:
        for meeting in MEETINGS:
            wav = f"{meeting}.Mix-Headset.wav"
            output = DEST / f"{meeting}-{START}-{END}.wav"
            with wave.open(str(SOURCE / wav), "rb") as src:
                if (src.getnchannels(), src.getsampwidth(), src.getframerate()) != (1, 2, 16000):
                    raise ValueError("Unexpected AMI mix format")
                src.setpos(START * 16000)
                frames = src.readframes((END - START) * 16000)
                with wave.open(str(output), "wb") as dst:
                    dst.setnchannels(1)
                    dst.setsampwidth(2)
                    dst.setframerate(16000)
                    dst.writeframes(frames)
            if len(frames) != (END - START) * 16000 * 2:
                raise ValueError("Truncated AMI excerpt")
            turns = []
            for speaker in "ABCD":
                member = f"segments/{meeting}.{speaker}.segments.xml"
                root = ET.fromstring(archive.read(member))
                for segment in root.findall("segment"):
                    a = round(float(segment.attrib["transcriber_start"]) * 1000)
                    b = round(float(segment.attrib["transcriber_end"]) * 1000)
                    a, b = max(a, START * 1000), min(b, END * 1000)
                    if b > a:
                        turns.append({"start_ms": a - START * 1000,
                                      "end_ms": b - START * 1000,
                                      "speaker_id": speaker})
            turns.sort(key=lambda t: (t["start_ms"], t["end_ms"], t["speaker_id"]))
            reference = {
                "schema_version": 1,
                "recording_id": f"AMI-{meeting}-{START}-{END}-Mix-Headset",
                "annotation_source": URLS[ARCHIVE] + f"#segments/{meeting}.{{A,B,C,D}}.segments.xml",
                "license": "CC BY 4.0",
                "kind": "real four-speaker English meeting, headset mix",
                "audio_sha256": sha(output),
                "audio_duration_ms": (END - START) * 1000,
                "diarization": turns,
                "source_sha256": {ARCHIVE: HASHES[ARCHIVE], wav: HASHES[wav]},
                "source_urls": {ARCHIVE: URLS[ARCHIVE], wav: URLS[wav]},
                "cut_seconds": [START, END],
            }
            (DEST / f"{meeting}-{START}-{END}.reference.json").write_text(
                json.dumps(reference, ensure_ascii=False, indent=2) + "\n")
            print(output, reference["audio_sha256"], len(turns), "manual turns")


if __name__ == "__main__":
    main()
