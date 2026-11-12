"""Actual C2 -> TitaNet quality replay on a PC; never accesses ADB or a phone."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("data", "model", "titanet", "harness"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--java", default="java")
    p.add_argument("--site", type=Path, default=Path("."))
    p.add_argument("--output", type=Path, default=ROOT / ".local/speakerbook-offdevice-current/host")
    a = p.parse_args()
    sys.path.insert(0, str(a.site.resolve()))
    if not a.output.resolve().is_relative_to((ROOT / ".local").resolve()):
        p.error("Generated evidence must stay in the ignored .local directory")
    a.output.mkdir(parents=True, exist_ok=True)
    state = {"schema": "speakerbook-offdevice-host-v1", "run_id": uuid.uuid4().hex,
             "status": "RUNNING", "execution_environment": platform.platform(),
             "android_test": False, "device_thermal_acceptance": False,
             "quality_release_gate": "NOT_ESTABLISHED"}
    summary = a.output / "summary.json"
    def save():
        temporary = summary.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf8")
        temporary.replace(summary)
    save()
    for name in ("c2-der.json", "c2-titanet.json"):
        (a.output/name).unlink(missing_ok=True)
    t0 = time.monotonic()
    def run(script, *args):
        state["stage"] = script
        save()
        subprocess.run([sys.executable, str(ROOT / "tools" / script), *map(str, args)],
                       cwd=ROOT, check=True)
    try:
        import soundfile as sf
        manifest = json.loads((a.data / "local_manifest.json").read_text(encoding="utf8"))
        if manifest["source_manifest_sha256"] != "2f1e26fe123afe43e76b96cd49fd62e75bdb94c2f056c1fc7fa43c981de46a6c":
            raise ValueError("Unrecognized frozen Russian benchmark manifest")
        rows = manifest["records"][55:70]
        if len(rows) != 15 or any(x["n_speakers"] != 2 for x in rows):
            raise ValueError("Expected frozen first 15 two-speaker clips")
        wavs = a.data / "c2-wavs"
        wavs.mkdir(exist_ok=True)
        from score_russian_bookmix_c2 import digest
        for row in rows:
            fid = row["file_id"]
            for ext, meta in row["files"].items():
                if digest(a.data / (fid + ext)) != meta["sha256"]:
                    raise ValueError("Dataset fingerprint mismatch: " + fid + ext)
            audio, rate = sf.read(a.data / (fid + ".flac"), dtype="int16")
            if rate != 16000 or audio.ndim != 1 or len(audio) != 960000:
                raise ValueError("Unexpected corpus waveform")
            sf.write(wavs / (fid + ".wav"), audio, rate, subtype="PCM_16")
        predictions = a.output / "predictions"
        run("c2pp/run_host.py", "--java", a.java, "--harness", a.harness, "--model", a.model,
            "--wavs", *[wavs / (x["file_id"] + ".wav") for x in rows],
            "--out", predictions, "--work", a.output / "work", "--passes", "product")
        run("score_russian_bookmix_c2.py", "--data", a.data, "--predictions", predictions,
            "--output", a.output / "c2-der.json")
        run("evaluate_russian_bookmix_c2_link.py", "--data", a.data, "--predictions", predictions,
            "--model", a.titanet, "--site", a.site, "--output", a.output / "c2-titanet.json")
        der = json.loads((a.output / "c2-der.json").read_text(encoding="utf8"))
        link = json.loads((a.output / "c2-titanet.json").read_text(encoding="utf8"))
        state.update(status="COMPLETED", stage="done", recordings=len(rows),
                     audio_seconds=900, der_250ms=der["pooled_der_250ms_including_overlap"],
                     speaker_link=link["two_excerpts_global_link"],
                     speaker_link_policy=link["two_excerpts_global_link"]["policy"],
                     runtime=link["model_runtime"],
                     limitations=link["limitations"])
    except BaseException as error:
        state.update(status="FAIL", error=type(error).__name__, message=str(error)[:1000])
        raise
    finally:
        state["wall_seconds"] = round(time.monotonic() - t0, 3)
        save()
        print(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()
