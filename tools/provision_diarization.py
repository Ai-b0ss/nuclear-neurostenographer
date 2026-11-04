"""Pinned public diarization assets, never committed. No credentials/dependencies.

python tools/provision_diarization.py [--test-assets]
Creates .local/diarization.zip for offline Android installation.
"""
import argparse
import json
import shutil
import zipfile
from provision_asr import ROOT, download

SEG_REV = "9403a6902bb58e3d5ae8c7e77c3422de279db2e0"
SPEAKER_REV = "065629c313eaf1a01c65c640c46d77e61e9607b4"
SEG_BASE = f"https://huggingface.co/csukuangfj/sherpa-onnx-pyannote-segmentation-3-0/resolve/{SEG_REV}/"
RELEASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
FILES = {
    "segmentation.onnx": (SEG_BASE + "model.onnx", "220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079"),
    "segmentation-LICENSE": (SEG_BASE + "LICENSE", "14d7016ad68e7394d6e6b78d96cc2ae431c905287b89674cfdf021e79e62b8ba"),
    "embedding.onnx": (RELEASE + "speaker-recongition-models/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx", "1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b"),
    "embedding-LICENSE": (f"https://raw.githubusercontent.com/modelscope/3D-Speaker/{SPEAKER_REV}/LICENSE", "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4"),
}
FIXTURE = (RELEASE + "speaker-segmentation-models/0-four-speakers-zh.wav",
           "bedf036caed208386c67b4ef4b11f83d74dd0d420b102163a1c33cd09cde7010")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-assets", action="store_true")
    args = parser.parse_args()
    folder = ROOT / ".local/diarization"
    for name, (url, digest) in FILES.items():
        download(url, folder / name, digest)
    dest = ROOT / ".local/diarization.zip"
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_STORED) as z:
        for name in FILES:
            z.write(folder / name, name)
    if args.test_assets:
        assets = ROOT / ".local/androidTestAssets"
        assets.mkdir(exist_ok=True)
        shutil.copyfile(dest, assets / dest.name)
        download(FIXTURE[0], assets / "four-speakers.wav", FIXTURE[1])
    (ROOT / ".local/diarization-provenance.json").write_text(json.dumps({
        "segmentation_revision": SEG_REV, "embedding_source_revision": SPEAKER_REV,
        "files": FILES, "fixture": FIXTURE,
        "fixture_limit": "Public upstream Chinese example; not Russian dialogue benchmark or DER ground truth",
    }, indent=2) + "\n", encoding="utf-8")
    print(f"VERIFIED OFFLINE DIARIZATION ZIP: {dest}")


if __name__ == "__main__":
    main()
