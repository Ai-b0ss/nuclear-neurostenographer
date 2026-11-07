"""Fetch only the pinned upstream source and checkpoint into .local."""
import argparse
import json
from pathlib import Path
import subprocess

from research import (CHECKPOINT_SHA256, CHECKPOINT_SIZE, CHECKPOINT_URL,
                      DEFAULT_CHECKPOINT, DEFAULT_UPSTREAM, HF_DATASET,
                      HF_REVISION, LOCAL_ROOT, UPSTREAM_COMMIT,
                      UPSTREAM_REPOSITORY, download, sha256, upstream_revision)


def provision_upstream(destination=DEFAULT_UPSTREAM):
    destination = Path(destination)
    if destination.exists():
        if upstream_revision(destination) != UPSTREAM_COMMIT:
            raise RuntimeError(f"Existing upstream is not pinned to {UPSTREAM_COMMIT}: {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(destination)], check=True)
    subprocess.run(["git", "-C", str(destination), "remote", "add", "origin", UPSTREAM_REPOSITORY], check=True)
    subprocess.run(["git", "-C", str(destination), "fetch", "--depth", "1", "origin", UPSTREAM_COMMIT], check=True)
    subprocess.run(["git", "-C", str(destination), "checkout", "--detach", "FETCH_HEAD"], check=True)
    if upstream_revision(destination) != UPSTREAM_COMMIT:
        raise RuntimeError("Fetched upstream revision does not match the pin")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, default=DEFAULT_UPSTREAM)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    args = parser.parse_args()
    provision_upstream(args.upstream)
    download(CHECKPOINT_URL, args.checkpoint, CHECKPOINT_SHA256)
    provenance = {
        "schema_version": 1,
        "upstream_repository": UPSTREAM_REPOSITORY,
        "upstream_commit": UPSTREAM_COMMIT,
        "hf_dataset": HF_DATASET,
        "hf_revision": HF_REVISION,
        "checkpoint_url": CHECKPOINT_URL,
        "checkpoint_sha256": CHECKPOINT_SHA256,
        "checkpoint_size_bytes": CHECKPOINT_SIZE,
        "checkpoint_actual_sha256": sha256(args.checkpoint),
    }
    LOCAL_ROOT.mkdir(parents=True, exist_ok=True)
    (LOCAL_ROOT / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(provenance, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
