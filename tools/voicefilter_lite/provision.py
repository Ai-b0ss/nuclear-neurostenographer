"""Provision pinned VoiceFilter-Lite models and optional isolated Python dependencies."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import venv

from adapter import DEFAULT_MODEL_DIR, LOCK, LOCK_PATH, ROOT, sha256


def provision_file(url: str, source: Path | None, destination: Path, spec: dict) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        actual = {"size_bytes": destination.stat().st_size, "sha256": sha256(destination)}
        if actual == {"size_bytes": spec["size_bytes"], "sha256": spec["sha256"]}:
            return actual
    temporary = destination.with_name(destination.name + ".part")
    try:
        if source is not None:
            if not source.is_file():
                raise ValueError(f"Pinned source file is missing: {source}")
            shutil.copyfile(source, temporary)
        else:
            with urllib.request.urlopen(url, timeout=120) as response, temporary.open("wb") as output:
                shutil.copyfileobj(response, output)
        actual = {"size_bytes": temporary.stat().st_size, "sha256": sha256(temporary)}
        if actual != {"size_bytes": spec["size_bytes"], "sha256": spec["sha256"]}:
            raise ValueError(f"Pinned file integrity mismatch: {destination.name}: {actual}")
        os.replace(temporary, destination)
        return actual
    finally:
        if temporary.exists():
            temporary.unlink()


def install_dependencies(venv_dir: Path) -> str:
    venv_dir.parent.mkdir(parents=True, exist_ok=True)
    if not (venv_dir / "pyvenv.cfg").is_file():
        venv.EnvBuilder(with_pip=True, clear=False).create(venv_dir)
    python = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-r",
            str(LOCK_PATH.with_name("requirements.txt")),
        ],
        check=True,
        timeout=600,
    )
    return str(python)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--source-dir", type=Path, help="Existing upstream checkout; HEAD must match the pin")
    parser.add_argument("--install-deps", action="store_true")
    parser.add_argument("--venv", type=Path, default=ROOT / ".local" / "voicefilter-lite" / "venv")
    args = parser.parse_args()
    source_root = args.source_dir
    if source_root is not None:
        actual_commit = subprocess.run(
            ["git", "-C", str(source_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if actual_commit != LOCK["upstream"]["commit"]:
            raise ValueError(f"Upstream checkout is {actual_commit}, not the pinned commit")
    base = (
        f"https://raw.githubusercontent.com/linsanzhu/open-voicefilter-lite/"
        f"{LOCK['upstream']['commit']}/"
    )
    provenance = {"upstream": LOCK["upstream"], "files": {}}
    for name, spec in LOCK["files"].items():
        source = source_root / spec["path"] if source_root is not None else None
        actual = provision_file(base + spec["path"], source, args.models_dir / name, spec)
        provenance["files"][name] = {**spec, **actual}
        print(f"VERIFIED {name} size={actual['size_bytes']} sha256={actual['sha256']}")
    provenance_path = args.models_dir.parent / "provenance.json"
    provenance_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    if args.install_deps:
        print(f"PYTHON {install_dependencies(args.venv)}")
    print(f"MODELS {args.models_dir}")


if __name__ == "__main__":
    main()
