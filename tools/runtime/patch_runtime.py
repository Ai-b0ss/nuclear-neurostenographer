"""Apply a small reviewed patch ONLY to exact sherpa-onnx 1.12.20 source bytes.

No remote source writes. Candidate is not selected by the app until JNI tests.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

PINS = {
    "math.h": "72875e5be91f78963d6f1d395c749359d8534966d799ae1623d79e94c6caab3a",
    "offline-speaker-diarization-pyannote-impl.h": "acf576376d0e86a8a604138e3de71b02947a388df05f468f673701250b7b4d02",
}


def replace_once(body, old, new):
    if body.count(old) != 1:
        raise ValueError("Patch context must occur exactly once")
    return body.replace(old, new, 1)


def patched(name, body):
    if name == "math.h":
        # Clamp BEFORE forming the iterator passed to partial_sort.
        return replace_once(body,
            "  std::vector<int32_t> vec_index(size);",
            "  if (size <= 0 || topk <= 0) return {};\n"
            "  topk = std::min(size, topk);\n"
            "  std::vector<int32_t> vec_index(size);")
    body = replace_once(body, '#include "sherpa-onnx/csrc/math.h"',
        '#include "sherpa-onnx/csrc/math.h"\n'
        '#include "sherpa-onnx/csrc/safe-diarization-labels.h"')
    body = replace_once(body, "auto result = ComputeResult(final_labels);",
        "auto result = ComputeResult(final_labels, final_labels.cols() - 1);")
    body = replace_once(body, "Matrix2DInt32 ans(num_rows, num_cols);",
        "// Last column is unknown identity, not an additional inferred person.\n"
        "    Matrix2DInt32 ans(num_rows, num_cols + 1);")
    body = replace_once(body, "auto top_k = TopkIndex(&count(i, 0), num_cols, k);",
        "auto top_k = SafeDiarizationFrameLabels(&count(i, 0), num_cols, k);")
    body = replace_once(body, "ans(i, m) = 1;", "ans(i, m < 0 ? num_cols : m) = 1;")
    body = replace_once(body, "const Matrix2DInt32 &final_labels) const {",
        "const Matrix2DInt32 &final_labels, int32_t unknown_speaker = -1) const {")
    # Two constructors in ComputeResult; keep HandleOneChunkSpecialCase unchanged.
    body = replace_once(body, "                                                     speaker_index);",
        "                                                     speaker_index == unknown_speaker ? -1 : speaker_index);")
    body = replace_once(body, "                                                 speaker_index);",
        "                                                 speaker_index == unknown_speaker ? -1 : speaker_index);")
    return body


def apply(source):
    directory = source / "sherpa-onnx/csrc"
    originals = {name: (directory / name).read_bytes() for name in PINS}
    for name, data in originals.items():
        if hashlib.sha256(data).hexdigest() != PINS[name]:
            raise ValueError(f"Unrecognized upstream source: {name}")
    changes = {name: patched(name, data.decode("utf-8")).encode("utf-8")
               for name, data in originals.items()}
    for name, data in changes.items():
        (directory / name).write_bytes(data)
    helper = Path(__file__).with_name("safe-diarization-labels.h")
    shutil.copyfile(helper, directory / helper.name)
    report = {"base_commit": "5ce3d6d93a5f4fe11657bf11a6bf3a022eeef22f",
              "patch": "topk-bounds-and-unknown-v1", "files": {}}
    for name in [*PINS, helper.name]:
        report["files"][name] = {"before": PINS.get(name),
            "after": hashlib.sha256((directory / name).read_bytes()).hexdigest()}
    (source / "runtime-patch.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    print(json.dumps(apply(parser.parse_args().source), indent=2))
