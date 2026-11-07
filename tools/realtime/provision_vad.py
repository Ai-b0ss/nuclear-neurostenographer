"""Pinned upstream sherpa Silero v5 release asset; MIT. No runtime network access."""
import hashlib
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
URL = 'https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx'
SHA = '9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6'


def main():
    path = ROOT / '.local/realtimeAssets/silero_vad.onnx'
    path.parent.mkdir(parents=True, exist_ok=True)
    data = path.read_bytes() if path.exists() else urllib.request.urlopen(URL, timeout=60).read()
    if len(data) != 643854 or hashlib.sha256(data).hexdigest() != SHA:
        raise SystemExit('Silero release asset size/SHA-256 mismatch; no file replaced')
    path.write_bytes(data)
    # MIT license at snakers4/silero-vad caddb3b7ce1dee88a14d5621a0e9a8fdeb2c2c48
    # is maintained as source text in the opted-in source set.
    print(path, SHA)


if __name__ == '__main__':
    main()
