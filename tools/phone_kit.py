"""Install and check the offline kit on a USB-connected Android phone (adb), and collect evidence.

  python phone_kit.py wait                  # wait for the phone to appear, explain what is missing, then check
  python phone_kit.py check                 # is the phone suitable? (ABI, Android, free space, network state)
  python phone_kit.py install               # verify SHA256SUMS, install the APK, push models, wait for install
  python phone_kit.py monitor --minutes 25  # sample app and worker memory, battery, temperature while you test
  python phone_kit.py scan                  # look for ANR, crashes and kills of the app in logcat/DropBox
  python phone_kit.py exports --prefix transcript   # pull and validate TXT/JSON/SRT saved in Download

Only metadata is collected: no audio and no transcript text leave the phone through this tool
(`exports` copies the files you saved yourself, to validate their structure).
adb is found automatically (see find_adb) or given with --adb PATH or the ADB_PATH variable;
nothing is installed and PATH is not changed. Needs Python 3.8+ and adb, nothing else.
Without a phone every subcommand ends with a clear message and exit code 2 (NOT_RUN).
"""
import argparse
import glob
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

PACKAGE = "ru.neurostenographer.app"
KIT_DIR_ON_PHONE = f"/sdcard/Android/data/{PACKAGE}/files/kit"
HERE = Path(__file__).resolve().parent
MIN_FREE_KIB = 1_500_000          # APK + two ZIPs + staging copy + installed models, with margin
MIN_RAM_KIB = 3_000_000
KIT_FILES = ("app-debug.apk", "gigaam-v3.zip", "diarization.zip")
NOT_RUN = 2


class Adb:
    def __init__(self, serial=None, executable="adb"):
        self.prefix = [executable] + (["-s", serial] if serial else [])

    def run(self, *args, timeout=60, check=True):
        result = subprocess.run(self.prefix + list(args), capture_output=True, text=True, timeout=timeout)
        if check and result.returncode != 0:
            raise RuntimeError(f"adb {' '.join(args)} failed: {(result.stderr or result.stdout).strip()}")
        return result.stdout

    def shell(self, *args, timeout=60, check=True):
        return self.run("shell", *args, timeout=timeout, check=check)


def find_adb(explicit=None, environ=None, which=shutil.which, is_file=os.path.isfile, glob_files=glob.glob,
             module_dir=None):
    """Return (path, source) of an adb executable, or (None, reason). Order:
    --adb, ADB_PATH/ADB, PATH, ANDROID_HOME/ANDROID_SDK_ROOT, default SDK folders, the `adbutils`
    Python package, and bundled copies in per-user Python environments (such as the extension
    folders of desktop apps). Nothing is installed and PATH is not modified.
    """
    environ = os.environ if environ is None else environ
    exe = "adb.exe" if os.name == "nt" else "adb"
    if explicit:
        found = explicit if is_file(explicit) else which(explicit)
        return (found, "--adb") if found else (None, f"--adb {explicit} does not exist")
    for name in ("ADB_PATH", "ADB"):
        value = environ.get(name)
        if value and is_file(value):
            return value, name
    found = which("adb")
    if found:
        return found, "PATH"
    for name in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        root = environ.get(name)
        if root and is_file(os.path.join(root, "platform-tools", exe)):
            return os.path.join(root, "platform-tools", exe), name
    local, home = environ.get("LOCALAPPDATA"), os.path.expanduser("~")
    for folder in filter(None, [local and os.path.join(local, "Android", "Sdk", "platform-tools"),
                                os.path.join(home, "Android", "Sdk", "platform-tools"),
                                os.path.join(home, "Library", "Android", "sdk", "platform-tools")]):
        if is_file(os.path.join(folder, exe)):
            return os.path.join(folder, exe), "default SDK folder"
    package = module_dir
    if package is None:
        spec = importlib.util.find_spec("adbutils")
        package = os.path.dirname(spec.origin) if spec and spec.origin else None
    if package and is_file(os.path.join(package, "binaries", exe)):
        return os.path.join(package, "binaries", exe), "adbutils package"
    patterns = []
    for variable in ("LOCALAPPDATA", "APPDATA"):
        base = environ.get(variable)
        if base:
            tail = os.path.join("*", "*", "*", ".venv", "Lib", "site-packages", "adbutils", "binaries", exe)
            patterns += [os.path.join(base, "Packages", "*", "LocalCache", "Roaming", tail),
                         os.path.join(base, tail)]
    for pattern in patterns:
        matches = sorted(glob_files(pattern))
        if matches:
            return matches[0], "bundled adbutils copy"
    return None, "adb not found"


def parse_devices(text):
    """Serials in state `device` from `adb devices` output."""
    devices = []
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices


