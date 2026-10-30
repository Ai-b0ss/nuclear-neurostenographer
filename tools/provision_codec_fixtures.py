"""Generate numeric tones, never speech, for Android codec import tests.

FFmpeg is a test-fixture tool on the runner, not an app library. No external audio
or model is downloaded. Files remain ignored; manifest records actual generator.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import wave

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--output", type=Path, default=ROOT / ".local/androidTestAssets/codecs")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    # Remove stale fixtures first: a generator failure must not leave old evidence.
    variants = {"tone.m4a": ["-c:a", "aac", "-b:a", "96k"],
                "tone.mp3": ["-c:a", "libmp3lame", "-b:a", "96k"],
                "tone-vorbis.ogg": ["-c:a", "libvorbis"],
                "tone-opus.ogg": ["-c:a", "libopus"],
                "tone.flac": ["-c:a", "flac"]}
    manifest = args.output / "manifest.json"
    rejected = {"two-tracks.m4a": ["-map", "0:a", "-map", "0:a", "-c:a", "aac"],
                "too-long.m4a": ["-t", "121", "-c:a", "aac", "-b:a", "32k"]}
    manifest.unlink(missing_ok=True)
    for name in variants | rejected:
        (args.output / name).unlink(missing_ok=True)
    version = subprocess.check_output([args.ffmpeg, "-version"], text=True).splitlines()[0]
    with tempfile.TemporaryDirectory(dir=args.output) as temp:
        source = Path(temp) / "numeric.wav"
        rate, frames = 44100, 55125  # 1.25 s, two distinct channels, no words or identities.
        with wave.open(str(source), "wb") as wav:
            wav.setparams((2, 2, rate, frames, "NONE", "not compressed"))
            data = bytearray()
            for frame in range(frames):
                data += struct.pack("<hh", *(round(8000 * math.sin(2 * math.pi * hz * frame / rate))
                                             for hz in (440, 880)))
            wav.writeframes(data)
        records = {}
        try:
            for name, options in variants.items():
                output = args.output / name
                subprocess.run([args.ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                                "-i", str(source), "-map_metadata", "-1", *options, str(output)],
                               check=True, timeout=30)
                records[name] = {"sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                                 "bytes": output.stat().st_size}
            failures = {}
            for name, options in rejected.items():
                output = args.output / name
                loop = ["-stream_loop", "-1"] if name == "too-long.m4a" else []
                subprocess.run([args.ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                                *loop, "-i", str(source), "-map_metadata", "-1", *options, str(output)],
                               check=True, timeout=30)
                failures[name] = {"sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                                  "bytes": output.stat().st_size}
            manifest.write_text(json.dumps({"kind": "GENERATED_NUMERIC_TONES_NOT_SPEECH",
                "ffmpeg": version, "rate": rate, "channels": 2, "source_duration_ms": 1250,
                "source_pcm_sha256": hashlib.sha256(data).hexdigest(), "files": records,
                "reject_files": failures}, indent=2) + "\n")
        except BaseException:
            for name in variants | rejected:
                (args.output / name).unlink(missing_ok=True)
            raise
    print(manifest)


if __name__ == "__main__":
    main()
