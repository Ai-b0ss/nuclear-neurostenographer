"""Build .local/nemotron.zip for the Android C2 prototype from pinned public files. Never committed.

The export declares ONNX IR 10, which ONNX Runtime 1.17.1 rejects. Only the IR version byte of the graph changes;
weights and operators stay the same, and the result is pinned below. The ONNX preprocessor is not shipped: it fails
on 1.17.1 at STFT, so NemotronMel computes the log-mel in Kotlin from the pinned filter bank and window.
python tools/provision_nemotron.py [--test-assets]
"""
import argparse
import hashlib
import json
import shutil
import zipfile
from provision_asr import ROOT, download

ONNX_REV = "4a911fc3ca821b76a99fffd5ce5135bd1efca540"
LITERT_REV = "c6e48fcb3519be365babc7bd74e3e0ae2dc5c855"
ONNX_BASE = f"https://huggingface.co/joosthel/Nemotron-3-Diarization-ONNX/resolve/{ONNX_REV}/"
LITERT_BASE = f"https://huggingface.co/litert-community/Nemotron-3-Diarization-LiteRT/resolve/{LITERT_REV}/assets/"
SOURCE = {
    "model.int8.onnx": (ONNX_BASE + "model.int8.onnx", "17fd04215d655d2feee413a44f96e57d4ebd96cdd9cdbdf8c26da266e08bc835"),
    "LICENSE": (ONNX_BASE + "LICENSE", "2ab44b68365473c112f5092211a38f231cb23e50de68b75a13369adbd76a74df"),
    "NOTICE": (ONNX_BASE + "NOTICE", "29e938a6febe0878b9ab2c8983c342e7d6cae5530964f674dc04312d06d29d71"),
    "mel_filters.bin": (LITERT_BASE + "frontend_mel128_257.bin", "bce5ec5f194a5913f6508cee5a85512e7bad2352db8fc28f5c6ff75af8b09137"),
    "hann400.bin": (LITERT_BASE + "hann400.bin", "c427e2029118cf789649e5a4d439b6115d0dd0cbf95dcd22f65e3c848add8c5b"),
    "silence_embeds.bin": (LITERT_BASE + "silence_embeds.bin", "d4417b3c0eabdf7c47032fac2b5b5a7ee83d819a6ddda8fd8eaf74e2b5cc4ac7"),
}
PATCHED_MODEL_SHA256 = "c465504c2f3a29242e1b3d894187ae5962be7320bed71a2ae203950285ee6025"


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def patch_ir_version(source, destination):
    """ModelProto starts with field 1, ir_version: bytes 08 0a mean IR 10."""
    with open(source, "rb") as f:
        head = f.read(2)
    if head != b"\x08\x0a":
        raise ValueError(f"Unexpected ONNX header: {head.hex()}")
    shutil.copyfile(source, destination)
    with open(destination, "r+b") as f:
        f.seek(1)
        f.write(b"\x09")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-assets", action="store_true")
    args = parser.parse_args()
    folder = ROOT / ".local/nemotron"
    for name, (url, digest) in SOURCE.items():
        download(url, folder / name, digest)
    patched = folder / "model.int8.ir9.onnx"
    patch_ir_version(folder / "model.int8.onnx", patched)
    if sha256(patched) != PATCHED_MODEL_SHA256:
        raise ValueError("Patched model hash mismatch")
    (folder / "CHANGES.txt").write_bytes((
        f"model.int8.ir9.onnx is model.int8.onnx from joosthel/Nemotron-3-Diarization-ONNX@{ONNX_REV} with the ONNX IR version byte changed from 10 to 9.\n"
        f"mel_filters.bin, hann400.bin and silence_embeds.bin come from litert-community/Nemotron-3-Diarization-LiteRT@{LITERT_REV}.\n").encode("utf-8"))
    dest = ROOT / ".local/nemotron.zip"
    names = ["model.int8.ir9.onnx", "mel_filters.bin", "hann400.bin", "silence_embeds.bin", "LICENSE", "NOTICE", "CHANGES.txt"]
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_STORED) as z:
        for name in names:
            z.write(folder / name, name)
    if args.test_assets:
        assets = ROOT / ".local/androidTestAssets"
        assets.mkdir(exist_ok=True)
        shutil.copyfile(dest, assets / dest.name)
    print(json.dumps({"zip": str(dest), "sha256": sha256(dest), "patched_model_sha256": PATCHED_MODEL_SHA256}))


if __name__ == "__main__":
    main()
