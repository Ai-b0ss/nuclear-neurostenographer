"""Fetch the pinned LiteRT host code and graphs for the comparison probe. Nothing here is committed or shipped."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from provision_asr import ROOT, download  # noqa: E402

REV = "c6e48fcb3519be365babc7bd74e3e0ae2dc5c855"
BASE = f"https://huggingface.co/litert-community/Nemotron-3-Diarization-LiteRT/resolve/{REV}/"
CODE = {"Nemotron3Diarizer.kt": "95472bcf0fc2740e63d05305c485b2e25eac1137a327760a6f69c010ebaa5432",
        "MelFrontend.kt": "3dfec00ddce6113cb4891a6ce0ab978274163819d20bd517be6064f2fdf12b67",
        "SpeakerCache.kt": "3e8958e72f7bf3b7c2da61b7e2f8fe07797c69480ba1405abd1ac5c0ffe8c38b"}
MODELS = {"nemotron3_diar_frontend.tflite": "c01df58c31b425183c5a008552b517e53007fee39748baa2a4c49c1a55072810",
          "nemotron3_diar_encoder_offline_fp16.tflite": "b312fd74b1931af83185d84f017dd330d0478887db7ccf6ff0e4b65ff0dda28b"}
ASSETS = {"frontend_mel128_257.bin": "bce5ec5f194a5913f6508cee5a85512e7bad2352db8fc28f5c6ff75af8b09137",
          "hann400.bin": "c427e2029118cf789649e5a4d439b6115d0dd0cbf95dcd22f65e3c848add8c5b",
          "silence_embeds.bin": "d4417b3c0eabdf7c47032fac2b5b5a7ee83d819a6ddda8fd8eaf74e2b5cc4ac7"}


def main():
    for name, digest in CODE.items():
        download(BASE + f"android/app/src/main/java/com/nemotron3diar/{name}", ROOT / "app/src/litertProbe/java/com/nemotron3diar" / name, digest)
    target = ROOT / ".local/androidTestAssets/litert"
    for name, digest in MODELS.items():
        download(BASE + name, target / name, digest)
    for name, digest in ASSETS.items():
        download(BASE + f"assets/{name}", target / name, digest)
    print("LiteRT probe ready")


if __name__ == "__main__":
    main()
