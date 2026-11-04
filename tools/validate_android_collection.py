"""Reject adb's zero-exit error text and require complete evidence on green runs.

This validates collection/JSON structure, not truth of model or device results.
"""
import argparse
import json
from pathlib import Path

NAMES = ["asr-0", "asr-1", "diarization-0", "diarization-1", "codec-import",
         "recording", "worker-lifecycle", "mixture", "recording-pipeline"]


def validate(directory):
    collected, missing, invalid = [], [], []
    for name in NAMES:
        path = directory / (name + ".json")
        if not path.exists():
            missing.append(name)
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not data:
                raise ValueError("Expected nonempty JSON object")
            collected.append(name)
        except (ValueError, OSError):
            invalid.append(name)
            # Only known collector-owned outputs are removed, never audio/user data.
            path.unlink(missing_ok=True)
    report = {"scope": "JSON collection only, not inference assertions",
              "collected": collected, "missing": missing, "invalid": invalid,
              "complete": not missing and not invalid}
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "collection-summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    report = validate(args.directory)
    print(json.dumps(report))
    raise SystemExit(1 if args.require_complete and not report["complete"] else 0)