def parse_device_states(text):
    """{serial: state} for every line of `adb devices` (device, unauthorized, offline, ...)."""
    states = {}
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2:
            states[parts[0]] = parts[1]
    return states


EMULATOR_SERIAL = re.compile(r"^emulator-\d+$")


def is_emulator_serial(serial):
    """Emulators (`emulator-5554`) are never the physical phone, whatever their state."""
    return EMULATOR_SERIAL.match(serial) is not None


WINDOWS_DRIVER_HINT = ("On Windows, if Device Manager shows an 'ADB'/'HDB' interface of the phone with a "
                       "yellow warning (Code 28), its driver is missing: see 'Драйвер Windows' in docs/PHONE_ACCEPTANCE.md.")


def explain_no_device(states, serial=None):
    """Return a concrete reason and next action when no physical phone is usable.

    Emulators in the list are ignored and mentioned separately, so an offline emulator cannot be
    mistaken for a phone that needs reconnecting.
    """
    emulators = {k: v for k, v in states.items() if is_emulator_serial(k)}
    phones = {k: v for k, v in states.items() if not is_emulator_serial(k)}
    if serial:
        phones = {k: v for k, v in phones.items() if k == serial}
    note = ""
    if emulators:
        note = (" Ignored emulator(s) " + ", ".join(f"{k} ({v})" for k, v in sorted(emulators.items()))
                + ": an emulator is never accepted as the physical phone.")
    if not phones:
        return ("no physical phone is visible to adb. Use a data USB cable (not charge-only), set USB mode to "
                "'File transfer', enable Developer options > USB debugging, unlock the screen, reconnect, "
                "and accept 'Allow USB debugging' on the phone. " + WINDOWS_DRIVER_HINT + note)
    if any(v == "unauthorized" for v in phones.values()):
        return ("the phone is connected but has not authorized this PC: unlock it and tap 'Allow' in the "
                "'Allow USB debugging?' dialog (tick 'Always allow'), then retry." + note)
    if any(v == "offline" for v in phones.values()):
        return ("the phone is listed as offline: reconnect the cable, toggle USB debugging off and on, "
                "then retry." + note)
    ready = [k for k, v in phones.items() if v == "device"]
    if len(ready) > 1:
        return f"several phones are ready ({', '.join(ready)}): pass --serial." + note
    return f"unexpected adb states: {phones}" + note


def parse_free_kib(df_output):
    """Available KiB from `df -k /data` (toybox): last data line, 4th numeric column."""
    for line in reversed([l for l in df_output.splitlines() if l.strip()]):
        fields = line.split()
        numbers = [f for f in fields[1:] if f.isdigit()]
        if len(numbers) >= 3:
            return int(numbers[2])
    raise ValueError("Cannot read free space from df output")


def parse_meminfo_total_pss(text):
    match = re.search(r"TOTAL PSS:\s*([0-9]+)", text) or re.search(r"^\s*TOTAL\s+([0-9]+)", text, re.MULTILINE)
    return int(match.group(1)) if match else None


def parse_battery(text):
    temperature = re.search(r"temperature:\s*(-?\d+)", text)
    level = re.search(r"level:\s*(\d+)", text)
    return (int(temperature.group(1)) / 10 if temperature else None, int(level.group(1)) if level else None)


def preflight(adb):
    """Return (problems, report) for the connected phone."""
    abi = adb.shell("getprop", "ro.product.cpu.abi").strip()
    sdk = int(adb.shell("getprop", "ro.build.version.sdk").strip() or 0)
    ram_match = re.search(r"MemTotal:\s*(\d+)", adb.shell("cat", "/proc/meminfo"))
    ram_kib = int(ram_match.group(1)) if ram_match else 0
    free_kib = parse_free_kib(adb.shell("df", "-k", "/data"))
    airplane = adb.shell("settings", "get", "global", "airplane_mode_on", check=False).strip()
    wifi = adb.shell("settings", "get", "global", "wifi_on", check=False).strip()
    report = {
        "model": adb.shell("getprop", "ro.product.model").strip(), "android_sdk": sdk,
        "release": adb.shell("getprop", "ro.build.version.release").strip(), "abi": abi,
        "ram_kib": ram_kib, "free_data_kib": free_kib,
        "airplane_mode": airplane == "1", "wifi_on": wifi == "1",
    }
    qemu = adb.shell("getprop", "ro.kernel.qemu", check=False).strip()
    hardware = adb.shell("getprop", "ro.hardware", check=False).strip()
    report["emulator"] = qemu == "1" or hardware in ("goldfish", "ranchu")
    problems = []
    if report["emulator"]:
        problems.append("this device is an emulator (ro.kernel.qemu/ro.hardware); it cannot be a physical acceptance")
    if abi != "arm64-v8a":
        problems.append(f"ABI is {abi}; the acceptance target is arm64-v8a")
    if sdk < 26:
        problems.append(f"Android SDK {sdk} is below the minimum 26")
    if free_kib < MIN_FREE_KIB:
        problems.append(f"Free space {free_kib // 1024} MiB is below {MIN_FREE_KIB // 1024} MiB")
    if ram_kib < MIN_RAM_KIB:
        problems.append(f"RAM {ram_kib // 1024} MiB is low; expect a ~612 MiB app peak plus a ~455 MiB worker")
    return problems, report


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_kit_files(kit):
    sums = kit / "SHA256SUMS.txt"
    if not sums.is_file():
        return ["SHA256SUMS.txt missing"]
    listed = {}
    for line in sums.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, name = line.split(maxsplit=1)
            listed[name.strip().lstrip("*")] = digest
    problems = []
    for name in KIT_FILES:
        if name not in listed:
            problems.append(f"{name} is not listed in SHA256SUMS.txt")
        elif not (kit / name).is_file():
            problems.append(f"{name} missing")
        elif file_sha256(kit / name) != listed[name]:
            problems.append(f"{name} checksum mismatch: do not install")
    return problems


