"""Download the pinned public sources of the frozen corpus and verify them. Layout matches build_corpus.py."""
import argparse
import hashlib
from pathlib import Path
import urllib.request

RUBOOK = "https://huggingface.co/datasets/mexus/ru-book-mix-10h/resolve/18655c48833c5acfcd868a36eb38465712d15f1c/"
IVKOND = "https://huggingface.co/datasets/ivkond/synthetic-speech-diarization-ru/resolve/3fa8404cfde61d2e3a3369000ce771747821e844/"
DATAHIVE = "https://huggingface.co/datasets/datahiveai/russian-conversations-sample/resolve/1d22534f5a9ef4a377bc42faeb456d456ce29850/preview/"
SILERO = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx"
PINNED = {
    "raw/rubook/manifest.jsonl": (RUBOOK + "manifest.jsonl", "2f1e26fe123afe43e76b96cd49fd62e75bdb94c2f056c1fc7fa43c981de46a6c"),
    "raw/rubook/shard-0000.tar": (RUBOOK + "data/shard-0000.tar", "116e65e98552b3d93807e09bbac77e3c982332487438b3e2d3f789ec5a183da3"),
    "raw/rubook/shard-0001.tar": (RUBOOK + "data/shard-0001.tar", "e9d4fffbf13f86bd3b542a21f2cfd996ada59e11a398cdca4a81572e1a04219c"),
    "raw/rubook/shard-0002.tar": (RUBOOK + "data/shard-0002.tar", "ce1595c269a6f83e32b00b00cb9c26e62f03bc8a102650178455bdb83e324afe"),
    "raw/rubook/shard-0003.tar": (RUBOOK + "data/shard-0003.tar", "0d7e191020006e31a0ee05f4ae2946abd009078100e7fcceebb1c7928934701b"),
    "raw/ivkond/shard0.parquet": (IVKOND + "train-00000-of-00030.parquet", "9b6bba30e9d02d875bf645f6cae997f7de6ebac32b326396066a676cc887abee"),
    "models/silero/silero_vad.onnx": (SILERO, "9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6"),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    args = parser.parse_args()
    for relative, (url, digest) in PINNED.items():
        path = args.data / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(url, path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise SystemExit(f"Hash mismatch: {relative}")
    folder = args.data / "raw/datahive"
    folder.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(DATAHIVE + "metadata.jsonl", folder / "metadata.jsonl")
    for i in range(1, 21):
        name = f"ru_{i:06d}.mp3"
        urllib.request.urlretrieve(DATAHIVE + name, folder / name)
    print("sources ready")


if __name__ == "__main__":
    main()
