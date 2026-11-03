"""End-to-end check of the adb model-kit installation on a DISPOSABLE emulator.

Runs after the evidence was collected (it clears the app data):
  1. clean app -> the screen says the recognition model is missing;
  2. a corrupt gigaam-v3.zip pushed to the kit folder -> rejected with the file name, the ZIP stays;
  3. the real public ZIPs pushed -> both models install, both ZIPs are removed, the hint disappears.
Public model assets only; no audio. Never run against a personal phone (it wipes the app data).
"""
import json
import subprocess
import sys
import time
from pathlib import Path

from run_android_ui import AndroidUi, PACKAGE, dismiss_foreign_anr_dialog

ROOT = Path(__file__).resolve().parents[1]
KIT = f"/sdcard/Android/data/{PACKAGE}/files/kit"
ASSETS = ROOT / ".local/androidTestAssets"
MISSING = "Модель распознавания не установлена"


def push(ui, local, name):
    subprocess.run([ui.adb, "push", str(local), f"{KIT}/{name}"], check=True, timeout=900, capture_output=True)


def wait_for(ui, label, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        _, node = ui.find(label=label, timeout=0)
        if node is not None:
            return True
        time.sleep(2)
    return False


def restart(ui):
    ui.shell("am", "force-stop", PACKAGE)
    ui.launch()


def run(ui):
    checks = ui.checks
    for name in ("gigaam-v3.zip", "diarization.zip"):
        if not (ASSETS / name).is_file():
            raise AssertionError(f"Public model asset {name} is missing from {ASSETS}")
    ui.shell("settings", "put", "global", "hide_error_dialogs", "1")
    ui.shell("logcat", "-c")
    ui.started_at = ui.shell("date", "+%Y-%m-%dT%H:%M:%S").strip().replace("T", " ")
    ui.shell("am", "force-stop", PACKAGE)
    ui.shell("pm", "clear", PACKAGE)
    dismiss_foreign_anr_dialog(ui)
    ui.launch()
    ui.visible(MISSING)
    ui.screenshot("kit-no-model")
    checks.append("missing_model_is_explained_on_the_main_screen")

    ui.shell("mkdir", "-p", KIT)
    corrupt = ui.directory / "corrupt-gigaam-v3.zip"
    corrupt.write_bytes(bytes((i * 31) % 256 for i in range(4096)))
    push(ui, corrupt, "gigaam-v3.zip")
    restart(ui)
    if not wait_for(ui, "gigaam-v3.zip:", 60):
        raise AssertionError("A corrupt kit ZIP was not reported by name")
    ui.visible(MISSING)
    if "gigaam-v3.zip" not in ui.shell("ls", KIT):
        raise AssertionError("A rejected ZIP must stay in the kit folder for a retry")
    ui.screenshot("kit-corrupt-rejected")
    checks.append("corrupt_kit_zip_is_rejected_by_name_and_kept")

    push(ui, ASSETS / "gigaam-v3.zip", "gigaam-v3.zip")
    push(ui, ASSETS / "diarization.zip", "diarization.zip")
    restart(ui)
    if not wait_for(ui, "Комплект установлен", 240):
        raise AssertionError("The kit did not install within 240 s")
    left = ui.shell("ls", KIT)
    if "zip" in left:
        raise AssertionError(f"Installed ZIPs were not removed: {left.strip()}")
    _, banner = ui.find(label=MISSING, timeout=1)
    if banner is not None:
        raise AssertionError("The missing-model hint is still shown after the kit install")
    ui.screenshot("kit-installed")
    checks.append("real_kit_zips_install_and_are_removed")
    return {"status": "PASS", "checks": checks, "scope": "Disposable emulator; public model assets; adb push kit install",
            "private_audio_collected": False}


def main():
    ui = AndroidUi(Path("device-evidence/kit"))
    report_file = Path("device-evidence/kit-install.json")
    try:
        report = run(ui)
    except Exception as error:
        report = {"status": "FAIL", "error": str(error), "checks_completed": ui.checks}
        try:
            ui.screenshot("failure")
        except Exception:
            pass
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