def connect(args):
    path, source = find_adb(args.adb)
    if path is None:
        print(f"NOT_RUN: {source}. Pass --adb PATH, set ADB_PATH, or install Android platform-tools "
              "(only adb and Python are needed).")
        sys.exit(NOT_RUN)
    print(f"Using adb: {path} ({source})")
    try:
        listing = subprocess.run([path, "devices"], capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"NOT_RUN: adb could not run ({error}).")
        sys.exit(NOT_RUN)
    devices = [d for d in parse_devices(listing) if not is_emulator_serial(d)]
    if args.serial:
        if is_emulator_serial(args.serial):
            print(f"NOT_RUN: --serial {args.serial} is an emulator; physical acceptance needs a real phone.")
            sys.exit(NOT_RUN)
        devices = [d for d in devices if d == args.serial]
    if len(devices) != 1:
        print(f"NOT_RUN: expected exactly one authorized device, found {len(devices)}: "
              + explain_no_device(parse_device_states(listing), args.serial))
        sys.exit(NOT_RUN)
    return Adb(devices[0], path)


def command_check(args):
    adb = connect(args)
    problems, report = preflight(adb)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    for problem in problems:
        print("PROBLEM:", problem)
    if not report["airplane_mode"]:
        print("NOTE: airplane mode is off; turn it on (and Wi-Fi off) before the offline test.")
    return 1 if problems else 0


def command_wait(args):
    """Poll until exactly one authorized phone appears, then run `check`. Exit 2 (NOT_RUN) on timeout."""
    path, source = find_adb(args.adb)
    if path is None:
        print(f"NOT_RUN: {source}. Pass --adb PATH or set ADB_PATH.")
        return NOT_RUN
    print(f"Using adb: {path} ({source}). Waiting up to {args.minutes} min for a phone; Ctrl+C stops.")
    deadline = time.monotonic() + args.minutes * 60
    last = None
    while True:
        listing = subprocess.run([path, "devices"], capture_output=True, text=True, timeout=60).stdout
        states = parse_device_states(listing)
        ready = [k for k, v in states.items()
                 if v == "device" and not is_emulator_serial(k) and (not args.serial or k == args.serial)]
        if len(ready) == 1:
            print(f"Phone found: {ready[0]}")
            return command_check(args)
        reason = explain_no_device(states, args.serial)
        # An emulator appearing or disappearing must not repeat the same advice.
        key = reason.split(" Ignored emulator")[0]
        if key != last:
            print("Waiting:", reason)
            last = key
        if time.monotonic() >= deadline:
            print("NOT_RUN: no usable phone appeared.")
            return NOT_RUN
        time.sleep(3)


