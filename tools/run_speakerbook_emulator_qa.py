"""Run fresh C2+TitaNet Android QA only on a verified x86_64 emulator.

Never selects a physical device. Artifacts contain metadata, not transcript previews.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid

from provision_asr import ROOT
from evaluate_russian_bookmix_voice_link import SHA_TITANET

PACKAGE = "ru.neurostenographer.app.speakerbookqa"
TEST = PACKAGE + ".test"
ALLOWED = {"run_id", "status", "scope", "execution_environment", "qa_mode",
           "duration_ms", "wall_ms", "rtf", "segments", "profiled_blocks",
           "first_segments", "second_segments", "first_speaker_ids", "second_speaker_ids",
           "shared_speaker_ids", "speaker_source", "unknown_segments",
           "segments_by_5min_interval", "max_battery_temperature_c", "stage", "error"}


def verify_emulator(serial, qemu, abi):
    if not re.fullmatch(r"emulator-\d+", serial) or qemu.strip() != "1" or abi.strip() != "x86_64":
        raise ValueError("Refusing non-emulator/non-x86_64 target; physical phone is never allowed")


def accepted_result(output, record):
    return bool(re.search(r"OK\s*\(1 test\)", output)) and record.get("status") == "PASS" and (
        record.get("execution_environment") == "ANDROID_X86_64_EMULATOR_NOT_PHONE")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--adb", default="adb")
    p.add_argument("--serial")
    p.add_argument("--aapt", required=True)
    p.add_argument("--long", action="store_true")
    p.add_argument("--fixtures", type=Path, default=ROOT/".local/speakerbook-offdevice-current/fixtures")
    p.add_argument("--titanet", type=Path, default=ROOT/".local/speakerbook-active/scratch/models/nemo_en_titanet_small.onnx")
    p.add_argument("--output", type=Path, default=ROOT/".local/speakerbook-offdevice-current/emulator")
    a = p.parse_args()
    listing = subprocess.check_output([a.adb, "devices"], text=True)
    targets = [x.split()[0] for x in listing.splitlines()[1:]
               if len(x.split()) == 2 and x.split()[1] == "device" and x.startswith("emulator-")]
    if a.serial is None:
        if len(targets) != 1:
            p.error("Need exactly one emulator or an explicit --serial")
        a.serial = targets[0]
    def adb(*args, timeout=60, check=True):
        return subprocess.run([a.adb, "-s", a.serial, *map(str, args)], check=check,
                              capture_output=True, text=True, encoding="utf8", errors="replace", timeout=timeout)
    verify_emulator(a.serial, adb("shell", "getprop", "ro.kernel.qemu").stdout,
                    adb("shell", "getprop", "ro.product.cpu.abi").stdout)
    if not a.output.resolve().is_relative_to((ROOT/".local").resolve()):
        p.error("Evidence output must stay under .local")
    a.output.mkdir(parents=True, exist_ok=True)
    summary = {"schema": "speakerbook-emulator-qa-v1", "run_id": uuid.uuid4().hex,
               "status": "RUNNING", "execution_environment": "ANDROID_X86_64_EMULATOR_NOT_PHONE",
               "physical_device_accessed": False, "thermal_performance_measured": False, "cases": []}
    def save():
        path = a.output/"summary.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(summary, indent=2)+"\n", encoding="utf8")
        tmp.replace(path)
    save()
    for mode in ("repeat", "differentSources", "withoutModel", "long"):
        (a.output/(mode+".json")).unlink(missing_ok=True)
    def stop_qa():
        errors = []
        for package in (PACKAGE, TEST):
            try:
                result = adb("shell", "am", "force-stop", package, check=False)
                if result.returncode: errors.append(package + ": force-stop failed")
            except Exception as error:
                errors.append(package + ": " + type(error).__name__)
        try:
            names = adb("shell", "ps", "-A", "-o", "NAME").stdout.splitlines()
            if any(name.strip() == PACKAGE or name.strip().startswith(PACKAGE+":") or name.strip()==TEST for name in names):
                errors.append("QA process still running")
        except Exception as error:
            errors.append("cleanup verification: " + type(error).__name__)
        return {"verified": not errors, "errors": errors}
    begun = time.monotonic()
    try:
        from score_russian_bookmix_c2 import digest
        fixtures = json.loads((a.fixtures/"fixtures.json").read_text(encoding="utf8"))
        for name, info in fixtures["files"].items():
            if Path(name).name != name or digest(a.fixtures/name) != info["sha256"]:
                raise ValueError("Fixture checksum mismatch")
        if digest(a.titanet) != SHA_TITANET:
            raise ValueError("TitaNet checksum mismatch")
        apks = [ROOT/"app/build/outputs/apk/debug/app-debug.apk",
                ROOT/"app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk"]
        for apk, expected in zip(apks, [PACKAGE, TEST]):
            badging = subprocess.check_output([a.aapt, "dump", "badging", str(apk)], text=True)
            match = re.search(r"package: name='([^']+)'", badging)
            if not match or match.group(1) != expected:
                raise ValueError("Refusing APK with unexpected package")
            adb("install", "-r", "-t", apk, timeout=300)
        base = "/sdcard/Android/data/"+PACKAGE+"/files/qa"
        adb("shell", "mkdir", "-p", base+"/titanet")
        adb("push", a.titanet, base+"/titanet/"+a.titanet.name, timeout=120)
        for name in fixtures["files"]:
            adb("push", a.fixtures/name, base+"/"+name, timeout=120)
            actual = adb("shell", "sha256sum", base+"/"+name).stdout.split()[0]
            if actual != fixtures["files"][name]["sha256"]:
                raise ValueError("Emulator audio checksum mismatch")
        adb("shell", "svc", "wifi", "disable")
        adb("shell", "svc", "data", "disable")
        cases = [("repeat", "CrossWindowSpeakerBookDeviceTest", "speakerbook-device-evidence.json"),
                 ("differentSources", "CrossWindowSpeakerBookDeviceTest", "speakerbook-different-sources-evidence.json"),
                 ("withoutModel", "CrossWindowSpeakerBookDeviceTest", "speakerbook-without-model-evidence.json")]
        if a.long:
            cases.append(("long", "LongContinuousSpeakerBookDeviceTest", "speakerbook-long-20min-evidence.json"))
        for mode, klass, filename in cases:
            item = {"mode": mode, "status": "RUNNING"}
            summary["cases"].append(item)
            save()
            adb("shell", "run-as", PACKAGE, "rm", "-f", "files/"+filename)
            try:
                run = adb("shell", "am", "instrument", "-w", "-r", "-e", "class",
                          "ru.neurostenographer.app."+klass, "-e", "qaEnvironment", "emulator",
                          "-e", "qaMode", mode if mode != "long" else "repeat",
                          TEST+"/androidx.test.runner.AndroidJUnitRunner", timeout=4800, check=False)
                (a.output/(mode+".local.log")).write_text(run.stdout+run.stderr, encoding="utf8")
                raw = adb("exec-out", "run-as", PACKAGE, "cat", "files/"+filename, check=False)
                record = json.loads(raw.stdout) if raw.returncode == 0 and raw.stdout.strip() else {}
                clean = {k:v for k,v in record.items() if k in ALLOWED}
                (a.output/(mode+".json")).write_text(json.dumps(clean, indent=2)+"\n", encoding="utf8")
                item["status"] = "PASS" if run.returncode == 0 and accepted_result(run.stdout, record) else "FAIL"
                item["record"] = clean
                if adb("shell", "sha256sum", base+"/titanet/"+a.titanet.name).stdout.split()[0] != SHA_TITANET:
                    raise ValueError("QA model was not restored after missing-model test")
            except Exception as error:
                item.update(status="FAIL", error=type(error).__name__, message=str(error)[:500])
            finally:
                item["cleanup"] = stop_qa()
                if not item["cleanup"]["verified"]: item["status"] = "FAIL"
                save()
        summary["status"] = "PASS_EXECUTION" if all(x["status"]=="PASS" for x in summary["cases"]) else "FAIL"
    except BaseException as error:
        summary.update(status="FAIL", error=type(error).__name__, message=str(error)[:1000])
        raise
    finally:
        summary["cleanup"] = stop_qa()
        if not summary["cleanup"]["verified"]: summary["status"] = "FAIL"
        summary["wall_seconds"] = round(time.monotonic()-begun, 3)
        save()
        print(json.dumps(summary, indent=2))
    if summary["status"] != "PASS_EXECUTION":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
