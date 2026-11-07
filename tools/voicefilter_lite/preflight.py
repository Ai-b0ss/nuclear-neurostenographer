"""Validate pinned models, runtime dependencies, ONNX metadata and CPU contracts."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import platform

from adapter import AdapterError, DEFAULT_MODEL_DIR, LOCK, VoiceFilterLite, verify_models


def run_preflight(model_dir: Path = DEFAULT_MODEL_DIR, threads: int = 1) -> dict:
    models = verify_models(model_dir)
    dependencies = {
        name: importlib.metadata.version(name)
        for name in ("numpy", "scipy", "onnxruntime")
    }
    expected = {"numpy": "2.2.6", "scipy": "1.15.3", "onnxruntime": "1.23.2"}
    if dependencies != expected:
        raise AdapterError(f"Dependency mismatch: expected {expected}, got {dependencies}")
    engine = VoiceFilterLite(model_dir, threads=threads)
    return {
        "status": "OK",
        "mode": "offline_research_only",
        "upstream": LOCK["upstream"],
        "models": models,
        "dependencies": dependencies,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "execution_provider": "CPUExecutionProvider",
        "mask_config": engine.config,
        "dvector_config": engine.dvector_config,
        "enrollment_seconds": 3.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    args = parser.parse_args()
    try:
        report = run_preflight(args.models_dir, args.threads)
    except (AdapterError, ImportError, OSError) as error:
        raise SystemExit(f"PREFLIGHT FAILED: {error}") from error
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
