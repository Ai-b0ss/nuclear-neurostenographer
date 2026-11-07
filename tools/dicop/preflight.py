"""Validate the pinned DiCoP source checkout without loading or downloading a model.

python tools/dicop/preflight.py --upstream /path/to/DiCoP --output preflight.json

A valid source checkout makes conversion available, but not Russian inference. The published
DiCoP_v0.1 checkpoint is English and based on Parakeet-TDT-0.6b-v2; a local checkpoint is not
considered Russian-proven merely because it exists.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

from contract import CHECKPOINT_ID, MISSING_RUSSIAN_CHECKPOINT, checkpoint_contract, upstream_contract

REQUIRED_SOURCES = ("infer.py", "utils/audio.py", "utils/rttm.py", "utils/stm.py")
REQUIRED_PYTHON = (3, 11)
DEPENDENCIES = ("torch", "nemo", "lhotse", "meeteval")


def git(upstream, *args):
    result = subprocess.run(
        ["git", *args], cwd=upstream, check=False, capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode:
        raise ValueError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def inspect(upstream, checkpoint=None):
    upstream = Path(upstream).resolve()
    report = {
        "schema_version": 1,
        "upstream": upstream_contract(),
        "checkpoint": checkpoint_contract(),
        "python": {
            "actual": sys.version.split()[0],
            "required": ">=3.11",
            "ok": sys.version_info >= REQUIRED_PYTHON,
        },
        "dependencies": {
            name: importlib.util.find_spec(name) is not None for name in DEPENDENCIES
        },
        "model_download": "DISABLED",
        "training": "NOT_RUN",
    }
    errors = []
    if not upstream.is_dir():
        errors.append(f"upstream directory not found: {upstream}")
        report["upstream"]["actual_commit"] = None
    else:
        try:
            actual = git(upstream, "rev-parse", "HEAD")
            report["upstream"]["actual_commit"] = actual
            if actual != report["upstream"]["commit"]:
                errors.append(f"upstream commit {actual} != pinned {report['upstream']['commit']}")
            dirty = git(upstream, "status", "--porcelain", "--", *REQUIRED_SOURCES)
            report["upstream"]["required_sources_unmodified"] = not dirty
            if dirty:
                errors.append("pinned inference sources have local modifications")
        except ValueError as exc:
            errors.append(str(exc))
        missing = [name for name in REQUIRED_SOURCES if not (upstream / name).is_file()]
        report["upstream"]["missing_sources"] = missing
        errors.extend(f"missing upstream source: {name}" for name in missing)
    if not report["python"]["ok"]:
        errors.append("Python >=3.11 is required by upstream")

    if checkpoint is None:
        report["checkpoint"]["requested"] = None
        report["checkpoint"]["status"] = "MISSING"
    elif checkpoint == CHECKPOINT_ID:
        report["checkpoint"]["requested"] = checkpoint
        report["checkpoint"]["status"] = "LANGUAGE_MISMATCH"
        errors.append("DiCoP_v0.1 is English; downloading or running it is forbidden for Russian quality evidence")
    elif "parakeet-tdt-0.6b-v3" in checkpoint.lower():
        report["checkpoint"]["requested"] = checkpoint
        report["checkpoint"]["status"] = "WRONG_BASE_MODEL"
        errors.append("Russian Parakeet v3 is not the DiCoP_v0.1 base model")
    else:
        report["checkpoint"]["requested"] = checkpoint
        report["checkpoint"]["status"] = "RUSSIAN_QUALITY_UNPROVEN"
        errors.append(MISSING_RUSSIAN_CHECKPOINT)

    if checkpoint is None or report["checkpoint"]["status"] != "LANGUAGE_MISMATCH":
        errors.append(MISSING_RUSSIAN_CHECKPOINT)
    report["conversion_ready"] = not any(
        error.startswith(("upstream", "pinned", "missing upstream", "Python")) for error in errors
    )
    report["inference"] = {"status": "NOT_RUN", "reason": MISSING_RUSSIAN_CHECKPOINT}
    report["status"] = "BLOCKED"
    report["errors"] = list(dict.fromkeys(errors))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--checkpoint", help="Only identify the checkpoint; never fetch or load it")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = inspect(args.upstream, args.checkpoint)
    text = json.dumps(report, ensure_ascii=False, indent=1) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
