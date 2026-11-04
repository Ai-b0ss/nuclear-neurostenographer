"""Does the Nemotron ONNX export run on ONNX Runtime 1.17.1, the version pinned for the Android app?

Unmodified graphs declare IR 10 and are rejected there. This writes copies declaring IR 9 and compares results.
python check_ort117.py prepare ONNX_DIR OUT_DIR   (needs the onnx package)
Then run run_c1.py from an ORT 1.17.1 environment on OUT_DIR, and compare the TSV files.
"""
from pathlib import Path
import shutil
import sys

import onnx


def main():
    source, out = Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    for name in ("diarize.py", "constants.npz"):
        shutil.copyfile(source / name, out / name)
    for name in ("preprocessor_core.onnx", "model.int8.onnx", "model.onnx"):
        model = onnx.load(source / name)
        print(name, "ir", model.ir_version, "opsets", [(o.domain, o.version) for o in model.opset_import], "external", any(t.data_location == 1 for t in model.graph.initializer))
        model.ir_version = 9
        onnx.save(model, out / name)


if __name__ == "__main__":
    main()
