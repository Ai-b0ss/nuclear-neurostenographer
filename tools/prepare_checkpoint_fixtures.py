"""Stage user-supplied QA fixtures; never download or commit recordings."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import wave

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--english-wav", type=Path, required=True)
    parser.add_argument("--russian-wavs", type=Path, nargs=4, required=True,
                        metavar=("CLEAN", "ABA", "ACTED", "FOUR_SPEAKERS"))
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    sources = [args.english_wav, *args.russian_wavs]
    names = ["english.wav", "russian.wav", "russian-aba.wav",
             "russian-acted.wav", "russian-syn4.wav"]
    # Validate everything before replacing any staged fixture.
    for path in sources:
        with wave.open(str(path), "rb") as audio:
            if not (audio.getsampwidth() == 2 and audio.getcomptype() == "NONE"
                    and 1 <= audio.getnchannels() <= 2
                    and 8000 <= audio.getframerate() <= 48000
                    and 0.3 <= audio.getnframes() / audio.getframerate() <= 1200):
                raise ValueError(f"Expected 0.3–1200 s PCM16 WAV: {path}")
    output = ROOT / ".local/englishTestAssets"
    output.mkdir(parents=True, exist_ok=True)
    for source, name in zip(sources, names):
        stage = output / (name + ".part")
        try:
            shutil.copyfile(source, stage)
            stage.replace(output / name)
        finally:
            stage.unlink(missing_ok=True)
    stage = output / "english.mp3.part"
    try:
        subprocess.run([args.ffmpeg, "-nostdin", "-v", "error", "-y",
                        "-i", str(output / "english.wav"), "-b:a", "64k",
                        "-f", "mp3", str(stage)], check=True)
        stage.replace(output / "english.mp3")
    finally:
        stage.unlink(missing_ok=True)
    manifest = {}
    for name in names + ["english.mp3"]:
        path = output / name
        with path.open("rb") as audio:
            manifest[name] = {"bytes": path.stat().st_size,
                              "sha256": hashlib.file_digest(audio, "sha256").hexdigest()}
    (output.parent / "checkpoint-fixtures.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Staged {len(manifest)} fixtures in {output}; recordings are not committed")


if __name__ == "__main__":
    main()
