"""Save a source-only recovery archive and patch without writing .git or publishing."""
import difflib
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def source_path(name, root=ROOT):
    """Fail closed before opening a recovery archive; never follow external links."""
    path = Path(name)
    prohibited = {".aar", ".apk", ".onnx", ".wav", ".mp3", ".m4a", ".ogg", ".opus", ".flac",
                  ".aac", ".amr", ".p12", ".keystore", ".jks", ".pt", ".gguf", ".pem", ".key",
                  ".jar", ".dll", ".so", ".zip", ".7z", ".exe"}
    assert not path.is_absolute() and ".." not in path.parts and ":" not in name, name
    assert not {part.lower() for part in path.parts} & {".local", ".git", ".gradle", "build", "__pycache__"}, name
    assert path.suffix.lower() not in prohibited, name
    assert not path.name.lower().startswith((".env", "secrets.")), name
    candidate = root / path
    assert candidate.resolve().is_relative_to(root.resolve()) and candidate.is_file(), name
    # Reject binary or accidentally oversized data even with a source suffix.
    assert candidate.stat().st_size <= 2 * 1024 * 1024, name
    body = candidate.read_bytes()
    assert b"\0" not in body, name
    body.decode("utf-8")
    return candidate


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="round1")
    args = parser.parse_args()
    assert args.name.isalnum(), "Checkpoint name must be alphanumeric"
    prefix = args.name
    tracked = set(git("ls-files", "-z").decode().strip("\0").split("\0"))
    untracked = set(filter(None, git("ls-files", "--others", "--exclude-standard", "-z").decode().split("\0")))
    changed = set(filter(None, git("diff", "--name-only", "-z").decode().split("\0"))) | untracked
    files = sorted(tracked | untracked)
    for name in files:
        source_path(name)
    dest = ROOT / ".local"
    dest.mkdir(exist_ok=True)
    patch = []
    for name in sorted(changed):
        old = git("show", "HEAD:" + name).decode("utf-8") if name in tracked else ""
        new = (ROOT / name).read_text(encoding="utf-8")
        for line in difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
            fromfile="a/" + name if name in tracked else "/dev/null", tofile="b/" + name):
            patch.append(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n")
    (dest / f"{prefix}-recovery.patch").write_text("".join(patch), encoding="utf-8", newline="\n")
    with zipfile.ZipFile(dest / f"{prefix}-source.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for name in files:
            z.write(ROOT / name, name)
    manifest = {"base_commit": git("rev-parse", "HEAD").decode().strip(),
        "remote_mutations": "NONE", "changed_files": sorted(changed),
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files},
        "archive_sha256": hashlib.sha256((dest / f"{prefix}-source.zip").read_bytes()).hexdigest()}
    (dest / f"{prefix}-checkpoint.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"source_files": len(files), "changed_files": len(changed),
        "archive": str(dest / f"{prefix}-source.zip"), "patch": str(dest / f"{prefix}-recovery.patch")}))


if __name__ == "__main__":
    main()