def command_install(args):
    kit = Path(args.kit)
    problems = verify_kit_files(kit)
    if problems:
        print("Kit rejected:", "; ".join(problems))
        return 1
    adb = connect(args)
    found, report = preflight(adb)
    if found and not args.force:
        print("Phone check failed (use --force to continue anyway):", "; ".join(found))
        return 1
    adb.run("install", "-r", str(kit / "app-debug.apk"), timeout=300)
    # The app-specific folder only exists after the first launch on some Android versions.
    adb.shell("am", "start", "-n", f"{PACKAGE}/.MainActivity")
    time.sleep(3)
    try:
        adb.shell("mkdir", "-p", KIT_DIR_ON_PHONE)
        for name in ("gigaam-v3.zip", "diarization.zip"):
            adb.run("push", str(kit / name), f"{KIT_DIR_ON_PHONE}/{name}", timeout=900)
    except RuntimeError as error:
        # Some phones forbid writing to Android/data over adb. Fall back to the visible folder.
        print(f"Could not write to the app folder ({error}).")
        for name in ("gigaam-v3.zip", "diarization.zip"):
            adb.run("push", str(kit / name), f"/sdcard/Download/{name}", timeout=900)
        print("The ZIPs are in the phone's Download folder. In the app press 'Установить модель ZIP' and choose "
              "gigaam-v3.zip, then 'Установить модели говорящих ZIP' and choose diarization.zip.")
        return 1
    # Restart so the app scans the folder; it installs both models and deletes the ZIPs.
    adb.shell("am", "force-stop", PACKAGE)
    adb.shell("am", "start", "-n", f"{PACKAGE}/.MainActivity")
    deadline = time.monotonic() + args.wait_minutes * 60
    while time.monotonic() < deadline:
        left = adb.shell("ls", KIT_DIR_ON_PHONE, check=False)
        if "zip" not in left:
            print("Models installed (the kit folder is empty). Open the app: both model buttons should say 'Заменить'.")
            return 0
        time.sleep(5)
    print("Install did not finish; the ZIPs are still in the kit folder. Read the message on the screen, "
          "then run `scan`. A rejected ZIP stays for a retry.")
    return 1


def command_monitor(args):
    adb = connect(args)
    samples = []
    end = time.monotonic() + args.minutes * 60
    started = time.monotonic()
    print("Sampling; run your scenario on the phone. Ctrl+C stops early.")
    try:
        while time.monotonic() < end:
            app = parse_meminfo_total_pss(adb.shell("dumpsys", "meminfo", PACKAGE, check=False))
            worker = parse_meminfo_total_pss(adb.shell("dumpsys", "meminfo", f"{PACKAGE}:diarization", check=False))
            temperature, level = parse_battery(adb.shell("dumpsys", "battery", check=False))
            samples.append({"t_s": round(time.monotonic() - started, 1), "app_pss_kib": app,
                            "worker_pss_kib": worker, "battery_c": temperature, "battery_percent": level})
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    peak = lambda key: max((s[key] for s in samples if s[key] is not None), default=None)
    summary = {"samples": len(samples), "peak_app_pss_kib": peak("app_pss_kib"),
               "peak_worker_pss_kib": peak("worker_pss_kib"), "max_battery_c": peak("battery_c"),
               "interval_s": args.interval, "series": samples}
    Path(args.output).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print({k: v for k, v in summary.items() if k != "series"})
    return 0


def command_scan(args):
    adb = connect(args)
    from app_failure_detector import scan
    logcat = adb.shell("logcat", "-d", "-b", "all", timeout=120)
    dropbox = adb.shell("dumpsys", "dropbox", "--print", "data_app_anr", "data_app_crash",
                        "data_app_native_crash", check=False, timeout=120)
    findings = scan(logcat, dropbox)
    print("\n".join(findings) if findings else "No ANR, crash or kill of the app or its worker found.")
    return 1 if findings else 0


def command_exports(args):
    adb = connect(args)
    target = Path(args.output)
    target.mkdir(parents=True, exist_ok=True)
    for extension in ("txt", "json", "srt"):
        adb.run("pull", f"/sdcard/Download/{args.prefix}.{extension}", str(target / f"{args.prefix}.{extension}"))
    from verify_transcript_exports import verify
    verify(target, args.prefix)
    print("Exports are structurally consistent (this does not measure recognition accuracy).")
    return 0


def main():
    # A console or pipe that cannot show Cyrillic must not crash the tool.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--adb", default=None, help="path to adb (otherwise found automatically)")
    parser.add_argument("--serial")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    wait = sub.add_parser("wait")
    wait.add_argument("--minutes", type=float, default=10)
    install = sub.add_parser("install")
    install.add_argument("--kit", default=str(HERE))
    install.add_argument("--wait-minutes", type=int, default=10)
    install.add_argument("--force", action="store_true")
    monitor = sub.add_parser("monitor")
    monitor.add_argument("--minutes", type=float, default=25)
    monitor.add_argument("--interval", type=float, default=1.0)
    monitor.add_argument("--output", default="phone-monitor.json")
    sub.add_parser("scan")
    exports = sub.add_parser("exports")
    exports.add_argument("--prefix", default="transcript")
    exports.add_argument("--output", default="phone-exports")
    args = parser.parse_args()
    return {"check": command_check, "wait": command_wait, "install": command_install, "monitor": command_monitor,
            "scan": command_scan, "exports": command_exports}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
