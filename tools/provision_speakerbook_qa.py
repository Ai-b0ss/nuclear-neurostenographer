"""Reproducible public inputs for off-device QA. No ADB or physical device access."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import wave
import zipfile

from provision_asr import ROOT, download
from run_host_inference import COMPILER, MAVEN
from evaluate_russian_bookmix_voice_link import SHA_TITANET

DATA = ROOT / ".local/speakerbook-active/scratch/ru_book_mix_eval"
TITANET = ROOT / ".local/speakerbook-active/scratch/models/nemo_en_titanet_small.onnx"
HARNESS = ROOT / ".local/speakerbook-host-harness"
A3_REV = "6888903da215c7735f51101d939f3bfa679fb2b8"
A3_ENCODER_SOURCE = "2cac62d0c270bd128f898f2be1a2d34780d524a6e9483888ebac7b00f97410f1"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def compose_fixtures(data, output):
    import numpy as np
    import soundfile as sf
    manifest = json.loads((data / "local_manifest.json").read_text(encoding="utf8"))
    if manifest["source_manifest_sha256"] != "2f1e26fe123afe43e76b96cd49fd62e75bdb94c2f056c1fc7fa43c981de46a6c":
        raise ValueError("Unrecognized fixture source manifest")
    rows = manifest["records"][55:70]
    # Deliberate functional positive control, not an independent accuracy sample.
    # rec_0055 has no admitted TitaNet profiles; it cannot test successful linking.
    first = next(x for x in rows if x["file_id"] == "rec_0058")
    voices = set(first["source_voice_labels"].values())
    other = next(x for x in rows[rows.index(first)+1:] if not voices & set(x["source_voice_labels"].values()))
    def read(row):
        path = data / (row["file_id"] + ".flac")
        if digest(path) != row["files"][".flac"]["sha256"]:
            raise ValueError("Fixture source checksum mismatch")
        pcm, rate = sf.read(path, dtype="int16")
        if rate != 16000 or pcm.ndim != 1 or len(pcm) != 960000:
            raise ValueError("Unexpected fixture source format")
        return pcm
    source, negative = read(first), read(other)
    output.mkdir(parents=True, exist_ok=True)
    samples = {
        "speakerbook_repeat_after_5min.wav": np.concatenate((source, np.zeros((302-60)*16000, dtype=np.int16), source)),
        "speakerbook_unrelated_after_5min.wav": np.concatenate((source, np.zeros((302-60)*16000, dtype=np.int16), negative)),
        "continuous_20m40s.wav": np.tile(source, 21)[:1240*16000],
    }
    records = {}
    for name, pcm in samples.items():
        with wave.open(str(output / name), "wb") as stream:
            stream.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            stream.writeframes(pcm.astype("<i2", copy=False).tobytes())
        records[name] = {"sha256": digest(output / name), "duration_ms": len(pcm)//16}
    report = {"schema": "speakerbook-emulator-fixtures-v1",
              "scope": "Synthetic audiobook functional fixtures, not independent identity accuracy",
              "source_dataset": manifest["source"], "source_manifest_sha256": manifest["source_manifest_sha256"],
              "first_id": first["file_id"], "negative_id": other["file_id"],
              "different_source_voices": True, "files": records,
              "selection_reason": "Functional positive with admitted profiles in the existing host diagnostic, not held-out accuracy",
              "limitations": ["Repeated source is a functional positive control",
                              "Long fixture repeats source speech; no natural meeting or phone performance claim"]}
    (output / "fixtures.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--android", action="store_true")
    p.add_argument("--host", action="store_true")
    p.add_argument("--fixtures-only", action="store_true")
    p.add_argument("--data", type=Path, default=DATA)
    a = p.parse_args()
    if not (a.data / "local_manifest.json").is_file():
        subprocess.run([sys.executable, str(ROOT/"tools/fetch_russian_bookmix_sample.py"),
                        "--output", str(a.data)], check=True)
    if a.fixtures_only:
        compose_fixtures(a.data, ROOT/".local/speakerbook-offdevice-current/fixtures")
        return
    download("https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/nemo_en_titanet_small.onnx",
             TITANET, SHA_TITANET)
    subprocess.run([sys.executable, str(ROOT/"tools/provision_nemotron.py")], check=True)
    if a.host:
        for name, (url, sha) in COMPILER.items():
            download(MAVEN+url, HARNESS/"kotlin"/(name+".jar"), sha)
        download(MAVEN+"com/microsoft/onnxruntime/onnxruntime/1.17.1/onnxruntime-1.17.1.jar",
                 HARNESS/"onnxruntime-1.17.1.jar",
                 "a4e57e18a04b6c1b5b0e2885af1d8557873d4ca04bfcebf79743966c4c8eb20f")
    if a.android:
        subprocess.run([sys.executable, str(ROOT/"tools/provision_asr.py")], check=True)
        spec = (ROOT/"app/src/main/java/ru/neurostenographer/app/AsrModelSpec.kt").read_text(encoding="utf8")
        import re
        pins = {name: sha for name,sha in re.findall(
            r'"(gigaam_v3_e2e_rnnt_[\w.]+)" to \("([0-9a-f]{64})"', spec)}
        if len(pins) != 4:
            raise ValueError("Expected the four product A3 model pins")
        directory = ROOT/".local/speakerbook-a3"
        base = "https://huggingface.co/Smirnov75/GigaAM-v3-sherpa-onnx/resolve/"+A3_REV+"/"
        for name, sha in pins.items():
            final = directory/name
            if final.is_file() and digest(final) == sha:
                continue
            if "encoder" in name:
                original = directory/"encoder-source.onnx"
                download(base+name, original, A3_ENCODER_SOURCE)
                subprocess.run([sys.executable, str(ROOT/"tools/asr_20261104/strip_unused_opsets.py"),
                                str(original), str(final)], check=True)
                if digest(final) != sha:
                    raise ValueError("Transformed A3 encoder does not match product pin")
                original.unlink()
            else:
                download(base+name, final, sha)
        assets = ROOT/".local/productAssets"
        assets.mkdir(exist_ok=True)
        with zipfile.ZipFile(assets/"gigaam-v3-e2e-rnnt.zip", "w", zipfile.ZIP_STORED) as z:
            for name in pins:
                z.write(directory/name, name)
        shutil.copyfile(ROOT/".local/nemotron.zip", assets/"nemotron.zip")
        compose_fixtures(a.data, ROOT/".local/speakerbook-offdevice-current/fixtures")


if __name__ == "__main__":
    main()
