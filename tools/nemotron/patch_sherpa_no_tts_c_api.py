"""Remove upstream disabled-TTS C API stubs from sherpa-onnx v1.12.20.

The upstream TTS=OFF build omits the implementation but still exports
unusable TTS functions and strings. Apply only to a pinned local source
checkout before building a product C API; the original source is retained
in Git. This changes no ASR or diarization code.
"""

import argparse
import subprocess
from pathlib import Path

REVISION = "5ce3d6d93a5f4fe11657bf11a6bf3a022eeef22f"


def remove_disabled_stubs(source: Path) -> bool:
    path = source / "sherpa-onnx" / "c-api" / "c-api.cc"
    content = path.read_text(encoding="utf-8")
    blocks = (
        ("#else\nconst SherpaOnnxOfflineTts *SherpaOnnxCreateOfflineTts(\n",
         "#endif  // SHERPA_ONNX_ENABLE_TTS == 1"),
        ("#else\nconst SherpaOnnxOfflineTts *SherpaOnnxCreateOfflineTtsOHOS(\n",
         "#endif  // #if SHERPA_ONNX_ENABLE_TTS == 1"),
    )
    changed = False
    for start, end in blocks:
        if start not in content:
            continue
        if content.count(start) != 1:
            raise ValueError(f"Unexpected duplicate block: {start}")
        left = content.index(start)
        right = content.index(end, left)
        content = content[:left] + content[right:]
        changed = True
    if changed:
        path.write_text(content, encoding="utf-8", newline="\n")
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Local sherpa-onnx v1.12.20 checkout")
    args = parser.parse_args()
    revision = subprocess.check_output(
        ["git", "-C", str(args.source), "rev-parse", "HEAD"], text=True).strip()
    if revision != REVISION:
        raise ValueError(f"Expected {REVISION}, found {revision}")
    changed = remove_disabled_stubs(args.source)
    print("Removed disabled TTS exports" if changed else "Already patched")


if __name__ == "__main__":
    main()
