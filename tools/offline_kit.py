"""Assemble and verify the offline installation kit (APK + two model ZIPs + checksums).

  python tools/offline_kit.py fetch-apk          # owner-triggered CI build -> .local/apk/, artifact deleted
  python tools/offline_kit.py assemble --apk .local/apk/app-debug.apk
  python tools/offline_kit.py verify .local/kit

Nothing here uploads anything. Model weights and the APK stay on this PC and the phones.
SHA256SUMS lists the ZIPs for transfer integrity; the importers in the app additionally check
every file inside the ZIPs against hashes pinned in source.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "Ai-b0ss/nuclear-neurostenographer"
WORKFLOW = "build-apk-kit.yml"
ARTIFACT = "private-apk-kit"
# Pinned in app/src/main/java/ru/neurostenographer/app/*ModelStore.kt and tools/runtime/runtime.properties.
RUNTIME_SHA256 = "771fda6a4abf845a6f84f48e05e887fdf159671beb88cbc9aae327806511c1c8"
ASR_FILES = {
    "model.int8.onnx": "f86ebfa0429ced91be6054fc344827e9c6c2572f3c318416cd974b06f66437ec",
    "tokens.txt": "17cc514451bcceac9c280068c71502f8448f99e9fb1456b8d0761651fd0392f2",
    "LICENSE": "f00de6715714c7a63d08639cdbfaa40224eefc407302614bd19f1a8b98c875aa",
}
MIN_ASR_ZIP_BYTES = 200 * 1024 * 1024
MIN_DIARIZATION_ZIP_BYTES = 40 * 1024 * 1024
KIT_FILES = ("app-debug.apk", "gigaam-v3.zip", "diarization.zip")


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def run(*cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=ROOT).stdout


def fetch_apk(destination):
    """Download the APK of the newest successful owner-triggered run, then delete the artifact."""
    runs = json.loads(run("gh", "run", "list", "--repo", REPO, "--workflow", WORKFLOW, "--status", "success",
                          "--limit", "1", "--json", "databaseId,headSha"))
    if not runs:
        sys.exit(f"No successful {WORKFLOW} run. Start it yourself:\n  gh workflow run {WORKFLOW} --repo {REPO} "
                 f"--ref feature/long-recordings -f confirm=PRIVATE-USE-ONE-DAY")
    run_id = str(runs[0]["databaseId"])
    destination.mkdir(parents=True, exist_ok=True)
    run("gh", "run", "download", run_id, "--repo", REPO, "-n", ARTIFACT, "-D", str(destination))
    apk = destination / "app-debug.apk"
    expected = (destination / "APK-SHA256.txt").read_text().split()[0]
    if sha256(apk) != expected:
        sys.exit("APK checksum differs from the one recorded in CI; not using it")
    artifacts = json.loads(run("gh", "api", f"repos/{REPO}/actions/runs/{run_id}/artifacts"))["artifacts"]
    for item in artifacts:
        if item["name"] == ARTIFACT:
            run("gh", "api", "-X", "DELETE", f"repos/{REPO}/actions/artifacts/{item['id']}")
    print(f"APK {apk} sha256 {expected} (run {run_id}); the CI artifact was deleted")


def ensure_models():
    for script, zip_name in (("provision_asr.py", "gigaam-v3.zip"), ("provision_diarization.py", "diarization.zip")):
        if not (ROOT / ".local" / zip_name).is_file():
            args = [sys.executable, str(ROOT / "tools" / script)] + (["--model"] if script == "provision_asr.py" else [])
            subprocess.run(args, check=True, cwd=ROOT)


def verify_kit(kit):
    """Return a list of problems (empty means the kit is consistent)."""
    sums = kit / "SHA256SUMS.txt"
    if not sums.is_file():
        return ["SHA256SUMS.txt missing"]
    problems = []
    listed = {}
    for line in sums.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, name = line.split(maxsplit=1)
            listed[name.strip().lstrip("*")] = digest
    for name in KIT_FILES:
        path = kit / name
        if name not in listed:
            problems.append(f"{name} is not in SHA256SUMS.txt")
        elif not path.is_file():
            problems.append(f"{name} missing")
        elif sha256(path) != listed[name]:
            problems.append(f"{name} checksum mismatch")
    for name, minimum in (("gigaam-v3.zip", MIN_ASR_ZIP_BYTES), ("diarization.zip", MIN_DIARIZATION_ZIP_BYTES)):
        path = kit / name
        if path.is_file() and path.stat().st_size < minimum:
            problems.append(f"{name} is smaller than expected ({path.stat().st_size} bytes)")
    manifest = kit / "KIT_MANIFEST.json"
    if not manifest.is_file():
        problems.append("KIT_MANIFEST.json missing")
    else:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if data.get("runtime_sha256") != RUNTIME_SHA256:
            problems.append("manifest runtime SHA-256 is not the pinned no-TTS runtime")
        if data.get("asr_files") != ASR_FILES:
            problems.append("manifest ASR file hashes differ from the pinned ones")
    return problems


def assemble(apk, kit):
    ensure_models()
    kit.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(apk, kit / "app-debug.apk")
    for name in ("gigaam-v3.zip", "diarization.zip"):
        shutil.copyfile(ROOT / ".local" / name, kit / name)
    provenance = ROOT / ".local/diarization-provenance.json"
    manifest = {
        "kit_scope": "private team use; weights and APK are not published (docs/RUNTIME_LICENSES.md)",
        "runtime_sha256": RUNTIME_SHA256, "asr_files": ASR_FILES,
        "diarization_provenance": json.loads(provenance.read_text(encoding="utf-8")) if provenance.is_file() else None,
        "files": {n: {"bytes": (kit / n).stat().st_size, "sha256": sha256(kit / n)} for n in KIT_FILES},
    }
    (kit / "KIT_MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (kit / "SHA256SUMS.txt").write_text("".join(f"{v['sha256']}  {n}\n" for n, v in manifest["files"].items()),
                                        encoding="utf-8")
    for helper in ("phone_kit.py", "app_failure_detector.py", "verify_transcript_exports.py"):
        shutil.copyfile(ROOT / "tools" / helper, kit / helper)
    problems = verify_kit(kit)
    if problems:
        sys.exit("Kit is inconsistent: " + "; ".join(problems))
    print(f"Kit ready: {kit}")
    for n, v in manifest["files"].items():
        print(f"  {n}  {v['bytes']} bytes  {v['sha256']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch-apk")
    fetch.add_argument("--out", type=Path, default=ROOT / ".local/apk")
    build = sub.add_parser("assemble")
    build.add_argument("--apk", type=Path, required=True)
    build.add_argument("--out", type=Path, default=ROOT / ".local/kit")
    check = sub.add_parser("verify")
    check.add_argument("kit", type=Path)
    args = parser.parse_args()
    if args.command == "fetch-apk":
        fetch_apk(args.out)
    elif args.command == "assemble":
        assemble(args.apk, args.out)
    else:
        problems = verify_kit(args.kit)
        print("OK" if not problems else "\n".join(problems))
        return 1 if problems else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
