"""No-network negative test of pinned-download integrity and cache replacement."""
import hashlib
from pathlib import Path
import tempfile
from unittest.mock import patch
import provision_asr


def main():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "model.onnx"
        path.write_bytes(b"previous")
        expected = hashlib.sha256(b"correct").hexdigest()

        def corrupt(_url, dest):
            Path(dest).write_bytes(b"corrupted download")

        with patch("urllib.request.urlretrieve", corrupt):
            try:
                provision_asr.download("https://example.invalid/model", path, expected)
                raise AssertionError("Corrupt download accepted")
            except ValueError:
                pass
        assert path.read_bytes() == b"previous"
        assert not path.with_suffix(".onnx.part").exists()

        def valid(_url, dest):
            Path(dest).write_bytes(b"correct")

        with patch("urllib.request.urlretrieve", valid):
            provision_asr.download("https://example.invalid/model", path, expected)
        assert path.read_bytes() == b"correct"
        with patch("urllib.request.urlretrieve", side_effect=AssertionError("Cache redownloaded")):
            provision_asr.download("https://example.invalid/model", path, expected)
    print("PASS pinned download: corruption rejected, previous file retained, replacement verified, cache verified")


if __name__ == "__main__":
    main()
